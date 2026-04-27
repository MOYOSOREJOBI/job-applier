"""
Job Applier Backend — FastAPI server on port 7700.
All endpoints return real persisted data from SQLite.
Sources: Greenhouse, Lever, Ashby, Indeed, Glassdoor, Workday, Amazon, Microsoft, GitHub repo.
LinkedIn discovery and apply automation are disabled.
"""
import asyncio
import hashlib
import json
import os
import queue
import re
import shutil
import time
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from storage.db import bootstrap, seed_settings, get_conn, get_setting, set_setting, all_settings
from engine.campaign_runner import create_campaign, run_campaign
from engine.apply.eligibility import explain_auto_apply_eligibility
from engine.apply.portal_policy import (
    AUTO_QUEUE_THRESHOLD,
    assisted_status_for_blocker,
    calculate_viability,
    classify_portal,
    job_domain,
    should_auto_queue,
)
from engine.apply.submit_policy import (
    ASSISTED_REVIEW,
    MANUAL_ONLY,
    can_submit_automatically,
    status_for_policy_decision,
)
from engine.artifacts.local_engine import (
    build_template_library,
    get_questionnaire_payload,
    list_blueprints,
    list_template_library,
    save_profile_answers,
)
from engine.scoring.scorer import score_job

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5174,http://127.0.0.1:5174").split(",")
LINKEDIN_DISABLED = True
LINKEDIN_DISABLED_REASON = "LinkedIn discovery and apply automation are disabled. Apply on linkedin.com manually."
DEFAULT_DISCOVERY_SOURCES = [
    "greenhouse",
    "lever",
    "ashby",
    "workday",
    "amazon",
    "microsoft",
    "github_repo",
]
BLOCKED_AUTOMATED_DISCOVERY_SOURCES = {"linkedin", "indeed", "glassdoor"}

app = FastAPI(title="Job Applier API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Bootstrap ─────────────────────────────────────────────────────────────────
bootstrap()
seed_settings()

# ── In-memory run state ───────────────────────────────────────────────────────
_run_state = {
    "running": False,
    "proc": None,
    "log_q": queue.Queue(maxsize=2000),
    "run_id": None,
    "meta": {},
}
_run_lock = threading.Lock()
_campaign_state = {
    "running": False,
    "campaign_id": None,
    "cancel_requested": False,
    "meta": {},
}
_campaign_lock = threading.Lock()
_coop_state = {
    "running": False,
    "error": "",
}
_coop_lock = threading.Lock()

# ── Auto-apply batch queue ────────────────────────────────────────────────────
_auto_q: queue.Queue = queue.Queue()
_auto_state = {
    "running": False,
    "stop_requested": False,
    "current_job_id": None,
    "current_job_title": "",
    "current_company": "",
    "done": 0,
    "failed": 0,
    "skipped": 0,
    "captcha_paused": False,
    "assisted_session_id": "",
    "assisted_job_id": "",
    "assisted_application_id": "",
    "assisted_blocker": "",
    "log_q": queue.Queue(maxsize=5000),
}
_auto_lock = threading.Lock()

ARTIFACT_RESULT_KEYS = [
    ("resume_pdf", "resume_pdf_path"),
    ("cover_pdf", "cover_pdf_path"),
    ("answer_pack", "answer_pack_path"),
    ("job_search", "search_artifact_path"),
    ("jd_md", "jd_path"),
    ("tips_md", "study_plan_path"),
]
REQUIRED_APPLICATION_ARTIFACTS = ("resume_pdf", "cover_pdf", "answer_pack", "jd_md", "tips_md")


def _artifact_exists(path: str) -> bool:
    return bool(path) and Path(path).exists()


def _missing_required_artifacts(artifacts: dict) -> list[str]:
    return [
        art_type
        for art_type in REQUIRED_APPLICATION_ARTIFACTS
        if not _artifact_exists(artifacts.get(art_type, ""))
    ]


def _apply_artifact_payload(artifacts: dict) -> dict:
    resume_path = artifacts.get("resume_pdf", "")
    cover_path = artifacts.get("cover_pdf", "")
    return {
        "resume_pdf_path": resume_path,
        "cover_pdf_path": cover_path,
        "answer_pack_path": artifacts.get("answer_pack", ""),
    }


def _stage_upload_artifacts(job_id: str, artifacts: dict) -> dict:
    """Copy generated PDFs to clean upload filenames while keeping original records."""
    staged = dict(artifacts)
    stage_dir = ROOT / "artifacts" / "staged" / job_id
    stage_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        "resume_pdf": "Resume.pdf",
        "cover_pdf": "Cover Letter.pdf",
    }
    for art_type, filename in mapping.items():
        src = artifacts.get(art_type, "")
        if not src or not Path(src).exists():
            continue
        dst = stage_dir / filename
        try:
            shutil.copyfile(src, dst)
            staged[art_type] = str(dst)
        except Exception:
            staged[art_type] = src
    return staged


def _pdf_text(path: str) -> str:
    if not path or not Path(path).exists():
        return ""
    try:
        from PyPDF2 import PdfReader  # type: ignore
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def _validate_application_artifacts(job: dict, artifacts: dict) -> tuple[bool, str]:
    resume = artifacts.get("resume_pdf", "")
    cover = artifacts.get("cover_pdf", "")
    if not _artifact_exists(resume) or not _artifact_exists(cover):
        return False, "Resume.pdf or Cover Letter.pdf missing."
    if Path(resume).name != "Resume.pdf" or Path(cover).name != "Cover Letter.pdf":
        return False, "Upload filenames must be exactly Resume.pdf and Cover Letter.pdf."
    if Path(resume).stat().st_size < 3000 or Path(cover).stat().st_size < 3000:
        return False, "Resume.pdf or Cover Letter.pdf appears too small/corrupt."
    resume_text = _pdf_text(resume)
    cover_text = _pdf_text(cover)
    if resume_text and "Moyosore Ogunjobi" not in resume_text:
        return False, "Resume.pdf does not contain Moyosore Ogunjobi."
    company = (job.get("company") or "").strip()
    title = (job.get("title") or "").strip()
    if cover_text:
        if company and company.lower() not in cover_text.lower():
            return False, f"Cover Letter.pdf does not contain company name: {company}."
        title_tokens = [t for t in re.split(r"[^A-Za-z0-9]+", title.lower()) if len(t) >= 5][:3]
        if title_tokens and not any(token in cover_text.lower() for token in title_tokens):
            return False, "Cover Letter.pdf does not appear tailored to the role title."
    return True, ""


def _persist_generated_artifacts(conn, job_id: str, result: dict, created_at: str):
    for art_type, path_key in ARTIFACT_RESULT_KEYS:
        path = result.get(path_key, "")
        if path and Path(path).exists():
            conn.execute(
                "INSERT OR REPLACE INTO artifacts (id, job_id, type, path, checksum, created_at) VALUES (?,?,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    job_id,
                    art_type,
                    path,
                    hashlib.md5(Path(path).read_bytes()).hexdigest(),
                    created_at,
                ),
            )


def _record_application_evidence(conn, application_id: str, artifacts: dict, result: dict | None = None):
    result = result or {}
    confirmation = result.get("confirmation") or {}
    confirmation_text = confirmation.get("reason") or confirmation.get("text") or ""
    conn.execute(
        """
        UPDATE applications
        SET confirmation_text=?,
            uploaded_resume_path=?,
            uploaded_cover_letter_path=?,
            answers_json=?
        WHERE id=?
        """,
        (
            confirmation_text,
            artifacts.get("resume_pdf", ""),
            artifacts.get("cover_pdf", ""),
            artifacts.get("answer_pack", ""),
            application_id,
        ),
    )


def _result_artifact_map(result: dict) -> dict:
    return {
        art_type: result.get(path_key, "")
        for art_type, path_key in ARTIFACT_RESULT_KEYS
        if result.get(path_key)
    }


def _load_answer_pack(path: str) -> dict:
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return {}


def _domain_memory_for_job(conn, job: dict) -> dict:
    domain = job_domain(job)
    if not domain:
        return {}
    row = conn.execute("SELECT * FROM domain_memory WHERE domain=?", (domain,)).fetchone()
    return dict(row) if row else {}


def automation_viability(
    job: dict,
    artifacts: dict | None = None,
    dry_parse: dict | None = None,
    conn=None,
    allow_backfill: bool = False,
) -> dict:
    """
    Lightweight preflight score before spending browser time.
    Dry-parse and domain memory can enrich it when available.
    """
    local_conn = conn or get_conn()
    try:
        domain_memory = _domain_memory_for_job(local_conn, job)
    finally:
        if conn is None:
            local_conn.close()

    viability = calculate_viability(job, domain_memory=domain_memory, dry_parse=dry_parse)
    policy = viability["policy"]
    notes = list(viability["reasons"])
    if artifacts is not None:
        missing = _missing_required_artifacts(artifacts)
        notes.append("artifacts ready" if not missing else f"missing artifacts: {', '.join(missing)}")

    eligible = should_auto_queue(job, viability, allow_backfill=allow_backfill)
    return {
        "score": viability["score"],
        "band": viability["band"],
        "tier": policy["automation_tier"],
        "eligible": eligible,
        "reason": "" if eligible else policy["reason"],
        "notes": notes,
        "policy": policy,
    }


def _persist_job_policy(conn, job_id: str, viability: dict):
    policy = viability.get("policy") or {}
    conn.execute(
        """
        UPDATE jobs
        SET automation_tier=?,
            automation_reason=?,
            automation_viability_score=?,
            automation_viability_band=?,
            automation_viability_reasons=?,
            updated_at=?
        WHERE id=?
        """,
        (
            policy.get("automation_tier", ""),
            policy.get("reason", ""),
            viability.get("score", 0),
            viability.get("band", ""),
            json.dumps(viability.get("notes") or viability.get("reasons") or []),
            now_iso(),
            job_id,
        ),
    )


def update_domain_memory(
    conn,
    job: dict,
    status: str,
    reason: str = "",
    duration_sec: float | None = None,
    selectors: dict | None = None,
):
    domain = job_domain(job)
    if not domain:
        return
    portal = (job.get("portal") or classify_portal(job)["portal"] or "").lower()
    existing = conn.execute("SELECT * FROM domain_memory WHERE domain=?", (domain,)).fetchone()
    row = dict(existing) if existing else {}
    success_count = int(row.get("success_count") or 0)
    fail_count = int(row.get("fail_count") or 0)
    assisted_count = int(row.get("assisted_count") or 0)
    captcha_count = int(row.get("captcha_count") or 0)
    login_count = int(row.get("login_required_count") or 0)
    email_count = int(row.get("email_verification_count") or 0)

    status_l = (status or "").lower()
    reason_l = (reason or "").lower()
    if status_l == "applied":
        success_count += 1
    elif status_l.startswith("assisted"):
        assisted_count += 1
    else:
        fail_count += 1
    if "captcha" in status_l or "captcha" in reason_l:
        captcha_count += 1
    if "login" in status_l or "login" in reason_l:
        login_count += 1
    if "email_verification" in status_l or "verification" in reason_l:
        email_count += 1

    avg_duration = row.get("avg_duration_sec")
    if duration_sec is not None:
        try:
            prev_total = success_count + fail_count + assisted_count - 1
            avg_duration = duration_sec if prev_total <= 0 or avg_duration is None else ((float(avg_duration) * prev_total) + duration_sec) / (prev_total + 1)
        except Exception:
            avg_duration = duration_sec

    conn.execute(
        """
        INSERT INTO domain_memory (
            domain, portal, success_count, fail_count, assisted_count, captcha_count,
            login_required_count, email_verification_count, avg_duration_sec,
            last_status, last_reason, selectors_json, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(domain) DO UPDATE SET
            portal=excluded.portal,
            success_count=excluded.success_count,
            fail_count=excluded.fail_count,
            assisted_count=excluded.assisted_count,
            captcha_count=excluded.captcha_count,
            login_required_count=excluded.login_required_count,
            email_verification_count=excluded.email_verification_count,
            avg_duration_sec=excluded.avg_duration_sec,
            last_status=excluded.last_status,
            last_reason=excluded.last_reason,
            selectors_json=excluded.selectors_json,
            updated_at=excluded.updated_at
        """,
        (
            domain,
            portal,
            success_count,
            fail_count,
            assisted_count,
            captcha_count,
            login_count,
            email_count,
            avg_duration,
            status,
            reason,
            json.dumps(selectors or json.loads(row.get("selectors_json") or "{}")),
            now_iso(),
        ),
    )


def _blocker_from_result(result: dict) -> str | None:
    if result.get("captcha"):
        return "captcha"
    blocker = result.get("blocker")
    if blocker:
        return blocker
    error = (result.get("error") or "").lower()
    if "email" in error and "verification" in error:
        return "email_verification"
    if "captcha" in error:
        return "captcha"
    if "account" in error and ("create" in error or "required" in error):
        return "account_required"
    if "login" in error or "sign in" in error or "password" in error:
        return "login_required"
    if "unknown required" in error or "required field" in error:
        return "unknown_required_field"
    if "manual" in error or "no submit button" in error or "confirmation was not detected" in error or "confirmation" in error:
        return "manual_review"
    if "unsupported" in error:
        return "unsupported_portal"
    return None


def _is_transient_result(result: dict) -> bool:
    if result.get("ok") or _blocker_from_result(result):
        return False
    error = (result.get("error") or "").lower()
    return any(token in error for token in ["timeout", "network", "stale", "not ready", "load", "upload", "navigation"])


def _latest_artifacts(conn, job_id: str) -> dict:
    rows = conn.execute(
        "SELECT type, path FROM artifacts WHERE job_id=? ORDER BY created_at DESC",
        (job_id,),
    ).fetchall()
    artifacts: dict[str, str] = {}
    for row in rows:
        artifacts.setdefault(row["type"], row["path"])
    return artifacts


def _generate_missing_artifacts_for_job(job: dict) -> dict:
    conn = get_conn()
    artifacts = _latest_artifacts(conn, job["id"])
    missing = _missing_required_artifacts(artifacts)
    conn.close()
    if not missing:
        return {"ok": True, "generated": False, "artifacts": artifacts, "missing": []}

    from engine.artifacts.generator import generate_artifacts

    result = generate_artifacts(job)
    conn = get_conn()
    now = now_iso()
    _persist_generated_artifacts(conn, job["id"], result, now)
    conn.execute("UPDATE jobs SET status='prepared', updated_at=? WHERE id=?", (now, job["id"]))
    conn.commit()
    artifacts = _latest_artifacts(conn, job["id"])
    conn.close()
    missing = _missing_required_artifacts(artifacts)
    return {
        "ok": not missing,
        "generated": True,
        "artifacts": artifacts,
        "missing": missing,
    }


def _auto_log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(f"[auto-apply] {msg}")
    try:
        _auto_state["log_q"].put_nowait(entry)
    except queue.Full:
        pass


def _auto_worker():
    """Background thread — processes jobs from _auto_q one at a time."""
    while True:
        try:
            job_id = _auto_q.get(timeout=2)
        except queue.Empty:
            with _auto_lock:
                if _auto_state["running"] and _auto_q.empty():
                    _auto_state["running"] = False
                    _auto_state["current_job_id"] = None
                    _auto_state["current_job_title"] = ""
                    _auto_state["current_company"] = ""
                    _auto_log("Queue empty — auto-apply complete.")
            continue

        with _auto_lock:
            if _auto_state["stop_requested"]:
                _auto_q.task_done()
                _auto_log("Stopped by user request.")
                _auto_state["running"] = False
                _auto_state["stop_requested"] = False
                continue

        conn = get_conn()
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        conn.close()

        if not job:
            _auto_log(f"Job {job_id} not found — skipping.")
            _auto_q.task_done()
            continue

        job = dict(job)
        title = job.get("title", "?")
        company = job.get("company", "?")

        with _auto_lock:
            _auto_state["current_job_id"] = job_id
            _auto_state["current_job_title"] = title
            _auto_state["current_company"] = company

        _auto_log(f"Starting: {title} @ {company}")

        eligible, reason = explain_auto_apply_eligibility(job)
        if not eligible:
            _auto_log(f"Skipping unsupported auto-apply target: {title} @ {company} — {reason}")
            with _auto_lock:
                _auto_state["skipped"] += 1
            _auto_q.task_done()
            continue

        # Ensure all submission artifacts exist before browser time starts.
        conn = get_conn()
        arts_rows = conn.execute(
            "SELECT * FROM artifacts WHERE job_id=? ORDER BY created_at DESC", (job_id,)
        ).fetchall()
        conn.close()
        artifacts = {dict(r)["type"]: dict(r)["path"] for r in arts_rows}

        missing_artifacts = _missing_required_artifacts(artifacts)
        if missing_artifacts:
            _auto_log(f"Generating missing artifacts for {title} @ {company}: {', '.join(missing_artifacts)}")
            try:
                from engine.artifacts.generator import generate_artifacts as _gen
                gen_result = _gen(job)
                _conn2 = get_conn()
                _now2 = now_iso()
                _persist_generated_artifacts(_conn2, job_id, gen_result, _now2)
                _conn2.execute("UPDATE jobs SET status='prepared', updated_at=? WHERE id=?", (_now2, job_id))
                _conn2.commit()
                _conn2.close()
                artifacts = {**artifacts, **_result_artifact_map(gen_result)}
                missing_artifacts = _missing_required_artifacts(artifacts)
                _auto_log(f"Artifacts ready for {title} @ {company}")
            except Exception as ae:
                _auto_log(f"Artifact error: {ae}")
                conn = get_conn()
                conn.execute("UPDATE jobs SET status='prep_failed', updated_at=? WHERE id=?", (now_iso(), job_id))
                conn.commit()
                conn.close()
                with _auto_lock:
                    _auto_state["failed"] += 1
                _auto_q.task_done()
                continue

        if missing_artifacts:
            _auto_log(f"Skipping {title} @ {company} — incomplete artifacts: {', '.join(missing_artifacts)}")
            conn = get_conn()
            conn.execute("UPDATE jobs SET status='prep_failed', updated_at=? WHERE id=?", (now_iso(), job_id))
            conn.commit()
            conn.close()
            with _auto_lock:
                _auto_state["failed"] += 1
            _auto_q.task_done()
            continue

        artifacts = _stage_upload_artifacts(job_id, artifacts)
        valid_artifacts, artifact_reason = _validate_application_artifacts(job, artifacts)
        if not valid_artifacts:
            _auto_log(f"Skipping {title} @ {company} — artifact validation failed: {artifact_reason}")
            conn = get_conn()
            conn.execute("UPDATE jobs SET status='prep_failed', updated_at=? WHERE id=?", (now_iso(), job_id))
            conn.commit()
            conn.close()
            with _auto_lock:
                _auto_state["failed"] += 1
            _auto_q.task_done()
            continue

        conn = get_conn()
        domain_memory = _domain_memory_for_job(conn, job)
        conn.close()
        # In the auto-apply queue, don't let CAPTCHA history from previous jobs
        # block subsequent jobs in the same batch — clear transient failure counts.
        sanitized_domain_memory = {
            **domain_memory,
            "captcha_count": 0,
            "fail_count": min(int(domain_memory.get("fail_count") or 0), 1),
            "last_status": None,
        }
        policy_decision = can_submit_automatically(
            job,
            page_state={},
            artifacts=artifacts,
            answers=_load_answer_pack(artifacts.get("answer_pack", "")),
            domain_memory=sanitized_domain_memory,
        )
        if not policy_decision.get("allowed"):
            mode = policy_decision.get("mode")
            reason = policy_decision.get("reason", "policy_blocked")
            status = status_for_policy_decision(policy_decision)
            _auto_log(f"Policy paused {title} @ {company}: {mode}/{reason}")
            conn = get_conn()
            conn.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", (status, now_iso(), job_id))
            app_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO applications
                    (id, job_id, stage, apply_mode, review_required, final_confirmation_given, failure_reason, notes, created_at, updated_at)
                VALUES (?,?,?,?,1,0,?,?,?,?)
                """,
                (
                    app_id,
                    job_id,
                    status,
                    mode or "ASSISTED_REVIEW",
                    reason,
                    f"Central policy decision: {reason}",
                    now_iso(),
                    now_iso(),
                ),
            )
            _record_application_evidence(conn, app_id, artifacts, {"policy_decision": policy_decision})
            update_domain_memory(conn, job, status, reason)
            conn.commit()
            conn.close()
            with _auto_lock:
                _auto_state["skipped"] += 1
            _auto_q.task_done()
            continue

        # Run fully automated apply
        apply_started = time.time()
        result = {"ok": False, "error": "Apply did not start."}
        from engine.apply.browser_apply import BrowserSession
        for attempt in range(3):
            try:
                session = BrowserSession(
                    session_id=str(uuid.uuid4()),
                    job=job,
                    artifacts=_apply_artifact_payload(artifacts),
                    headless=False,
                    keep_open_on_blocker=True,
                )
                result = session.auto_apply_full()
            except Exception as ex:
                result = {"ok": False, "error": str(ex)}
            if result.get("ok") or not _is_transient_result(result) or attempt == 2:
                break
            wait = 2 ** attempt
            _auto_log(f"Transient failure for {title} @ {company}; retrying in {wait}s ({attempt + 1}/2).")
            time.sleep(wait)
        duration_sec = time.time() - apply_started

        now = now_iso()
        conn = get_conn()

        blocker = _blocker_from_result(result)
        if blocker in {"captcha", "email_verification", "account_required", "login_required", "unknown_required_field", "manual_review"}:
            assisted_status = assisted_status_for_blocker(blocker)
            _auto_log(f"Assisted blocker on {title} @ {company}: {blocker} — queue paused for human review.")
            app_id = str(uuid.uuid4())
            with _auto_lock:
                _auto_state["captcha_paused"] = blocker == "captcha"
                _auto_state["failed"] += 1
                _auto_state["assisted_session_id"] = result.get("session_id", "")
                _auto_state["assisted_job_id"] = job_id
                _auto_state["assisted_application_id"] = app_id
                _auto_state["assisted_blocker"] = blocker
            conn.execute(
                "UPDATE jobs SET status=?, updated_at=? WHERE id=?", (assisted_status, now, job_id)
            )
            conn.execute(
                """
                INSERT INTO applications
                    (id, job_id, stage, apply_mode, review_required, final_confirmation_given, failure_reason, notes, created_at, updated_at)
                VALUES (?,?,?,?,1,0,?,?,?,?)
                """,
                (
                    app_id,
                    job_id,
                    assisted_status,
                    "AUTO_APPLY",
                    result.get("error", blocker),
                    f"Auto-apply paused: {blocker}",
                    now,
                    now,
                ),
            )
            _record_application_evidence(conn, app_id, artifacts, result)
            update_domain_memory(conn, job, assisted_status, result.get("error", blocker), duration_sec=duration_sec)
            conn.commit()
            conn.close()
            with _auto_lock:
                _auto_state["skipped"] += 1
            _auto_q.task_done()
            # Mark this job as needing human help and continue processing the queue
            # rather than draining it — next jobs may be on different domains.
            _auto_log(f"Skipped {title} @ {company} (CAPTCHA/human blocker). Continuing queue.")
            continue

        if result.get("ok"):
            _auto_log(f"Applied: {title} @ {company}")
            app_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO applications
                    (id, job_id, stage, apply_mode, review_required, final_confirmation_given, notes, created_at, updated_at)
                VALUES (?,?,?,?,0,1,?,?,?)
            """, (app_id, job_id, "submitted", "AUTO_APPLY",
                  f"Auto-applied. Fields filled: {len(result.get('filled', []))}",
                  now, now))
            _record_application_evidence(conn, app_id, artifacts, result)
            conn.execute("UPDATE jobs SET status='applied', updated_at=? WHERE id=?", (now, job_id))
            update_domain_memory(conn, job, "applied", "submitted", duration_sec=duration_sec)
            conn.commit()
            with _auto_lock:
                _auto_state["done"] += 1
            # Milestone notification
            total = conn.execute("SELECT COUNT(*) FROM applications WHERE stage='submitted'").fetchone()[0]
            if total > 0 and total % 50 == 0:
                try:
                    from engine.notifier import notify_milestone
                    notify_milestone(total)
                except Exception:
                    pass
        else:
            _auto_log(f"Failed: {title} @ {company} — {result.get('error', 'unknown')}")
            status = "failed_transient" if any(
                token in (result.get("error", "") or "").lower()
                for token in ["timeout", "network", "stale", "not ready", "load", "upload"]
            ) else "failed_unsupported" if blocker == "unsupported_portal" else "assisted_manual_review"
            conn.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", (status, now, job_id))
            app_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO applications
                    (id, job_id, stage, apply_mode, review_required, final_confirmation_given, failure_reason, notes, created_at, updated_at)
                VALUES (?,?,?,?,1,0,?,?,?,?)
                """,
                (
                    app_id,
                    job_id,
                    status,
                    "AUTO_APPLY",
                    result.get("error", "unknown"),
                    "Auto-apply did not reach confirmed submission.",
                    now,
                    now,
                ),
            )
            _record_application_evidence(conn, app_id, artifacts, result)
            update_domain_memory(conn, job, status, result.get("error", "unknown"), duration_sec=duration_sec)
            conn.commit()
            with _auto_lock:
                _auto_state["failed"] += 1

        conn.close()
        _auto_q.task_done()

        # Brief pause between applications to avoid rate limiting
        time.sleep(3)

    with _auto_lock:
        _auto_state["running"] = False
        _auto_state["current_job_id"] = None
    try:
        _write_application_run_summary()
    except Exception as exc:
        _auto_log(f"Run summary write failed: {exc}")


# Start the worker thread (daemon — dies with server)
_auto_worker_thread = threading.Thread(target=_auto_worker, daemon=True)
_auto_worker_thread.start()

# ── Helpers ───────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row) -> dict:
    return dict(row) if row else {}


def insert_notification(conn, kind: str, message: str, job_id: str | None = None):
    conn.execute(
        """
        INSERT INTO notifications (id, type, job_id, message, seen, created_at)
        VALUES (?,?,?,?,0,?)
        """,
        (str(uuid.uuid4()), kind, job_id, message, now_iso()),
    )


def upsert_job(conn, job: dict):
    """Insert or update a job record, preserving first_seen_at."""
    existing = conn.execute("SELECT first_seen_at, status FROM jobs WHERE id=?", (job["id"],)).fetchone()
    now = now_iso()
    viability = automation_viability(job, conn=conn, allow_backfill=True)
    policy = viability["policy"]
    if existing:
        # Update last_seen + score, preserve first_seen and status
        conn.execute("""
            UPDATE jobs SET
                last_seen_at=?, score=?, score_breakdown=?, fit_band=?,
                description_raw=?, description_normalized=?,
                automation_tier=?, automation_reason=?,
                automation_viability_score=?, automation_viability_band=?,
                automation_viability_reasons=?,
                updated_at=?
            WHERE id=?
        """, (
            now,
            job.get("score", 0),
            job.get("score_breakdown", "{}"),
            job.get("fit_band", "unknown"),
            job.get("description_raw", ""),
            job.get("description_normalized", ""),
            policy.get("automation_tier", ""),
            policy.get("reason", ""),
            viability.get("score", 0),
            viability.get("band", ""),
            json.dumps(viability.get("notes", [])),
            now,
            job["id"],
        ))
    else:
        conn.execute("""
            INSERT INTO jobs (
                id, source, source_type, portal, company, title, location, remote_type,
                url, description_raw, description_normalized, posted_at,
                first_seen_at, last_seen_at, score, score_breakdown, fit_band,
                support_tier, apply_mode, status, manual_only, restricted_reason,
                automation_tier, automation_reason, automation_viability_score,
                automation_viability_band, automation_viability_reasons,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            job["id"], job.get("source",""), job.get("source_type","api"),
            job.get("portal",""), job.get("company",""), job.get("title",""),
            job.get("location",""), job.get("remote_type",""),
            job.get("url",""), job.get("description_raw",""),
            job.get("description_normalized",""), job.get("posted_at",""),
            job.get("first_seen_at", now), job.get("last_seen_at", now),
            job.get("score", 0), job.get("score_breakdown","{}"),
            job.get("fit_band","unknown"),
            job.get("support_tier","C"), job.get("apply_mode","PREP_ONLY"),
            job.get("status","discovered"), job.get("manual_only",0),
            job.get("restricted_reason",""),
            policy.get("automation_tier", ""), policy.get("reason", ""),
            viability.get("score", 0), viability.get("band", ""),
            json.dumps(viability.get("notes", [])),
            now, now,
        ))
        insert_notification(
            conn,
            "new_job",
            f"New job: {job.get('title','')} @ {job.get('company','')} (score: {job.get('score',0):.0f})",
            job_id=job["id"],
        )


# ── GET /api/health ──────────────────────────────────────────────────────────
@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "2.0.0", "timestamp": datetime.now(timezone.utc).isoformat()}


# ── Autonomous Scheduler ──────────────────────────────────────────────────────
_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()

def _autonomous_loop():
    """Runs in background: scrape jobs every N hours, then auto-apply to eligible ones."""
    import importlib
    interval_hours = float(os.getenv("SCRAPE_INTERVAL_HOURS", "6"))
    enabled = os.getenv("AUTO_APPLY_ENABLED", "true").lower() == "true"
    if not enabled:
        print("[scheduler] AUTO_APPLY_ENABLED=false — autonomous loop disabled")
        return

    print(f"[scheduler] Autonomous loop started — scraping every {interval_hours}h")
    while not _scheduler_stop.is_set():
        try:
            # 1) Scrape new jobs via jobspy
            _run_job_scrape()
        except Exception as e:
            print(f"[scheduler] Scrape error: {e}")
        try:
            # 2) Auto-apply to top-scoring eligible jobs
            _run_auto_wave()
        except Exception as e:
            print(f"[scheduler] Auto-apply error: {e}")
        try:
            # 3) Check email inbox for confirmations / interview invites
            _run_email_check()
        except Exception as e:
            print(f"[scheduler] Email check error: {e}")
        _scheduler_stop.wait(interval_hours * 3600)

    print("[scheduler] Autonomous loop stopped")


def _run_job_scrape():
    from jobspy import scrape_jobs
    import pandas as pd
    search_terms = [
        "software engineer intern",
        "software developer co-op",
        "backend engineer intern",
        "data engineer intern",
        "machine learning intern",
        "cloud engineer intern",
        "devops intern",
        "iOS developer intern",
    ]
    locations = ["Canada", "Calgary, AB", "Toronto, ON", "Vancouver, BC", "Remote"]
    conn = get_conn()
    new_count = 0
    for term in search_terms:
        for loc in locations[:2]:  # limit to avoid rate limits
            try:
                jobs = scrape_jobs(
                    site_name=["indeed", "glassdoor", "linkedin"],
                    search_term=term,
                    location=loc,
                    results_wanted=30,
                    hours_old=48,
                    country_indeed="Canada",
                )
                for _, row in jobs.iterrows():
                    job_id = str(uuid.uuid4())
                    url = str(row.get("job_url", "") or "")
                    if not url:
                        continue
                    existing = conn.execute("SELECT id FROM jobs WHERE url=?", (url,)).fetchone()
                    if existing:
                        continue
                    desc = str(row.get("description", "") or "")
                    title = str(row.get("title", "") or term)
                    company = str(row.get("company", "") or "Unknown")
                    location = str(row.get("location", "") or loc)
                    now = datetime.now(timezone.utc).isoformat()
                    job_data = {
                        "id": job_id, "title": title, "company": company,
                        "location": location, "url": url,
                        "description_raw": desc[:8000],
                        "source": row.get("site", "jobspy"), "source_type": "scraper",
                    }
                    score_result = score_job(job_data)
                    score = score_result.get("score", 0) if isinstance(score_result, dict) else 0
                    conn.execute("""
                        INSERT INTO jobs (id, source, source_type, company, title, location, url,
                            description_raw, score, status, first_seen_at, last_seen_at, created_at, updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (job_id, job_data["source"], "scraper", company, title, location, url,
                          desc[:8000], score, "discovered", now, now, now, now))
                    conn.commit()
                    new_count += 1
            except Exception as e:
                print(f"[scrape] {term}/{loc}: {e}")
    print(f"[scrape] Added {new_count} new jobs")
    conn.close()


def _run_auto_wave():
    min_score = float(os.getenv("MIN_SCORE_TO_APPLY", "65"))
    daily_cap = int(os.getenv("AUTO_APPLY_DAILY_CAP", "25"))
    conn = get_conn()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    applied_today = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE submitted_at >= ?", (today,)
    ).fetchone()[0]
    remaining = max(0, daily_cap - applied_today)
    if remaining == 0:
        print(f"[auto-apply] Daily cap ({daily_cap}) reached — skipping")
        conn.close()
        return
    top_jobs = conn.execute("""
        SELECT j.id, j.title, j.company, j.url, j.score
        FROM jobs j
        LEFT JOIN applications a ON a.job_id = j.id
        WHERE j.score >= ? AND j.status = 'discovered' AND a.id IS NULL
        ORDER BY j.score DESC LIMIT ?
    """, (min_score, remaining)).fetchall()
    conn.close()
    print(f"[auto-apply] {len(top_jobs)} jobs eligible (score≥{min_score}, cap remaining={remaining})")
    for job_row in top_jobs[:remaining]:
        try:
            _prepare_and_queue_job(dict(job_row))
        except Exception as e:
            print(f"[auto-apply] Error preparing {job_row['title']} @ {job_row['company']}: {e}")


def _prepare_and_queue_job(job: dict):
    from engine.artifacts.local_engine import build_application_artifacts
    job_id = job["id"]
    conn = get_conn()
    full_job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not full_job:
        return
    full_job = dict(full_job)
    try:
        build_application_artifacts(full_job)
        conn2 = get_conn()
        now = datetime.now(timezone.utc).isoformat()
        app_id = str(uuid.uuid4())
        conn2.execute("""
            INSERT INTO applications (id, job_id, stage, apply_mode, created_at, updated_at)
            VALUES (?,?,?,?,?,?)
        """, (app_id, job_id, "prep", "AUTO", now, now))
        conn2.execute("UPDATE jobs SET status='prep' WHERE id=?", (job_id,))
        conn2.commit()
        conn2.close()
        print(f"[auto-apply] Prepared: {job['title']} @ {job['company']}")
    except Exception as e:
        print(f"[auto-apply] Prep failed for {job_id}: {e}")


def _run_email_check():
    import imaplib
    import email as email_lib
    gmail = os.getenv("GMAIL_EMAIL", "")
    app_pw = os.getenv("GMAIL_APP_PASSWORD", "")
    if not gmail or not app_pw:
        return
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(gmail, app_pw)
        mail.select("inbox")
        _, msgs = mail.search(None, 'UNSEEN SUBJECT "application"')
        ids = msgs[0].split() if msgs[0] else []
        conn = get_conn()
        now = datetime.now(timezone.utc).isoformat()
        for mid in ids[-20:]:  # newest 20 unseen
            _, data = mail.fetch(mid, "(RFC822)")
            msg = email_lib.message_from_bytes(data[0][1])
            subject = str(msg.get("Subject", ""))
            sender = str(msg.get("From", ""))
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
            lower_body = (subject + " " + body).lower()
            is_confirmation = any(s in lower_body for s in [
                "thanks for applying", "thank you for applying",
                "application received", "successfully submitted",
                "we received your application",
            ])
            is_interview = any(s in lower_body for s in [
                "interview", "phone screen", "next steps", "move forward",
                "schedule a call", "meet with us",
            ])
            is_rejection = any(s in lower_body for s in [
                "not moving forward", "decided to move in a different direction",
                "not a fit", "position has been filled", "other candidates",
            ])
            if is_confirmation or is_interview or is_rejection:
                status = "interview_invite" if is_interview else ("rejected" if is_rejection else "confirmed")
                conn.execute("""
                    INSERT OR IGNORE INTO email_events (id, subject, sender, status, received_at, body_snippet)
                    VALUES (?,?,?,?,?,?)
                """, (str(uuid.uuid4()), subject[:200], sender[:200], status, now, body[:500]))
                conn.commit()
                print(f"[email] {status}: {subject[:60]}")
        conn.close()
        mail.logout()
    except Exception as e:
        print(f"[email-check] {e}")


def _start_autonomous_scheduler():
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(target=_autonomous_loop, daemon=True, name="autonomous-scheduler")
    _scheduler_thread.start()
    print("[scheduler] Autonomous scheduler started")


# Start autonomous scheduler on boot
_start_autonomous_scheduler()


# ── GET /api/status ───────────────────────────────────────────────────────────
@app.get("/api/status")
def get_status():
    conn = get_conn()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    new_24h = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE first_seen_at >= datetime('now','-24 hours')"
    ).fetchone()[0]
    applied_today = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE submitted_at >= ?", (today,)
    ).fetchone()[0]
    total_applied = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE stage='submitted'"
    ).fetchone()[0]
    artifacts_count = conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
    unseen_notifications = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE seen=0"
    ).fetchone()[0]
    latest_campaign = conn.execute(
        """
        SELECT id, name, state, target_total, target_openai, target_gemini, tomorrow_target,
               selected_count, prepared_count, submitted_count, assistance_count, failed_count,
               started_at, ended_at
        FROM campaigns
        ORDER BY started_at DESC
        LIMIT 1
        """
    ).fetchone()

    # Weekly chart (last 7 days)
    week_chart = []
    for i in range(6, -1, -1):
        day = conn.execute(
            f"SELECT date(first_seen_at, 'localtime') as d, COUNT(*) as c FROM jobs "
            f"WHERE date(first_seen_at, 'localtime') = date('now', '-{i} days') GROUP BY d"
        ).fetchone()
        date_str = conn.execute(f"SELECT date('now', '-{i} days')").fetchone()[0]
        week_chart.append({"date": date_str, "discovered": day[1] if day else 0})

    daily_cap = int(get_setting("DAILY_CAP", "40"))

    conn.close()
    return {
        "total_jobs": total_jobs,
        "new_24h": new_24h,
        "applied_today": applied_today,
        "total_applied": total_applied,
        "artifacts_count": artifacts_count,
        "unseen_notifications": unseen_notifications,
        "daily_cap": daily_cap,
        "remaining": max(0, daily_cap - applied_today),
        "cap_pct": min(100, round(applied_today / max(daily_cap, 1) * 100)),
        "running": _run_state["running"],
        "run_meta": _run_state.get("meta", {}),
        "campaign_running": _campaign_state["running"],
        "campaign_meta": _campaign_state.get("meta", {}),
        "latest_campaign": row_to_dict(latest_campaign),
        "artifact_engine_mode": get_setting("ARTIFACT_ENGINE_MODE", "deterministic"),
        "week_chart": week_chart,
        "linkedin_disabled": LINKEDIN_DISABLED,
        "linkedin_reason": LINKEDIN_DISABLED_REASON,
    }


@app.get("/api/coop-emergency/status")
def coop_emergency_status():
    summary_path = ROOT / "logs" / "coop_emergency_latest.json"
    proof_path = ROOT / "logs" / "coop_emergency_latest.csv"
    summary = {
        "jobs_discovered_raw": 0,
        "jobs_deduplicated": 0,
        "jobs_scored": 0,
        "top_jobs_selected": 0,
        "artifacts_generated": 0,
        "safe_auto_submitted": 0,
        "assisted_review_ready": 0,
        "manual_only_saved": 0,
        "blocked": 0,
        "failed": 0,
        "proof_log": str(proof_path) if proof_path.exists() else "",
        "updated_at": "",
    }
    if summary_path.exists():
        try:
            summary.update(json.loads(summary_path.read_text()))
        except Exception:
            pass
    summary["running"] = _coop_state["running"]
    summary["error"] = _coop_state["error"]
    conn = get_conn()
    try:
        unknown_count = 0
        unknown_path = ROOT / "data" / "user_questions_needed.json"
        if unknown_path.exists():
            payload = json.loads(unknown_path.read_text())
            unknown_count = len(payload.get("blocking_questions") or [])
        review_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM applications
            WHERE stage IN ('READY_FOR_REVIEW','MANUAL_ONLY','BLOCKED_CAPTCHA','BLOCKED_LOGIN','BLOCKED_UNKNOWN_QUESTION')
               OR stage LIKE 'assisted_%'
            """
        ).fetchone()[0]
        summary["unknown_questions_needing_review"] = unknown_count
        summary["review_queue_count"] = review_count
    finally:
        conn.close()
    return summary


@app.get("/api/coop-emergency/proof-log")
def coop_emergency_proof_log():
    proof_path = ROOT / "logs" / "coop_emergency_latest.csv"
    if not proof_path.exists():
        return {"ok": False, "error": "No co-op emergency proof log has been exported yet.", "path": ""}
    return {"ok": True, "path": str(proof_path)}


class CoopEmergencyStartRequest(BaseModel):
    discover: int = 500
    prepare: int = 200
    batch_size: int = 100


def _run_coop_emergency_task(discover: int, prepare: int, batch_size: int):
    try:
        from engine.campaign_runner import run_coop_emergency
        run_coop_emergency(discover=discover, prepare=prepare, batch_size=batch_size)
    except Exception as exc:
        _coop_state["error"] = str(exc)
        print(f"[coop] fatal: {exc}", flush=True)
    finally:
        _coop_state["running"] = False


@app.post("/api/coop-emergency/start")
def start_coop_emergency(req: CoopEmergencyStartRequest):
    with _coop_lock:
        if _coop_state["running"]:
            return {"ok": False, "error": "Co-op emergency runner is already running."}
        _coop_state["running"] = True
        _coop_state["error"] = ""
        threading.Thread(
            target=_run_coop_emergency_task,
            args=(max(1, min(req.discover, 1000)), max(1, min(req.prepare, 500)), max(1, min(req.batch_size, 100))),
            daemon=True,
        ).start()
    return {"ok": True}


# ── GET /api/jobs ─────────────────────────────────────────────────────────────
@app.get("/api/jobs")
def get_jobs(
    status: Optional[str] = None,
    source: Optional[str] = None,
    portal: Optional[str] = None,
    fit_band: Optional[str] = None,
    support_tier: Optional[str] = None,
    new_only: Optional[bool] = False,
    artifact_ready: Optional[bool] = False,
    min_score: Optional[float] = None,
    search: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
):
    conn = get_conn()
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []

    if status:
        query += " AND status=?"
        params.append(status)
    if source:
        query += " AND source LIKE ?"
        params.append(f"%{source}%")
    if portal:
        query += " AND portal=?"
        params.append(portal)
    if fit_band:
        query += " AND fit_band=?"
        params.append(fit_band)
    if support_tier:
        query += " AND support_tier=?"
        params.append(support_tier)
    if new_only:
        query += " AND first_seen_at >= datetime('now','-24 hours')"
    if min_score is not None:
        query += " AND score >= ?"
        params.append(min_score)
    if search:
        query += " AND (title LIKE ? OR company LIKE ? OR location LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])

    query += " ORDER BY score DESC, first_seen_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    jobs = [dict(r) for r in rows]

    # Attach artifact_ready flag from artifacts table
    if jobs:
        ids = [j["id"] for j in jobs]
        art_rows = conn.execute(
            f"SELECT job_id, type, path FROM artifacts WHERE job_id IN ({','.join('?'*len(ids))}) ORDER BY created_at DESC",
            ids,
        ).fetchall()
        art_map: dict[str, dict[str, str]] = {}
        for row in art_rows:
            art_map.setdefault(row["job_id"], {})
            art_map[row["job_id"]].setdefault(row["type"], row["path"])
        for j in jobs:
            artifacts = art_map.get(j["id"], {})
            missing = _missing_required_artifacts(artifacts)
            viability = automation_viability(j, artifacts, conn=conn)
            j["artifact_ready"] = len(missing) == 0
            j["artifact_types"] = sorted(artifacts.keys())
            j["artifact_missing"] = missing
            j["auto_apply_eligible"] = viability["eligible"]
            j["auto_apply_reason"] = viability["reason"]
            j["automation_viability_score"] = viability["score"]
            j["automation_viability_band"] = viability["band"]
            j["automation_tier"] = viability["tier"]
            j["automation_reasons"] = viability["notes"]
            try:
                j["score_breakdown"] = json.loads(j.get("score_breakdown") or "{}")
            except Exception:
                j["score_breakdown"] = {}

    if artifact_ready:
        jobs = [j for j in jobs if j.get("artifact_ready")]

    # Count with same filters (no LIMIT/OFFSET)
    count_query = query.split(" ORDER BY ")[0].replace("SELECT *", "SELECT COUNT(*)")
    count_params = params[:-2]  # strip limit + offset
    total = conn.execute(count_query, count_params).fetchone()[0]
    if artifact_ready:
        total = len(jobs)  # post-filter; approximate
    conn.close()
    return {"jobs": jobs, "total": total, "returned": len(jobs)}


# ── GET /api/jobs/:id ─────────────────────────────────────────────────────────
@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    job = dict(row)
    try:
        job["score_breakdown"] = json.loads(job.get("score_breakdown") or "{}")
    except Exception:
        job["score_breakdown"] = {}
    conn = get_conn()
    arts = conn.execute("SELECT type, path FROM artifacts WHERE job_id=? ORDER BY created_at DESC", (job_id,)).fetchall()
    conn.close()
    artifact_map = {}
    for row in arts:
        artifact_map.setdefault(row["type"], row["path"])
    missing = _missing_required_artifacts(artifact_map)
    viability = automation_viability(job, artifact_map)
    job["artifact_ready"] = len(missing) == 0
    job["artifact_missing"] = missing
    job["auto_apply_eligible"] = viability["eligible"]
    job["auto_apply_reason"] = viability["reason"]
    job["automation_viability_score"] = viability["score"]
    job["automation_viability_band"] = viability["band"]
    job["automation_tier"] = viability["tier"]
    job["automation_reasons"] = viability["notes"]
    return job


# ── GET /api/jobs/:id/artifacts ───────────────────────────────────────────────
@app.get("/api/jobs/{job_id}/artifacts")
def get_job_artifacts(job_id: str):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM artifacts WHERE job_id=? ORDER BY created_at DESC", (job_id,)).fetchall()
    conn.close()
    return {"artifacts": [dict(r) for r in rows]}


@app.post("/api/jobs/{job_id}/dry-parse")
def dry_parse_job(job_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    job = dict(row)
    from engine.apply.browser_apply import dry_parse_application

    result = dry_parse_application(job, headless=True)
    viability = automation_viability(job, dry_parse=result)
    conn = get_conn()
    _persist_job_policy(conn, job_id, viability)
    blocker = result.get("blocker")
    if blocker:
        status = assisted_status_for_blocker(blocker)
        conn.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", (status, now_iso(), job_id))
        update_domain_memory(conn, job, status, result.get("reason") or blocker)
    conn.commit()
    conn.close()
    return {"ok": True, "dry_parse": result, "viability": viability}


# ── GET /api/jobs/:id/application-map ────────────────────────────────────────
@app.get("/api/jobs/{job_id}/application-map")
def get_application_map(job_id: str):
    conn = get_conn()
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job = dict(job)

    if "linkedin" in (job.get("url") or "").lower():
        return {
            "supported": False,
            "reason": "LinkedIn is not supported for assisted apply.",
            "mode": "MANUAL_ONLY",
        }

    tier = job.get("support_tier", "C")
    mode = job.get("apply_mode", "PREP_ONLY")
    eligible, auto_reason = explain_auto_apply_eligibility(job)
    return {
        "job_id": job_id,
        "portal": job.get("portal"),
        "support_tier": tier,
        "apply_mode": mode,
        "manual_only": bool(job.get("manual_only")),
        "restricted_reason": auto_reason or job.get("restricted_reason"),
        "fields_expected": _expected_fields(job.get("portal", "generic")),
        "submit_enabled": eligible,
        "submit_requires_confirmation": True,
    }


def _expected_fields(portal: str) -> list[str]:
    if portal == "greenhouse":
        return ["First Name", "Last Name", "Email", "Phone", "Resume (file)", "Cover Letter (file)", "LinkedIn URL"]
    if portal == "lever":
        return ["Name", "Email", "Phone", "Resume (file)", "LinkedIn URL"]
    if portal == "ashby":
        return ["Full Name", "Email", "Phone", "City", "Country", "LinkedIn", "Resume (file)"]
    if portal == "workday":
        return ["First Name", "Last Name", "Email", "Phone", "City", "Country", "Resume (file)"]
    return ["Name", "Email", "Phone", "Resume (file)"]


# ── POST /api/jobs/:id/prepare ────────────────────────────────────────────────
class PrepareRequest(BaseModel):
    model: Optional[str] = None
    provider: Optional[str] = None


@app.post("/api/jobs/{job_id}/prepare")
def prepare_job(job_id: str, req: PrepareRequest, background_tasks: BackgroundTasks):
    conn = get_conn()
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    engine_mode = get_setting("ARTIFACT_ENGINE_MODE", "deterministic")
    # Accept Claude, OpenAI, or Gemini when LLM mode is enabled.
    api_key = (
        get_setting("CLAUDE_API_KEY")
        or os.environ.get("CLAUDE_API_KEY", "")
        or os.environ.get("ANTHROPIC_API_KEY", "")
    )
    openai_key = get_setting("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    gemini_key = (
        get_setting("GEMINI_API_KEY")
        or os.environ.get("GEMINI_API_KEY", "")
        or os.environ.get("GOOGLE_API_KEY", "")
    )
    if engine_mode == "llm" and not api_key and not openai_key and not gemini_key:
        raise HTTPException(status_code=400, detail="No API key configured. Add CLAUDE_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY in Settings.")

    provider = req.provider or ("local" if engine_mode != "llm" else "anthropic")
    model = req.model or (get_setting("CLAUDE_MODEL", "claude-sonnet-4-6") if provider == "anthropic" else "")
    job_dict = dict(job)

    background_tasks.add_task(_run_prepare, job_dict, api_key, model, provider)
    return {"ok": True, "message": "Artifact generation started. Check Artifacts page in a moment."}


def _run_prepare(job: dict, api_key: str, model: str, provider: str):
    from engine.artifacts.generator import generate_artifacts
    try:
        result = generate_artifacts(job, api_key, model, preferred_provider=provider)
        conn = get_conn()
        now = now_iso()

        _persist_generated_artifacts(conn, job["id"], result, now)

        conn.execute("UPDATE jobs SET status='prepared', updated_at=? WHERE id=?", (now, job["id"]))
        conn.commit()
        conn.close()
        print(f"[prepare] Done: {job['title']} @ {job['company']}")
        try:
            from engine.notifier import notify_prepare_done
            notify_prepare_done(job["title"], job["company"])
        except Exception:
            pass
    except Exception as e:
        print(f"[prepare] FAILED for {job.get('id')}: {e}")
        conn = get_conn()
        conn.execute("UPDATE jobs SET status='prep_failed', updated_at=? WHERE id=?", (now_iso(), job["id"]))
        conn.commit()
        conn.close()


# ── POST /api/artifacts/prepare-batch ───────────────────────────────────────
class PrepareBatchRequest(BaseModel):
    job_ids: list[str]


@app.post("/api/artifacts/prepare-batch")
def prepare_batch(req: PrepareBatchRequest):
    if not req.job_ids:
        return {"prepared": 0, "failed": 0, "results": []}
    job_ids = list(dict.fromkeys(req.job_ids))[:500]
    conn = get_conn()
    placeholders = ",".join("?" * len(job_ids))
    rows = conn.execute(f"SELECT * FROM jobs WHERE id IN ({placeholders})", job_ids).fetchall()
    conn.close()
    jobs_by_id = {row["id"]: dict(row) for row in rows}

    prepared = 0
    failed = 0
    results = []
    for job_id in job_ids:
        job = jobs_by_id.get(job_id)
        if not job:
            failed += 1
            results.append({"job_id": job_id, "ok": False, "error": "Job not found"})
            continue
        try:
            result = _generate_missing_artifacts_for_job(job)
            if result["ok"]:
                prepared += 1
            else:
                failed += 1
            results.append({
                "job_id": job_id,
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "ok": result["ok"],
                "generated": result["generated"],
                "missing": result["missing"],
            })
        except Exception as exc:
            failed += 1
            results.append({
                "job_id": job_id,
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "ok": False,
                "error": str(exc),
            })
    return {"prepared": prepared, "failed": failed, "results": results}


# ── POST /api/jobs/:id/assist-apply ──────────────────────────────────────────
class AssistApplyRequest(BaseModel):
    headless: bool = False


@app.post("/api/jobs/{job_id}/assist-apply")
def assist_apply(job_id: str, req: AssistApplyRequest):
    conn = get_conn()
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    arts = conn.execute("SELECT * FROM artifacts WHERE job_id=? ORDER BY created_at DESC", (job_id,)).fetchall()
    conn.close()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job = dict(job)

    if "linkedin" in (job.get("url") or "").lower():
        return {"ok": False, "error": "LinkedIn is not supported for assisted apply. Apply manually at linkedin.com."}

    if job.get("manual_only"):
        return {
            "ok": False,
            "error": f"This job is manual-only. Reason: {job.get('restricted_reason', 'No URL or unsupported portal')}",
            "apply_url": job.get("url", ""),
        }

    if not job.get("url"):
        return {"ok": False, "error": "No URL for this job. Import with a URL to use ASSIST APPLY."}

    artifacts = {}
    for row in arts:
        a = dict(row)
        artifacts[a["type"]] = a["path"]

    from engine.apply.browser_apply import create_session, get_session

    staged_artifacts = _stage_upload_artifacts(job_id, artifacts)
    session_id = create_session(
        job=job,
        artifacts={
            "resume_pdf_path": staged_artifacts.get("resume_pdf", ""),
            "cover_pdf_path": staged_artifacts.get("cover_pdf", ""),
        },
        headless=req.headless,
    )

    session = get_session(session_id)
    start_result = session.start()
    if not start_result.get("ok"):
        return start_result

    map_result = session.map_fields()
    fill_result = session.fill_safe_fields()
    review = session.get_review_state()

    # Record application
    app_id = str(uuid.uuid4())
    conn = get_conn()
    conn.execute("""
        INSERT INTO applications (id, job_id, stage, apply_mode, browser_session_id,
            review_required, final_confirmation_given, notes, created_at, updated_at)
        VALUES (?,?,?,?,?,1,0,?,?,?)
    """, (
        app_id, job_id, "review", job.get("apply_mode", "ASSISTED_FILL"),
        session_id,
        f"Assisted apply started. Fields filled: {len(fill_result.get('filled',[]))}",
        now_iso(), now_iso(),
    ))
    conn.commit()
    conn.close()

    return {
        "ok": True,
        "session_id": session_id,
        "application_id": app_id,
        "fields_mapped": len(map_result.get("fields", [])),
        "fields_filled": fill_result.get("filled", []),
        "fields_skipped": fill_result.get("skipped", []),
        "review": review,
    }


@app.post("/api/workday/{job_id}/login")
def workday_login_session(job_id: str):
    conn = get_conn()
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    arts = conn.execute("SELECT * FROM artifacts WHERE job_id=? ORDER BY created_at DESC", (job_id,)).fetchall()
    conn.close()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job = dict(job)
    if (job.get("portal") or "").lower() != "workday" and "workday" not in (job.get("url") or "").lower():
        return {"ok": False, "error": "This is not a Workday job."}
    artifacts = {dict(row)["type"]: dict(row)["path"] for row in arts}

    from engine.apply.browser_apply import create_session, get_session

    staged_artifacts = _stage_upload_artifacts(job_id, artifacts)
    session_id = create_session(
        job=job,
        artifacts={
            "resume_pdf_path": staged_artifacts.get("resume_pdf", ""),
            "cover_pdf_path": staged_artifacts.get("cover_pdf", ""),
        },
        headless=False,
        keep_open_on_blocker=True,
    )
    session = get_session(session_id)
    start = session.start()
    if not start.get("ok"):
        return start
    return {
        "ok": True,
        "session_id": session_id,
        "job_id": job_id,
        "domain": job_domain(job),
        "instructions": "Log in manually in the opened Workday browser. Complete MFA/email verification if prompted, then call /api/workday/{job_id}/mark-ready.",
    }


class WorkdayReadyRequest(BaseModel):
    session_id: str = ""


@app.post("/api/workday/{job_id}/mark-ready")
def workday_mark_ready(job_id: str, req: WorkdayReadyRequest):
    from engine.apply.browser_apply import close_session

    conn = get_conn()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Job not found")
    job = dict(row)
    update_domain_memory(conn, job, "workday_session_ready", "Manual Workday login/session prepared by user.")
    viability = automation_viability(job, conn=conn, allow_backfill=True)
    _persist_job_policy(conn, job_id, viability)
    conn.execute("UPDATE jobs SET status='prepared', updated_at=? WHERE id=?", (now_iso(), job_id))
    conn.commit()
    conn.close()
    if req.session_id:
        close_session(req.session_id)
    return {
        "ok": True,
        "domain": job_domain(job),
        "message": "Workday session marked ready. Jobs on this exact Workday domain can now be queued safely until another blocker appears.",
        "viability": viability,
    }


# ── POST /api/jobs/:id/confirm-submit ────────────────────────────────────────
class ConfirmSubmitRequest(BaseModel):
    session_id: str
    application_id: str


@app.post("/api/jobs/{job_id}/confirm-submit")
def confirm_submit(job_id: str, req: ConfirmSubmitRequest):
    from engine.apply.browser_apply import get_session, close_session

    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    conn = get_conn()
    job_row_for_policy = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    artifacts_for_policy = _latest_artifacts(conn, job_id)
    domain_memory = _domain_memory_for_job(conn, dict(job_row_for_policy) if job_row_for_policy else {"id": job_id})
    conn.close()
    job_for_policy = dict(job_row_for_policy) if job_row_for_policy else {"id": job_id}
    policy_decision = can_submit_automatically(
        job_for_policy,
        page_state={
            "fields": getattr(session, "field_map", None) or [],
            "current_url": session.page.url if getattr(session, "page", None) else "",
        },
        artifacts=artifacts_for_policy,
        answers=_load_answer_pack(artifacts_for_policy.get("answer_pack", "")),
        domain_memory=domain_memory,
    )
    if not policy_decision.get("allowed"):
        return {
            "ok": False,
            "blocker": "manual_review",
            "policy_decision": policy_decision,
            "error": "Policy requires manual browser submit. Review the open browser and click submit yourself.",
        }

    result = session.submit()
    now = now_iso()

    conn = get_conn()
    job_row_for_memory = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    job_for_memory = dict(job_row_for_memory) if job_row_for_memory else {"id": job_id}
    if result.get("ok"):
        conn.execute("""
            UPDATE applications SET stage='submitted', submitted_at=?,
                final_confirmation_given=1, updated_at=? WHERE id=?
        """, (now, now, req.application_id))
        conn.execute("UPDATE jobs SET status='applied', updated_at=? WHERE id=?", (now, job_id))
        update_domain_memory(conn, job_for_memory, "applied", "submitted")
        conn.commit()

        # Milestone notification every 100 applications
        total_applied = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE stage='submitted'"
        ).fetchone()[0]
        if total_applied > 0 and total_applied % 100 == 0:
            try:
                from engine.notifier import notify_milestone
                notify_milestone(total_applied)
            except Exception as _ne:
                print(f"[notify] milestone error: {_ne}")

        # Notify apply done
        try:
            job_row = conn.execute("SELECT title, company FROM jobs WHERE id=?", (job_id,)).fetchone()
            if job_row:
                from engine.notifier import notify_apply_done
                notify_apply_done(job_row["title"], job_row["company"], "submitted")
        except Exception as _ne:
            print(f"[notify] apply_done error: {_ne}")
    else:
        blocker = _blocker_from_result(result)
        status = assisted_status_for_blocker(blocker) if blocker else "failed_transient" if _is_transient_result(result) else "assisted_manual_review"
        conn.execute("""
            UPDATE applications SET stage=?, failure_reason=?, updated_at=? WHERE id=?
        """, (status, result.get("error", ""), now, req.application_id))
        conn.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", (status, now, job_id))
        update_domain_memory(conn, job_for_memory, status, result.get("error", ""))
        conn.commit()
    conn.close()

    close_session(req.session_id)
    return result


# ── POST /api/auto-apply/batch ────────────────────────────────────────────────
class BatchAutoApplyRequest(BaseModel):
    job_ids: list[str]
    dry_parse: bool = True
    min_viability: int = 85
    # Kept for backward-compatible clients. Risky portals are never allowed to
    # bypass viability checks; assisted outcomes pause the queue for review.
    assisted_mode: bool = False


def _enqueue_auto_apply_ids(eligible_ids: list[str], skipped: list[dict]) -> dict:
    with _auto_lock:
        if _auto_state["captcha_paused"]:
            _auto_state["captcha_paused"] = False
        _auto_state["stop_requested"] = False
        _auto_state["running"] = True
        _auto_state["done"] = 0
        _auto_state["failed"] = 0
        _auto_state["skipped"] = len(skipped)

    queued = 0
    for job_id in eligible_ids:
        try:
            _auto_q.put_nowait(job_id)
            queued += 1
        except queue.Full:
            break

    if skipped:
        sample = ", ".join(
            f"{item.get('company', '?')}:{item.get('portal', '?')}"
            for item in skipped[:5]
        )
        suffix = "..." if len(skipped) > 5 else ""
        _auto_log(f"Skipped {len(skipped)} unsupported/manual jobs before queueing ({sample}{suffix}).")
    _auto_log(f"Queued {queued} auto-safe jobs for auto-apply.")
    return {"ok": True, "queued": queued, "skipped": skipped}


@app.post("/api/auto-apply/batch")
def batch_auto_apply(req: BatchAutoApplyRequest):
    if not req.job_ids:
        return {"ok": False, "error": "No job IDs provided"}

    requested_ids = list(dict.fromkeys(req.job_ids))
    conn = get_conn()
    placeholders = ",".join("?" * len(requested_ids))
    rows = conn.execute(
        f"SELECT * FROM jobs WHERE id IN ({placeholders})",
        requested_ids,
    ).fetchall()
    conn.close()
    jobs_by_id = {row["id"]: dict(row) for row in rows}

    eligible_ids: list[str] = []
    skipped: list[dict] = []
    dry_parser = None
    for job_id in requested_ids:
        job = jobs_by_id.get(job_id)
        if not job:
            skipped.append({"job_id": job_id, "reason": "Job not found."})
            continue
        min_viability = max(0, min(int(req.min_viability), 100))
        allow_backfill = min_viability < 85
        # When explicitly supplying job IDs, ignore accumulated CAPTCHA history —
        # the user is intentionally re-trying these jobs.
        _patched_job = {**job, "_override_captcha_count": 0}
        viability = automation_viability(_patched_job, allow_backfill=allow_backfill)

        # Portal must support auto-apply even when explicitly requested
        portal = (job.get("portal") or "").lower()
        portal_ok = portal in {"lever", "ashby", "simple", "greenhouse"}
        if not portal_ok:
            skipped.append({
                "job_id": job_id,
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "portal": portal,
                "viability_score": viability.get("score", 0),
                "reason": f"portal '{portal}' not supported for auto-apply",
            })
            continue

        if viability["eligible"] and req.dry_parse:
            if dry_parser is None:
                from engine.apply.browser_apply import dry_parse_application as dry_parser
            dry = dry_parser(job, headless=True)
            viability = automation_viability(_patched_job, dry_parse=dry, allow_backfill=allow_backfill)
            conn = get_conn()
            _persist_job_policy(conn, job_id, viability)
            if dry.get("blocker"):
                status = assisted_status_for_blocker(dry.get("blocker"))
                conn.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", (status, now_iso(), job_id))
                update_domain_memory(conn, job, status, dry.get("reason") or dry.get("blocker"))
            conn.commit()
            conn.close()

        # For explicit batch requests: skip score gate if portal is supported and apply_mode is set
        apply_mode_ok = (job.get("apply_mode") or "").strip().upper() == "ASSISTED_FILL"
        if apply_mode_ok and portal_ok:
            eligible_ids.append(job_id)
            continue

        if not viability["eligible"] or int(viability.get("score") or 0) < min_viability:
            skipped.append(
                {
                    "job_id": job_id,
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "portal": portal,
                    "viability_score": viability["score"],
                    "reason": viability["reason"] or "; ".join(viability["notes"]),
                }
            )
            continue

        eligible_ids.append(job_id)

    if not eligible_ids:
        _auto_log(f"No supported auto-apply jobs queued. Skipped {len(skipped)} unsupported/manual jobs.")
        return {
            "ok": False,
            "error": "No safe auto-apply jobs. Use Lever or Ashby jobs with viability >= the requested threshold; risky portals are assisted only.",
            "queued": 0,
            "skipped": skipped,
        }

    return _enqueue_auto_apply_ids(eligible_ids, skipped)


class AutoApplyWaveRequest(BaseModel):
    target: int = 100
    min_viability: int = AUTO_QUEUE_THRESHOLD
    portals: list[str] = ["lever", "ashby", "simple"]
    exclude_portals: list[str] = ["workday", "linkedin"]
    prepare_artifacts: bool = True
    dry_parse: bool = True


@app.post("/api/auto-apply/wave")
def auto_apply_wave(req: AutoApplyWaveRequest):
    target = max(1, min(int(req.target), 500))
    portals = [p.lower() for p in (req.portals or [])]
    exclude = {p.lower() for p in (req.exclude_portals or [])}
    allowed = [p for p in portals if p not in exclude]
    if not allowed:
        return {"ok": False, "error": "No allowed portals for wave."}

    conn = get_conn()
    placeholders = ",".join("?" * len(allowed))
    rows = conn.execute(
        f"""
        SELECT *
        FROM jobs
        WHERE COALESCE(url, '') != ''
          AND status NOT IN ('applied')
          AND COALESCE(status, '') NOT LIKE 'assisted_%'
          AND COALESCE(status, '') NOT LIKE 'failed_%'
          AND COALESCE(status, '') NOT IN ('prep_failed')
          AND portal IN ({placeholders})
        ORDER BY automation_viability_score DESC, score DESC, first_seen_at DESC
        LIMIT ?
        """,
        (*allowed, target * 25),
    ).fetchall()
    conn.close()

    seen: set[tuple[str, str, str]] = set()
    selected: list[dict] = []
    skipped: list[dict] = []
    prepared = 0
    failed_prepare = 0
    dry_parsed = 0
    assisted = 0

    from engine.apply.browser_apply import dry_parse_application
    from engine.campaign_runner import _is_auto_apply_target

    wave_started = time.time()
    max_seconds = 180
    max_examined = max(target * 25, target)
    examined = 0
    for row in rows:
        if len(selected) >= target:
            break
        if examined >= max_examined or (time.time() - wave_started) > max_seconds:
            break
        examined += 1
        job = dict(row)
        dedupe_key = (
            (job.get("company") or "").strip().lower(),
            (job.get("title") or "").strip().lower(),
            (job.get("location") or "").strip().lower(),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        if not _is_auto_apply_target(job, auto_submit=True):
            skipped.append({
                "job_id": job["id"],
                "company": job.get("company", ""),
                "title": job.get("title", ""),
                "portal": job.get("portal", ""),
                "reason": "not a technical/data auto-apply target",
            })
            continue

        artifacts = {}
        allow_backfill = int(req.min_viability) < 85
        pre_viability = automation_viability(job, allow_backfill=allow_backfill)
        if not pre_viability["eligible"] or pre_viability["score"] < req.min_viability:
            skipped.append({
                "job_id": job["id"],
                "company": job.get("company", ""),
                "title": job.get("title", ""),
                "portal": job.get("portal", ""),
                "viability_score": pre_viability["score"],
                "reason": pre_viability["reason"] or "; ".join(pre_viability["notes"][:3]),
            })
            continue

        if req.prepare_artifacts:
            try:
                prep = _generate_missing_artifacts_for_job(job)
                artifacts = prep.get("artifacts", {})
                if prep.get("ok"):
                    prepared += 1
                else:
                    failed_prepare += 1
                    skipped.append({"job_id": job["id"], "company": job.get("company", ""), "title": job.get("title", ""), "portal": job.get("portal", ""), "reason": f"artifact_missing:{prep.get('missing', [])}"})
                    continue
            except Exception as exc:
                failed_prepare += 1
                skipped.append({"job_id": job["id"], "company": job.get("company", ""), "title": job.get("title", ""), "portal": job.get("portal", ""), "reason": f"artifact_error:{exc}"})
                continue

        dry = None
        if req.dry_parse:
            dry = dry_parse_application(job, headless=True)
            dry_parsed += 1
            if dry.get("blocker"):
                status = assisted_status_for_blocker(dry.get("blocker"))
                conn = get_conn()
                conn.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", (status, now_iso(), job["id"]))
                update_domain_memory(conn, job, status, dry.get("reason") or dry.get("blocker"))
                conn.commit()
                conn.close()
                assisted += 1
                skipped.append({"job_id": job["id"], "company": job.get("company", ""), "title": job.get("title", ""), "portal": job.get("portal", ""), "reason": dry.get("blocker")})
                continue

        viability = automation_viability(job, artifacts=artifacts, dry_parse=dry, allow_backfill=allow_backfill)
        conn = get_conn()
        _persist_job_policy(conn, job["id"], viability)
        conn.commit()
        conn.close()

        if viability["eligible"] and viability["score"] >= req.min_viability:
            selected.append(job)
        else:
            skipped.append({
                "job_id": job["id"],
                "company": job.get("company", ""),
                "title": job.get("title", ""),
                "portal": job.get("portal", ""),
                "viability_score": viability["score"],
                "reason": viability["reason"] or "; ".join(viability["notes"][:3]),
            })

    queue_result = _enqueue_auto_apply_ids([job["id"] for job in selected], skipped) if selected else {"ok": False, "queued": 0, "skipped": skipped}
    report = {
        "ok": bool(selected),
        "target": target,
        "examined": examined,
        "duration_sec": round(time.time() - wave_started, 1),
        "selected": len(selected),
        "queued": queue_result.get("queued", 0),
        "prepared": prepared,
        "failed_prepare": failed_prepare,
        "dry_parsed": dry_parsed,
        "assisted": assisted,
        "skipped": skipped,
    }
    report["summary_path"] = _write_application_run_summary(report)
    return report


# ── POST /api/auto-apply/stop ─────────────────────────────────────────────────
@app.post("/api/auto-apply/stop")
def stop_auto_apply():
    with _auto_lock:
        _auto_state["stop_requested"] = True
        _auto_state["captcha_paused"] = False
    # Drain the queue
    while not _auto_q.empty():
        try:
            _auto_q.get_nowait()
            _auto_q.task_done()
        except queue.Empty:
            break
    _auto_log("Stop requested — draining queue.")
    return {"ok": True}


@app.post("/api/auto-apply/resume-assisted")
def resume_assisted_auto_apply():
    from engine.apply.browser_apply import get_session, close_session

    with _auto_lock:
        session_id = _auto_state.get("assisted_session_id", "")
        job_id = _auto_state.get("assisted_job_id", "")
        application_id = _auto_state.get("assisted_application_id", "")
        blocker = _auto_state.get("assisted_blocker", "")

    if not session_id or not job_id:
        return {"ok": False, "error": "No assisted browser session is waiting."}

    session = get_session(session_id)
    if not session:
        return {"ok": False, "error": "Assisted browser session is no longer open. Restart the job."}

    _auto_log(f"Resuming assisted job after human step: {blocker or 'manual'}")
    result = session.resume_after_human()
    now = now_iso()

    conn = get_conn()
    job_row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    job = dict(job_row) if job_row else {"id": job_id}

    if result.get("ok"):
        if application_id:
            conn.execute(
                """
                UPDATE applications
                SET stage='submitted', submitted_at=?, final_confirmation_given=1,
                    failure_reason='', updated_at=?
                WHERE id=?
                """,
                (now, now, application_id),
            )
        else:
            application_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO applications
                    (id, job_id, stage, apply_mode, review_required, final_confirmation_given, notes, created_at, updated_at)
                VALUES (?,?,?,?,0,1,?,?,?)
                """,
                (application_id, job_id, "submitted", "AUTO_APPLY", "Submitted after human-assisted verification.", now, now),
            )
        conn.execute("UPDATE jobs SET status='applied', updated_at=? WHERE id=?", (now, job_id))
        update_domain_memory(conn, job, "applied", "submitted_after_human")
        conn.commit()
        conn.close()
        close_session(session_id)
        with _auto_lock:
            _auto_state["done"] += 1
            _auto_state["captcha_paused"] = False
            _auto_state["assisted_session_id"] = ""
            _auto_state["assisted_job_id"] = ""
            _auto_state["assisted_application_id"] = ""
            _auto_state["assisted_blocker"] = ""
        _auto_log("Applied after human-assisted step.")
        return {"ok": True, "result": result}

    new_blocker = _blocker_from_result(result)
    status = assisted_status_for_blocker(new_blocker)
    if application_id:
        conn.execute(
            "UPDATE applications SET stage=?, failure_reason=?, updated_at=? WHERE id=?",
            (status, result.get("error", ""), now, application_id),
        )
    conn.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", (status, now, job_id))
    update_domain_memory(conn, job, status, result.get("error", ""))
    conn.commit()
    conn.close()
    with _auto_lock:
        _auto_state["captcha_paused"] = new_blocker == "captcha"
        _auto_state["assisted_blocker"] = new_blocker
    _auto_log(f"Still needs assistance: {new_blocker} — {result.get('error', '')}")
    return {"ok": False, "result": result}


# ── GET /api/auto-apply/status ────────────────────────────────────────────────
@app.get("/api/auto-apply/status")
def auto_apply_status_stream():
    import json as _json

    def _generate():
        # Send current state snapshot immediately
        with _auto_lock:
            snap = {k: v for k, v in _auto_state.items() if k != "log_q"}
        yield f"data: {_json.dumps({'type': 'state', **snap})}\n\n"

        # Stream log lines
        while True:
            try:
                line = _auto_state["log_q"].get(timeout=1)
                yield f"data: {_json.dumps({'type': 'log', 'text': line})}\n\n"
            except queue.Empty:
                with _auto_lock:
                    snap = {k: v for k, v in _auto_state.items() if k != "log_q"}
                yield f"data: {_json.dumps({'type': 'state', **snap})}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")


def _write_application_run_summary(summary: dict | None = None) -> str:
    summary = summary or {}
    conn = get_conn()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = conn.execute(
        """
        SELECT a.*, j.company, j.title, j.portal, j.url
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE substr(a.created_at, 1, 10) >= ?
        ORDER BY a.created_at DESC
        """,
        (today,),
    ).fetchall()
    domain_rows = conn.execute("SELECT * FROM domain_memory ORDER BY updated_at DESC LIMIT 20").fetchall()
    conn.close()

    submitted = [dict(r) for r in rows if r["stage"] == "submitted"]
    assisted = [dict(r) for r in rows if (r["stage"] or "").startswith("assisted")]
    failed = [dict(r) for r in rows if (r["stage"] or "").startswith("failed")]
    confirmations = [r for r in submitted if r.get("confirmation_text") or r.get("final_confirmation_given")]
    failure_counts: dict[str, int] = {}
    unknown_questions: list[str] = []
    for row in assisted + failed:
        reason = (row.get("failure_reason") or "").strip()
        if reason:
            failure_counts[reason[:160]] = failure_counts.get(reason[:160], 0) + 1
            if "unknown required" in reason.lower():
                unknown_questions.append(reason[:220])

    lines = [
        "# Application Run Summary",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- Examined count: {summary.get('examined', 'n/a')}",
        f"- Prepared count: {summary.get('prepared', 'n/a')}",
        f"- Submitted count: {len(submitted)}",
        f"- Assisted/manual count: {len(assisted)}",
        f"- Failed count: {len(failed)}",
        f"- Confirmation count: {len(confirmations)}",
        "",
        "## Successfully Submitted Jobs",
    ]
    if submitted:
        for row in submitted[:100]:
            lines.append(f"- {row['company']} | {row['title']} | {row['portal']} | {row['url']}")
    else:
        lines.append("- None confirmed yet.")
    lines += ["", "## Top Blocker Domains"]
    for row in domain_rows[:10]:
        d = dict(row)
        lines.append(f"- {d.get('domain')} | {d.get('last_status')} | assisted={d.get('assisted_count')} captcha={d.get('captcha_count')} | {str(d.get('last_reason') or '')[:140]}")
    lines += ["", "## Top Failure / Assisted Reasons"]
    if failure_counts:
        for reason, count in sorted(failure_counts.items(), key=lambda item: item[1], reverse=True)[:10]:
            lines.append(f"- {count}x {reason}")
    else:
        lines.append("- None.")
    lines += ["", "## Unknown Required Questions"]
    if unknown_questions:
        for q in unknown_questions[:20]:
            lines.append(f"- {q}")
    else:
        lines.append("- None captured.")
    lines += [
        "",
        "## Recommendations",
        "- Run Wave 1 only until at least one portal/domain produces confirmed submissions.",
        "- Keep Workday and LinkedIn manual/assisted only.",
        "- Answer items in data/user_questions_needed.json before retrying blocked jobs.",
    ]
    path = ROOT / "logs" / "application_run_summary.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return str(path)


@app.get("/api/auto-apply/run-summary")
def auto_apply_run_summary():
    return {"ok": True, "path": _write_application_run_summary()}


@app.get("/api/user-questions-needed")
def user_questions_needed():
    path = ROOT / "data" / "user_questions_needed.json"
    if not path.exists():
        return {"ok": True, "path": str(path), "blocking_questions": [], "known_manual_topics": []}
    try:
        payload = json.loads(path.read_text())
    except Exception:
        payload = {"blocking_questions": [], "known_manual_topics": []}
    return {"ok": True, "path": str(path), **payload}


@app.get("/api/applications/export-submitted")
def export_submitted_applications():
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT a.*, j.company, j.title, j.portal, j.url
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE a.stage='submitted'
        ORDER BY a.submitted_at DESC, a.created_at DESC
        """
    ).fetchall()
    conn.close()
    out_path = ROOT / "logs" / "submitted_applications.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [dict(r) for r in rows]
    out_path.write_text(json.dumps(payload, indent=2))
    return {"ok": True, "path": str(out_path), "count": len(payload), "applications": payload[:100]}


@app.get("/api/auto-apply/analytics")
def auto_apply_analytics():
    conn = get_conn()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = conn.execute(
        """
        SELECT a.*, j.portal, j.company, j.title, j.url
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE substr(a.created_at, 1, 10) >= ?
        """,
        (today,),
    ).fetchall()
    attempted = len(rows)
    applied = sum(1 for r in rows if r["stage"] == "submitted")
    assisted = sum(1 for r in rows if (r["stage"] or "").startswith("assisted") or r["stage"] == "needs_assistance")
    failed = sum(1 for r in rows if (r["stage"] or "").startswith("failed") or r["stage"] == "failed")

    by_portal: dict[str, dict[str, int]] = {}
    failures: dict[str, int] = {}
    for row in rows:
        portal = row["portal"] or "unknown"
        by_portal.setdefault(portal, {"attempted": 0, "applied": 0, "assisted": 0, "failed": 0})
        by_portal[portal]["attempted"] += 1
        stage = row["stage"] or ""
        if stage == "submitted":
            by_portal[portal]["applied"] += 1
        elif stage.startswith("assisted") or stage == "needs_assistance":
            by_portal[portal]["assisted"] += 1
        elif stage.startswith("failed") or stage == "failed":
            by_portal[portal]["failed"] += 1
        reason = row["failure_reason"] or ""
        if reason:
            failures[reason[:120]] = failures.get(reason[:120], 0) + 1

    domain_rows = conn.execute(
        "SELECT * FROM domain_memory ORDER BY updated_at DESC LIMIT 200"
    ).fetchall()
    artifacts_generated = conn.execute(
        "SELECT COUNT(*) FROM artifacts WHERE substr(created_at, 1, 10) >= ?",
        (today,),
    ).fetchone()[0]
    skipped_workday = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE portal='workday' AND status LIKE 'assisted_%'"
    ).fetchone()[0]
    skipped_linkedin = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE portal='linkedin' OR url LIKE '%linkedin.com%'"
    ).fetchone()[0]
    conn.close()

    domain_payload = [dict(r) for r in domain_rows]
    best_domains = sorted(
        domain_payload,
        key=lambda r: (r.get("success_count") or 0, -1 * (r.get("fail_count") or 0)),
        reverse=True,
    )[:10]
    worst_domains = sorted(
        domain_payload,
        key=lambda r: ((r.get("fail_count") or 0) + (r.get("captcha_count") or 0), r.get("assisted_count") or 0),
        reverse=True,
    )[:10]

    durations = [float(r.get("avg_duration_sec") or 0) for r in domain_payload if r.get("avg_duration_sec")]
    return {
        "attempted_today": attempted,
        "applied_today": applied,
        "failed_today": failed,
        "assisted_today": assisted,
        "success_rate": round((applied / attempted) * 100, 1) if attempted else 0,
        "success_by_portal": by_portal,
        "success_by_domain": domain_payload,
        "top_failure_reasons": sorted(
            [{"reason": reason, "count": count} for reason, count in failures.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10],
        "average_apply_duration": round(sum(durations) / len(durations), 1) if durations else 0,
        "artifacts_generated": artifacts_generated,
        "skipped_workday_count": skipped_workday,
        "skipped_linkedin_count": skipped_linkedin,
        "best_domains": best_domains,
        "worst_domains": worst_domains,
    }


# ── GET /api/pdfs ─────────────────────────────────────────────────────────────
@app.get("/api/pdfs")
def get_pdfs():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM artifacts ORDER BY created_at DESC LIMIT 100").fetchall()
    conn.close()

    arts = []
    for row in rows:
        a = dict(row)
        path = Path(a.get("path", ""))
        a["exists"] = path.exists()
        a["size_kb"] = round(path.stat().st_size / 1024, 1) if path.exists() else 0
        a["name"] = path.name
        arts.append(a)

    return {"pdfs": arts, "count": len(arts)}


# ── GET /api/sources ──────────────────────────────────────────────────────────
@app.get("/api/sources")
def get_sources():
    return {
        "sources": [
            {
                "id": "greenhouse",
                "name": "Greenhouse API",
                "tier": "A",
                "description": "Official public Boards API. Structured JSON. No auth required.",
                "apply_mode": "ASSISTED_FILL",
                "polling_interval_minutes": 10,
                "enabled": True,
            },
            {
                "id": "lever",
                "name": "Lever Postings API",
                "tier": "A",
                "description": "Official public Postings API. JSON. No auth required.",
                "apply_mode": "ASSISTED_FILL",
                "polling_interval_minutes": 10,
                "enabled": True,
            },
            {
                "id": "ashby",
                "name": "Ashby Job Board API",
                "tier": "A",
                "description": "Official public job board API. JSON. No auth required.",
                "apply_mode": "ASSISTED_FILL",
                "polling_interval_minutes": 10,
                "enabled": True,
            },
            {
                "id": "github_repo",
                "name": "GitHub Internship Repo",
                "tier": "C",
                "description": "Parses Canadian-Tech-Internships markdown table. Discovery only.",
                "apply_mode": "PREP_ONLY",
                "polling_interval_minutes": 60,
                "enabled": True,
            },
            {
                "id": "workday",
                "name": "Workday",
                "tier": "B",
                "description": "Discovery/prep only by policy. Account creation and email verification make auto-submit unsafe.",
                "apply_mode": "PREP_ONLY",
                "polling_interval_minutes": 60,
                "enabled": True,
            },
            {
                "id": "amazon",
                "name": "Amazon Jobs",
                "tier": "C",
                "description": "Discovery/prep only.",
                "apply_mode": "PREP_ONLY",
                "polling_interval_minutes": 60,
                "enabled": True,
            },
            {
                "id": "microsoft",
                "name": "Microsoft Careers",
                "tier": "C",
                "description": "Discovery/prep only.",
                "apply_mode": "PREP_ONLY",
                "polling_interval_minutes": 60,
                "enabled": True,
            },
            {
                "id": "indeed",
                "name": "Indeed",
                "tier": "C",
                "description": "Manual/import only by policy. Indeed Apply is never automated.",
                "apply_mode": "PREP_ONLY",
                "polling_interval_minutes": 60,
                "enabled": False,
            },
            {
                "id": "url_import",
                "name": "URL Import",
                "tier": "A/B/C",
                "description": "Import any job by URL. Portal auto-detected. Tier assigned by portal.",
                "apply_mode": "varies",
                "polling_interval_minutes": None,
                "enabled": True,
            },
            {
                "id": "text_import",
                "name": "Text / Paste Import",
                "tier": "C",
                "description": "Paste a job description. Discovery + artifact generation only.",
                "apply_mode": "PREP_ONLY",
                "polling_interval_minutes": None,
                "enabled": True,
            },
            {
                "id": "linkedin",
                "name": "LinkedIn Jobs",
                "tier": "C",
                "description": "Discovers public LinkedIn job listings. Easy Apply and link-apply jobs. Manual apply only — no LinkedIn automation.",
                "apply_mode": "PREP_ONLY",
                "polling_interval_minutes": 60,
                "enabled": False,
                "note": LINKEDIN_DISABLED_REASON,
            },
            {
                "id": "glassdoor",
                "name": "Glassdoor Jobs",
                "tier": "C",
                "description": "Manual/import only by policy. No automated Glassdoor scraping or apply automation.",
                "apply_mode": "PREP_ONLY",
                "polling_interval_minutes": 60,
                "enabled": False,
            },
        ]
    }


# ── POST /api/sources/test ────────────────────────────────────────────────────
class SourceTestRequest(BaseModel):
    source_id: str


@app.post("/api/sources/test")
def test_source(req: SourceTestRequest):
    sid = req.source_id
    try:
        if sid == "greenhouse":
            from engine.sources.greenhouse import fetch_company_jobs
            jobs = fetch_company_jobs("shopify", "Shopify")
            return {"ok": True, "source": sid, "sample_count": len(jobs)}
        elif sid == "lever":
            from engine.sources.lever import fetch_company_jobs
            jobs = fetch_company_jobs("shopify", "Shopify")
            return {"ok": True, "source": sid, "sample_count": len(jobs)}
        elif sid == "ashby":
            from engine.sources.ashby import fetch_company_jobs
            jobs = fetch_company_jobs("cohere", "Cohere")
            return {"ok": True, "source": sid, "sample_count": len(jobs)}
        elif sid == "github_repo":
            from engine.sources.github_repo import fetch_all
            jobs = fetch_all()
            return {"ok": True, "source": sid, "sample_count": len(jobs)}
        elif sid == "linkedin":
            return {"ok": False, "source": sid, "error": LINKEDIN_DISABLED_REASON}
        else:
            return {"ok": False, "error": f"Unknown source: {sid}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── GET /api/notifications ────────────────────────────────────────────────────
@app.get("/api/notifications")
def get_notifications(limit: int = 50, unseen_only: bool = False):
    conn = get_conn()
    q = "SELECT * FROM notifications"
    if unseen_only:
        q += " WHERE seen=0"
    q += " ORDER BY created_at DESC LIMIT ?"
    rows = conn.execute(q, (limit,)).fetchall()
    conn.close()
    return {"notifications": [dict(r) for r in rows]}


@app.post("/api/notifications/mark-seen")
def mark_notifications_seen():
    conn = get_conn()
    conn.execute("UPDATE notifications SET seen=1 WHERE seen=0")
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Campaigns ────────────────────────────────────────────────────────────────
class CampaignStartRequest(BaseModel):
    target_total: int = 100
    openai_target: int = 50
    gemini_target: int = 50
    claude_target: int = 0
    min_score: float = 55
    auto_submit: bool = True
    tomorrow_target: int = 1000


def _campaign_progress(meta: dict):
    _campaign_state["meta"] = meta


def _campaign_stop_requested() -> bool:
    return _campaign_state.get("cancel_requested", False)


def _run_campaign_task(campaign_id: str):
    import traceback
    try:
        run_campaign(
            campaign_id,
            progress_callback=_campaign_progress,
            stop_requested=_campaign_stop_requested,
        )
    except Exception as exc:
        tb = traceback.format_exc()
        print(f"[campaign:{campaign_id[:8]}] FATAL: {exc}\n{tb}", flush=True)
        conn = get_conn()
        conn.execute(
            "UPDATE campaigns SET state='failed', ended_at=? WHERE id=?",
            (now_iso(), campaign_id),
        )
        insert_notification(conn, "campaign", f"Campaign failed: {exc}")
        conn.commit()
        conn.close()
    finally:
        _campaign_state["running"] = False
        _campaign_state["campaign_id"] = None
        _campaign_state["cancel_requested"] = False
        _campaign_state["meta"] = {}


@app.post("/api/campaigns/start")
def start_campaign(req: CampaignStartRequest, background_tasks: BackgroundTasks):
    with _campaign_lock:
        if _campaign_state["running"]:
            return {"ok": False, "error": "A campaign is already running"}

        if not (1 <= req.target_total <= 5000):
            raise HTTPException(status_code=400, detail="target_total must be between 1 and 5000")
        if req.openai_target < 0 or req.gemini_target < 0 or req.claude_target < 0:
            raise HTTPException(status_code=400, detail="Provider targets must be non-negative")
        if req.openai_target + req.gemini_target + req.claude_target != req.target_total:
            raise HTTPException(status_code=400, detail="Provider targets must add up to target_total")
        if req.tomorrow_target < 0:
            raise HTTPException(status_code=400, detail="tomorrow_target must be zero or greater")

        engine_mode = get_setting("ARTIFACT_ENGINE_MODE", "deterministic")
        if engine_mode == "llm":
            openai_key = get_setting("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
            gemini_key = get_setting("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
            claude_key = (
                get_setting("CLAUDE_API_KEY")
                or os.environ.get("CLAUDE_API_KEY", "")
                or os.environ.get("ANTHROPIC_API_KEY", "")
            )
            missing = []
            if req.openai_target and not openai_key:
                missing.append("OPENAI_API_KEY")
            if req.gemini_target and not gemini_key:
                missing.append("GEMINI_API_KEY")
            if req.claude_target and not claude_key:
                missing.append("CLAUDE_API_KEY")
            if missing:
                raise HTTPException(status_code=400, detail=f"Missing required keys: {', '.join(missing)}")

        campaign_id, selected_count = create_campaign(
            name=f"High-Fit Batch {req.target_total}",
            target_total=req.target_total,
            openai_target=req.openai_target,
            gemini_target=req.gemini_target,
            claude_target=req.claude_target,
            tomorrow_target=req.tomorrow_target,
            min_score=req.min_score,
            auto_submit=req.auto_submit,
        )
        _campaign_state["running"] = True
        _campaign_state["campaign_id"] = campaign_id
        _campaign_state["cancel_requested"] = False
        _campaign_state["meta"] = {
            "selected_count": selected_count,
            "target_total": req.target_total,
            "openai_target": req.openai_target,
            "gemini_target": req.gemini_target,
            "claude_target": req.claude_target,
        }
        # Run campaigns in a dedicated OS thread so Playwright's sync API
        # is not invoked from FastAPI's asyncio background-task context.
        threading.Thread(
            target=_run_campaign_task,
            args=(campaign_id,),
            daemon=True,
        ).start()
        return {"ok": True, "campaign_id": campaign_id, "selected_count": selected_count}


@app.post("/api/campaigns/stop")
def stop_campaign():
    if not _campaign_state["running"]:
        return {"ok": False, "error": "No campaign is running"}
    _campaign_state["cancel_requested"] = True
    return {"ok": True}


@app.get("/api/campaigns/latest")
def get_latest_campaign():
    conn = get_conn()
    campaign = conn.execute(
        "SELECT * FROM campaigns ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    if not campaign:
        conn.close()
        return {"campaign": None, "rows": [], "running": _campaign_state["running"], "meta": _campaign_state["meta"]}

    rows = conn.execute(
        """
        SELECT cr.*, j.title, j.company, j.location, j.score, j.fit_band, j.support_tier, j.portal, j.url
        FROM campaign_rows cr
        JOIN jobs j ON j.id = cr.job_id
        WHERE cr.campaign_id=?
        ORDER BY cr.rank ASC
        """,
        (campaign["id"],),
    ).fetchall()
    conn.close()

    payload = []
    for row in rows:
        item = dict(row)
        try:
            item["details"] = json.loads(item.get("details") or "{}")
        except Exception:
            item["details"] = {}
        payload.append(item)

    return {
        "campaign": dict(campaign),
        "rows": payload,
        "running": _campaign_state["running"],
        "meta": _campaign_state["meta"],
    }


@app.get("/api/campaigns/{campaign_id}")
def get_campaign(campaign_id: str):
    conn = get_conn()
    campaign = conn.execute(
        "SELECT * FROM campaigns WHERE id=?", (campaign_id,)
    ).fetchone()
    if not campaign:
        conn.close()
        raise HTTPException(status_code=404, detail="Campaign not found")

    rows = conn.execute(
        """
        SELECT cr.*, j.title, j.company, j.location, j.score, j.fit_band, j.support_tier, j.portal, j.url
        FROM campaign_rows cr
        JOIN jobs j ON j.id = cr.job_id
        WHERE cr.campaign_id=?
        ORDER BY cr.rank ASC
        """,
        (campaign_id,),
    ).fetchall()
    conn.close()

    payload = []
    for row in rows:
        item = dict(row)
        try:
            item["details"] = json.loads(item.get("details") or "{}")
        except Exception:
            item["details"] = {}
        payload.append(item)

    return {
        "campaign": dict(campaign),
        "rows": payload,
        "running": _campaign_state["campaign_id"] == campaign_id and _campaign_state["running"],
        "meta": _campaign_state["meta"] if _campaign_state["campaign_id"] == campaign_id else {},
    }


# ── GET/POST /api/settings ────────────────────────────────────────────────────
ALLOWED_SETTINGS = {
    "CLAUDE_API_KEY", "CLAUDE_MODEL", "DAILY_CAP", "DRY_RUN_DEFAULT",
    "TARGET_LOCATIONS", "TARGET_ROLES", "NEGATIVE_KEYWORDS",
    "MIN_SCORE", "BROWSER_HEADLESS", "ARTIFACTS_DIR",
    "ARTIFACT_ENGINE_MODE", "PROFILE_QA_JSON",
    "OPENAI_API_KEY", "GEMINI_API_KEY",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
}


@app.get("/api/settings")
def get_settings_endpoint():
    settings = all_settings()
    # Mask secrets before sending to the browser
    masked = {}
    for k, v in settings.items():
        if "KEY" in k or "PASSWORD" in k or "TOKEN" in k or "SECRET" in k:
            masked[k] = "*" * 8 if v else ""
        else:
            masked[k] = v
    return {"settings": masked, "linkedin_disabled": LINKEDIN_DISABLED}


class SettingUpdate(BaseModel):
    key: str
    value: str


@app.post("/api/settings")
def update_setting(req: SettingUpdate):
    if req.key not in ALLOWED_SETTINGS:
        raise HTTPException(status_code=400, detail=f"Unknown setting key: {req.key}. Allowed: {sorted(ALLOWED_SETTINGS)}")
    # Mask secrets
    if ("KEY" in req.key or "TOKEN" in req.key or "SECRET" in req.key) and req.value.startswith("*"):
        raise HTTPException(status_code=400, detail="Do not submit masked values.")
    if req.key == "DAILY_CAP":
        try:
            v = int(req.value)
            if not (1 <= v <= 5000):
                raise HTTPException(status_code=400, detail="DAILY_CAP must be 1–5000")
        except ValueError:
            raise HTTPException(status_code=400, detail="DAILY_CAP must be an integer")
    if req.key == "ARTIFACT_ENGINE_MODE":
        if req.value not in {"deterministic", "llm"}:
            raise HTTPException(status_code=400, detail="ARTIFACT_ENGINE_MODE must be 'deterministic' or 'llm'")
    set_setting(req.key, req.value)
    return {"ok": True, "key": req.key}


# ── Profile knowledge ────────────────────────────────────────────────────────
@app.get("/api/profile/knowledge")
def get_profile_knowledge():
    return {
        "engine_mode": get_setting("ARTIFACT_ENGINE_MODE", "deterministic"),
        "blueprints": list_blueprints(),
        "questions": get_questionnaire_payload(),
        "template_library": list_template_library(),
    }


class ProfileAnswersUpdate(BaseModel):
    answers: dict[str, str]


@app.post("/api/profile/answers")
def update_profile_answers(req: ProfileAnswersUpdate):
    saved = save_profile_answers(req.answers or {})
    return {"ok": True, "saved_count": len([v for v in saved.values() if v.strip()])}


@app.post("/api/profile/templates/build")
def build_profile_templates():
    built = build_template_library()
    return {"ok": True, "count": len(built), "templates": built}


# ── POST /api/discovery/trigger ───────────────────────────────────────────────
class DiscoveryRequest(BaseModel):
    sources: Optional[list[str]] = None  # None = all


@app.post("/api/discovery/trigger")
def trigger_discovery(req: DiscoveryRequest, background_tasks: BackgroundTasks):
    if _run_state["running"]:
        return {"ok": False, "error": "A run is already in progress"}
    raw_sources = req.sources or DEFAULT_DISCOVERY_SOURCES
    sources = [source for source in raw_sources if source not in BLOCKED_AUTOMATED_DISCOVERY_SOURCES]
    if not sources:
        return {"ok": False, "error": "Requested sources are manual/import-only by policy. Use URL or text import instead."}
    run_id = str(uuid.uuid4())
    _run_state["running"] = True
    _run_state["run_id"] = run_id
    _run_state["meta"] = {"sources": sources, "started_at": now_iso()}
    background_tasks.add_task(_run_discovery, run_id, sources)
    return {"ok": True, "run_id": run_id, "sources": sources}


def _run_discovery(run_id: str, sources: list[str]):
    conn = get_conn()
    counters = {"new": 0, "updated": 0, "total": 0, "errors": 0}

    conn.execute(
        "INSERT INTO runs (id, mode, state, source_scope, started_at, counters) VALUES (?,?,?,?,?,?)",
        (run_id, "discovery", "running", json.dumps(sources), now_iso(), json.dumps(counters)),
    )
    conn.commit()

    def log(msg):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        try:
            _run_state["log_q"].put_nowait(entry)
        except queue.Full:
            pass
        print(f"[discovery] {msg}")

    log(f"Discovery started. Sources: {sources}")

    all_jobs = []
    _linkedin_new: list[dict] = []
    _glassdoor_new: list[dict] = []
    _github_new: list[dict] = []

    for source in sources:
        log(f"Fetching {source}...")
        try:
            if source == "greenhouse":
                from engine.sources.greenhouse import fetch_all
                jobs = fetch_all()
            elif source == "lever":
                from engine.sources.lever import fetch_all
                jobs = fetch_all()
            elif source == "ashby":
                from engine.sources.ashby import fetch_all
                jobs = fetch_all()
            elif source == "github_repo":
                from engine.sources.github_repo import fetch_all
                jobs = fetch_all()
                _github_new = jobs
            elif source == "linkedin":
                log(LINKEDIN_DISABLED_REASON)
                continue
            elif source == "glassdoor":
                from engine.sources.glassdoor import fetch_all
                jobs = fetch_all()
                _glassdoor_new = jobs
            elif source == "workday":
                from engine.sources.workday import fetch_all
                jobs = fetch_all()
            elif source == "amazon":
                from engine.sources.amazon import fetch_all
                jobs = fetch_all()
            elif source == "microsoft":
                from engine.sources.microsoft import fetch_all
                jobs = fetch_all()
            elif source == "indeed":
                from engine.sources.indeed import fetch_all
                jobs = fetch_all()
            else:
                log(f"Unknown source: {source}")
                continue
            log(f"{source}: fetched {len(jobs)} jobs")
            all_jobs.extend(jobs)
            counters["total"] += len(jobs)
        except Exception as e:
            log(f"ERROR fetching {source}: {e}")
            counters["errors"] += 1

    # Filter by score
    min_score = float(get_setting("MIN_SCORE", "0"))
    log(f"Filtering {len(all_jobs)} jobs (min_score={min_score})...")

    saved = 0
    for job in all_jobs:
        if job.get("score", 0) < min_score:
            continue
        try:
            existing = conn.execute("SELECT id FROM jobs WHERE id=?", (job["id"],)).fetchone()
            upsert_job(conn, job)
            if existing:
                counters["updated"] += 1
            else:
                counters["new"] += 1
            saved += 1
        except Exception as e:
            log(f"DB error for job {job.get('id')}: {e}")

    conn.commit()
    now = now_iso()
    conn.execute(
        "UPDATE runs SET state='done', ended_at=?, counters=? WHERE id=?",
        (now, json.dumps(counters), run_id),
    )
    conn.commit()
    conn.close()

    log(f"Discovery complete. New: {counters['new']}, Updated: {counters['updated']}, Errors: {counters['errors']}")

    # Telegram notifications for new source batches
    try:
        from engine.notifier import (
            notify_discovery_complete,
            notify_linkedin_jobs_found,
            notify_glassdoor_jobs_found,
            notify_github_jobs_found,
        )
        notify_discovery_complete(counters["new"], counters["updated"], sources, counters["errors"])
        if _linkedin_new:
            notify_linkedin_jobs_found(_linkedin_new)
        if _glassdoor_new:
            notify_glassdoor_jobs_found(_glassdoor_new)
        if _github_new:
            notify_github_jobs_found(_github_new)
    except Exception as _ne:
        print(f"[notify] discovery complete error: {_ne}")

    _run_state["running"] = False
    _run_state["meta"] = {}


# ── POST /api/discovery/import-url ───────────────────────────────────────────
class ImportURLRequest(BaseModel):
    url: str


@app.post("/api/discovery/import-url")
def import_url(req: ImportURLRequest):
    from engine.sources.url_import import import_from_url
    result = import_from_url(req.url)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result.get("reason", "Import failed"))
    conn = get_conn()
    upsert_job(conn, result)
    conn.commit()
    conn.close()
    return {"ok": True, "job": result}


# ── POST /api/discovery/import-text ──────────────────────────────────────────
class ImportTextRequest(BaseModel):
    text: str
    title: Optional[str] = ""
    company: Optional[str] = ""


@app.post("/api/discovery/import-text")
def import_text(req: ImportTextRequest):
    from engine.sources.url_import import import_from_text
    job = import_from_text(req.text, req.title or "", req.company or "")
    conn = get_conn()
    upsert_job(conn, job)
    conn.commit()
    conn.close()
    return {"ok": True, "job": job}


# ── POST /api/run/start (legacy compat) ───────────────────────────────────────
class RunStartRequest(BaseModel):
    source: Optional[str] = "github"
    query: Optional[str] = ""
    category: Optional[str] = "tech"
    limit: Optional[int] = 20
    dry_run: Optional[bool] = True
    headless: Optional[bool] = True


@app.post("/api/run/start")
def run_start(req: RunStartRequest, background_tasks: BackgroundTasks):
    if _run_state["running"]:
        return {"ok": False, "error": "A run is already in progress"}
    sources = [req.source] if req.source != "all" else DEFAULT_DISCOVERY_SOURCES
    return trigger_discovery(DiscoveryRequest(sources=sources), background_tasks)


@app.post("/api/run/stop")
def run_stop():
    _run_state["running"] = False
    return {"ok": True}


@app.get("/api/run/status")
def run_status():
    return {
        "running": _run_state["running"],
        "run_id": _run_state.get("run_id"),
        "meta": _run_state.get("meta", {}),
    }


# ── GET /api/run/logs (SSE) ───────────────────────────────────────────────────
@app.get("/api/run/logs")
def run_logs():
    def event_stream():
        while True:
            try:
                line = _run_state["log_q"].get(timeout=25)
                yield f"data: {json.dumps({'type': 'log', 'text': line})}\n\n"
            except queue.Empty:
                if not _run_state["running"]:
                    yield f"data: {json.dumps({'type': 'exit', 'code': 0})}\n\n"
                    break
                yield ": keepalive\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    try:
        conn = get_conn()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "linkedin_disabled": LINKEDIN_DISABLED,
        "version": "2.0.0",
    }


# ── GET /api/applications/memory ─────────────────────────────────────────────
@app.get("/api/applications/memory")
def get_application_memory(limit: int = 500):
    """Return all stored application memory records — what was sent to each company."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT am.*, j.url, j.score, j.fit_band, j.portal
            FROM application_memory am
            LEFT JOIN jobs j ON j.id = am.job_id
            ORDER BY am.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    except Exception:
        # Table may not exist on older DBs — bootstrap will fix on next restart
        rows = []
    conn.close()
    return {"applications": [dict(r) for r in rows], "total": len(rows)}


# ─────────────────────────────────────────────────────────────────────────────
# BATCH SEMI-AUTO FILL  (4.2 flow — fill tabs, leave open for review)
# ─────────────────────────────────────────────────────────────────────────────

class BatchFillRequest(BaseModel):
    job_ids: list[str]
    category: Optional[str] = "tech"
    headless: Optional[bool] = False    # False = visible Chrome windows for review
    max_jobs: Optional[int] = 20


@app.post("/api/batch-fill/start")
def batch_fill_start(req: BatchFillRequest, background_tasks: BackgroundTasks):
    """
    4.2 flow: for up to 20 selected jobs, open Chrome tabs, generate tailored
    resume + cover letter, fill every form field, and LEAVE the tabs open for
    the user to review and click Submit themselves.
    """
    job_ids = list(dict.fromkeys(req.job_ids))[: req.max_jobs]
    if not job_ids:
        return {"ok": False, "error": "No job IDs provided"}

    conn = get_conn()
    placeholders = ",".join("?" * len(job_ids))
    rows = conn.execute(
        f"SELECT * FROM jobs WHERE id IN ({placeholders})", job_ids
    ).fetchall()
    conn.close()
    jobs_by_id = {row["id"]: dict(row) for row in rows}
    missing = [jid for jid in job_ids if jid not in jobs_by_id]

    results: list[dict] = []

    def _run_batch():
        from engine.artifacts.local_engine import build_local_artifacts
        from engine.apply.browser_apply import BrowserSession
        from engine.artifacts.generator import build_pdf
        import tempfile, os

        for job_id in job_ids:
            job = jobs_by_id.get(job_id)
            if not job:
                results.append({"job_id": job_id, "status": "not_found"})
                continue
            try:
                category = req.category or "tech"
                artifacts = build_local_artifacts({**job, "category": category})

                resume_md   = artifacts.get("resume_md", "")
                cover_letter = artifacts.get("cover_letter", "")
                ats_score   = artifacts.get("ats_score", 0)

                # Write temp PDFs
                tmp_dir = Path(tempfile.mkdtemp(prefix="batchfill_"))
                company_slug = "".join(c for c in (job.get("company") or "co") if c.isalnum())
                resume_pdf_path  = tmp_dir / f"{company_slug}_resume.pdf"
                cover_pdf_path   = tmp_dir / f"{company_slug}_cover.pdf"

                build_pdf(resume_md,   str(resume_pdf_path),  mode="resume")
                build_pdf(cover_letter, str(cover_pdf_path),  mode="cover")

                answer_pack = artifacts.get("answer_pack", {})
                answer_pack["cover_letter"] = cover_letter

                # Open browser tab, fill form, leave open
                session = BrowserSession(
                    job=job,
                    resume_pdf_path=str(resume_pdf_path),
                    cover_pdf_path=str(cover_pdf_path),
                    answer_pack=answer_pack,
                    headless=req.headless,
                    review_mode=True,   # stays open after fill
                )
                session_id = session.start()
                fill_result = session.fill_all_fields_auto()

                results.append({
                    "job_id":     job_id,
                    "company":    job.get("company", ""),
                    "title":      job.get("title", ""),
                    "url":        job.get("url", ""),
                    "status":     "filled" if fill_result.get("ok") else "fill_error",
                    "session_id": session_id,
                    "ats_score":  ats_score,
                    "blocker":    fill_result.get("blocker"),
                })
                _auto_log(f"[batch-fill] {job.get('company')} — filled (ATS {ats_score}%)")

            except Exception as exc:
                results.append({
                    "job_id": job_id,
                    "company": (job or {}).get("company", ""),
                    "status": "error",
                    "error": str(exc),
                })
                _auto_log(f"[batch-fill] ERROR {job_id}: {exc}")

    background_tasks.add_task(_run_batch)
    return {
        "ok": True,
        "queued": len(job_ids),
        "missing": missing,
        "message": (
            f"{len(job_ids)} job(s) queued for batch fill. "
            "Chrome tabs will open with all forms pre-filled — review and click Submit on each one."
        ),
    }


@app.get("/api/batch-fill/results")
def batch_fill_results():
    """Return current status of the batch fill operation."""
    return {"results": _batch_fill_results}


_batch_fill_results: list[dict] = []


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL NOTIFICATION on submission
# ─────────────────────────────────────────────────────────────────────────────

_CONFIRMATION_EMAIL = "moyojogunjobi@gmail.com"


def _send_submission_email(job: dict, artifacts: dict | None = None) -> bool:
    """Send a confirmation email to moyojogunjobi@gmail.com when an application is submitted."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    company = job.get("company", "Unknown Company")
    title   = job.get("title", "Unknown Role")
    url     = job.get("url", "")
    ats     = (artifacts or {}).get("ats_score", "—")

    subject = f"✅ Applied: {title} at {company}"
    body = f"""Application submitted successfully.

Role:    {title}
Company: {company}
URL:     {url}
ATS Score: {ats}%
Time:    {now_iso()}

—
Job Applier Bot
"""
    try:
        # Use SMTP from settings if configured; otherwise log and skip
        smtp_host = _get_setting_safe("SMTP_HOST", "")
        smtp_user = _get_setting_safe("SMTP_USER", "")
        smtp_pass = _get_setting_safe("SMTP_PASS", "")

        if not smtp_host or not smtp_user:
            # Fallback: log to backend log
            _auto_log(f"[email] ✅ SUBMITTED: {title} at {company} — email not sent (SMTP not configured)")
            return False

        msg = MIMEMultipart()
        msg["From"]    = smtp_user
        msg["To"]      = _CONFIRMATION_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL(smtp_host, 465) as s:
            s.login(smtp_user, smtp_pass)
            s.send_message(msg)

        _auto_log(f"[email] ✅ Confirmation sent for {title} at {company}")
        return True

    except Exception as exc:
        _auto_log(f"[email] ⚠️  Failed to send confirmation for {company}: {exc}")
        return False


def _get_setting_safe(key: str, default: str = "") -> str:
    try:
        from storage.db import get_setting
        return get_setting(key, default)
    except Exception:
        import os
        return os.environ.get(key, default)


# Patch submission handler to send email
_original_submit_handlers: list = []


@app.post("/api/notify/submitted")
def notify_submitted_manual(body: dict):
    """
    Called by the frontend when the user manually clicks Submit on a filled tab.
    Logs the submission and sends a confirmation email.
    """
    job_id  = body.get("job_id", "")
    company = body.get("company", "")
    title   = body.get("title", "")
    url     = body.get("url", "")

    conn = get_conn()
    conn.execute(
        "UPDATE jobs SET status='submitted', updated_at=? WHERE id=?",
        (now_iso(), job_id),
    )
    conn.commit()
    conn.close()

    _send_submission_email({"company": company, "title": title, "url": url})
    _auto_log(f"[manual-submit] ✅ {title} at {company}")
    return {"ok": True}


@app.post("/api/mass-apply/start")
def mass_apply_start(body: dict = {}):
    """
    ONE-CLICK MASS APPLY.
    Runs the full pipeline: discover → score → select → prepare artifacts → auto-apply.
    Supports Greenhouse, Lever, Ashby, Workday, Amazon, Microsoft, Simplify, Google Jobs,
    LinkedIn Easy Apply (if creds set), Indeed Easy Apply (if creds set).

    Body params (all optional):
      target       - number of jobs to apply to (default 30, max 100)
      min_score    - minimum viability score (default 50)
      auto_submit  - whether to actually submit or just prepare (default true)
      discover     - number of jobs to discover/scrape first (default 500)
      sources      - list of sources to use (default: all)
    """
    with _campaign_lock:
        if _campaign_state.get("running"):
            return {"ok": False, "error": "A campaign is already running. Stop it first."}

    target = min(int(body.get("target", 30)), 100)
    min_score = float(body.get("min_score", 50))
    auto_submit = bool(body.get("auto_submit", True))
    discover = int(body.get("discover", 500))

    def _run():
        with _campaign_lock:
            _campaign_state["running"] = True
            _campaign_state["cancel_requested"] = False

        try:
            from engine.campaign_runner import run_coop_emergency
            result = run_coop_emergency(
                discover=discover,
                prepare=target,
                batch_size=min(target, 50),
            )
            _campaign_state["last_result"] = result
            print(f"[mass-apply] Done: {result}", flush=True)
        except Exception as exc:
            _campaign_state["last_error"] = str(exc)
            print(f"[mass-apply] Error: {exc}", flush=True)
        finally:
            with _campaign_lock:
                _campaign_state["running"] = False

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return {
        "ok": True,
        "message": f"Mass apply started — targeting {target} jobs. Check /api/mass-apply/status for progress.",
        "target": target,
        "auto_submit": auto_submit,
    }


@app.get("/api/mass-apply/status")
def mass_apply_status():
    """Check the status of a running or completed mass apply."""
    running = _campaign_state.get("running", False)
    last_result = _campaign_state.get("last_result", {})
    last_error = _campaign_state.get("last_error", "")
    try:
        conn = get_conn()
        stats = conn.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status='applied') AS submitted,
                COUNT(*) FILTER (WHERE status='prepared') AS prepared,
                COUNT(*) FILTER (WHERE status='DISCOVERED') AS discovered,
                COUNT(*) AS total
            FROM jobs
            WHERE updated_at >= datetime('now', '-24 hours')
        """).fetchone()
        conn.close()
        recent = dict(stats) if stats else {}
    except Exception:
        recent = {}
    return {
        "running": running,
        "recent_24h": recent,
        "last_result": last_result,
        "last_error": last_error,
    }


@app.post("/api/mass-apply/stop")
def mass_apply_stop():
    """Stop a running mass apply."""
    with _campaign_lock:
        _campaign_state["cancel_requested"] = True
    return {"ok": True, "message": "Stop requested."}


@app.post("/api/email/check")
def trigger_email_check(body: dict = {}):
    """Check moyosorejobi@gmail.com for application confirmations, interviews, rejections."""
    try:
        from engine.email_monitor import run_check
        days = body.get("days", 3)
        result = run_check(since_days=days)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/email/events")
def get_email_events(limit: int = 50):
    """Return recent classified email events (confirmations, interviews, rejections)."""
    try:
        from engine.email_monitor import get_recent_events
        return {"events": get_recent_events(limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/email/interviews")
def get_interview_invites():
    """Return emails classified as interview invites."""
    try:
        from engine.email_monitor import get_recent_events
        events = get_recent_events(limit=200)
        interviews = [e for e in events if e.get("classification") == "interview"]
        return {"interviews": interviews, "count": len(interviews)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/openclaw/assist")
def openclaw_assist(body: dict):
    """
    Manually request OpenClaw assistance for a specific job application.
    Body: {job_id, blocker, message}
    """
    try:
        job_id = body.get("job_id", "")
        blocker = body.get("blocker", "manual_request")
        conn = get_conn()
        job_row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        conn.close()
        if not job_row:
            raise HTTPException(status_code=404, detail="Job not found")
        job = dict(job_row)
        from engine.campaign_runner import _try_openclaw_assist
        _try_openclaw_assist(job, blocker, "", "")
        return {"ok": True, "message": f"OpenClaw assist requested for {job.get('title','')} @ {job.get('company','')}"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.server:app", host="0.0.0.0", port=7700, reload=False)
