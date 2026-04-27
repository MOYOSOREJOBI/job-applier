"""
Batch campaign runner for high-fit job applications.
"""
import argparse
import csv
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from engine.apply.domain_memory import get_domain_memory, update_domain_memory
from engine.apply.portal_policy import AUTO_PORTALS, assisted_status_for_blocker, calculate_viability, should_auto_queue
from engine.apply.browser_apply import close_session, create_session, get_session
from engine.apply.submit_policy import (
    ASSISTED_REVIEW,
    MANUAL_ONLY,
    SAFE_AUTO_SUBMIT,
    can_submit_automatically,
    status_for_policy_decision,
)
from engine.artifacts.generator import generate_artifacts
from engine.notifier import (
    notify_campaign_assistance,
    notify_campaign_done,
    notify_campaign_started,
)
from engine.scoring.scorer import score_job
from storage.db import bootstrap
from storage.db import get_conn

BASE_DIR = Path(__file__).parent.parent
STAGED_DIR = BASE_DIR / "artifacts" / "staged"
APPLICATIONS_DIR = BASE_DIR / "applications"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)

ProgressCallback = Optional[Callable[[dict], None]]
StopCallback = Optional[Callable[[], bool]]

COOP_DISCOVERY_SOURCES = [
    "greenhouse", "lever", "ashby", "workday", "amazon", "microsoft",
    "github_repo", "simplify", "google_jobs", "linkedin", "indeed", "glassdoor",
]
PROOF_COLUMNS = [
    "date",
    "company",
    "title",
    "location",
    "portal",
    "job_url",
    "score",
    "mode",
    "status",
    "submit_time",
    "block_reason",
    "resume_path",
    "cover_letter_path",
    "answer_pack_path",
    "screenshot_path",
    "notes",
]

AUTO_APPLY_COMPANY_BLOCKLIST: set[str] = {
    # Palantir: image CAPTCHA appears during Lever form interaction (not detectable as reCAPTCHA)
    "palantir",
    # Mistral's Lever forms present hCaptcha at submit time.
    "mistral ai",
}

EXCLUDED_TITLE_TERMS = [
    "senior",
    "staff",
    "lead",
    "principal",
    "manager",
    "director",
    "architect",
    "software engineer 3",
    "product designer",
    "sales engineer",
    "field sales",
    "mid-market sales",
    "public sector enterprise core",
    "phd",
    "physician",
    "nurse",
    "lawyer",
    "counsel",
    "legal",
    "recruiter",
    "social media",
    "marketing",
    "product marketing",
    "communications",
    "enablement",
    "content operations",
    "supply planning",
    "manufacturing design",
    "sales",
    "account executive",
    "customer success",
    "people operations",
    "hr ",
    "human resources",
]

TARGET_TITLE_TERMS = [
    # Software / tech
    "engineer", "engineering", "developer", "develop", "software",
    "backend", "frontend", "full stack", "full-stack",
    "platform", "devops", "infrastructure", "sre",
    # Data / ML / AI
    "machine learning", "ml", "data", "analytics", "analyst",
    "data science", "data scientist", "ai ", "research",
    "business intelligence", "quantitative", "quant",
    # Finance / banking
    "financial", "finance", "capital markets", "risk", "treasury", "fintech",
    # Oil & gas / energy
    "petroleum", "reservoir", "production engineer", "digital engineer",
    "process engineer", "energy", "pipeline", "scada", "geospatial",
    # General tech-adjacent. "intern" alone is intentionally not enough;
    # it admits legal/marketing/social roles that waste auto-apply time.
    "technical", "technology", "co-op", "student",
]

TECH_SIGNAL_TERMS = [
    "engineer", "engineering", "developer", "develop", "software", "backend", "frontend",
    "full stack", "full-stack", "platform", "devops", "infrastructure", "sre",
    "machine learning", " ml", "data", "analytics", "analyst", "data science",
    "scientist", "ai ", "research", "business intelligence", "quant",
    "technical", "technology", "cloud", "security", "systems", "automation",
    "agent", "agentic",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _try_openclaw_assist(job: dict, blocker: str, resume_path: str, cover_path: str) -> None:
    """
    When auto-apply is blocked (CAPTCHA, login, unknown field), attempt to
    delegate the application to a local OpenClaw gateway via the tools/invoke API.
    OpenClaw can operate a supervised browser session on the user's behalf.
    Does nothing if OPENCLAW_GATEWAY_URL is not configured.
    """
    import os
    import requests as _req
    try:
        from storage.db import get_setting
        base_url = (get_setting("OPENCLAW_GATEWAY_URL", "") or os.getenv("OPENCLAW_GATEWAY_URL", "")).rstrip("/")
        token = get_setting("OPENCLAW_TOKEN", "") or os.getenv("OPENCLAW_TOKEN", "")
    except Exception:
        base_url = os.getenv("OPENCLAW_GATEWAY_URL", "").rstrip("/")
        token = os.getenv("OPENCLAW_TOKEN", "")

    if not base_url:
        return

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    message = (
        f"Job application needs human assistance.\n"
        f"Role: {job.get('title', '')} @ {job.get('company', '')}\n"
        f"URL: {job.get('url', '')}\n"
        f"Blocker: {blocker}\n"
        f"Resume: {resume_path}\n"
        f"Cover letter: {cover_path}\n\n"
        f"Please open the URL, complete and submit the application form for Moyosore Ogunjobi "
        f"(moyosorejobi@gmail.com, 825-736-5656). The resume and cover letter are attached above."
    )
    payload = {
        "model": os.getenv("OPENCLAW_MODEL", "openclaw/default"),
        "messages": [{"role": "user", "content": message}],
        "stream": False,
    }
    try:
        _req.post(f"{base_url}/v1/chat/completions", json=payload, headers=headers, timeout=10)
        print(f"[campaign] OpenClaw assist requested for {job.get('company', '')} ({blocker})", flush=True)
    except Exception as exc:
        print(f"[campaign] OpenClaw assist failed: {exc}", flush=True)


def _stage_artifacts(job_id: str, resume_pdf_path: str, cover_pdf_path: str) -> tuple[str, str]:
    """
    Copy generated artifacts to artifacts/staged/{job_id}/ with exact upload filenames.
    Portals receive 'Resume.pdf' and 'Cover Letter.pdf' — never timestamped names.
    """
    staged_job_dir = STAGED_DIR / job_id
    staged_job_dir.mkdir(parents=True, exist_ok=True)
    staged_resume = str(staged_job_dir / "Resume.pdf")
    staged_cover = str(staged_job_dir / "Cover Letter.pdf")
    if resume_pdf_path and Path(resume_pdf_path).exists():
        shutil.copy2(resume_pdf_path, staged_resume)
    if cover_pdf_path and Path(cover_pdf_path).exists():
        shutil.copy2(cover_pdf_path, staged_cover)
    return staged_resume, staged_cover


def _write_run_summary(campaign_id: str, rows: list, results: list[dict]) -> None:
    """Append a campaign run summary to logs/application_run_summary.md."""
    try:
        summary_path = LOGS_DIR / "application_run_summary.md"
        lines = [
            f"\n## Campaign {campaign_id[:8]}  —  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            f"| # | Company | Title | Portal | Status | Blocker |",
            f"|---|---------|-------|--------|--------|---------|",
        ]
        for row, res in zip(rows, results):
            status = "submitted" if res.get("ok") else res.get("stage", "failed")
            blocker = res.get("blocker", "") or ""
            lines.append(
                f"| {row.get('rank','')} | {row.get('company','')} | {row.get('title','')} "
                f"| {row.get('portal','')} | {status} | {blocker} |"
            )
        submitted = sum(1 for r in results if r.get("ok"))
        lines.append(f"\n**Total: {len(results)} processed, {submitted} submitted**\n")
        with open(summary_path, "a") as f:
            f.write("\n".join(lines))
    except Exception:
        pass


def build_provider_plan(openai_target: int, gemini_target: int, claude_target: int) -> list[str]:
    remaining = {
        "openai": openai_target,
        "gemini": gemini_target,
        "claude": claude_target,
    }
    plan: list[str] = []
    active = [provider for provider, count in remaining.items() if count > 0]
    while active:
        active.sort(key=lambda provider: (-remaining[provider], provider))
        next_active: list[str] = []
        for provider in active:
            if remaining[provider] <= 0:
                continue
            plan.append(provider)
            remaining[provider] -= 1
            if remaining[provider] > 0:
                next_active.append(provider)
        active = next_active
    return plan


def _artifact_provider_for_target(provider_target: str) -> str:
    return "anthropic" if provider_target == "claude" else provider_target


def _display_provider(provider_name: str) -> str:
    return "claude" if provider_name == "anthropic" else provider_name


def _is_auto_apply_target(job: dict, auto_submit: bool) -> bool:
    title = (job.get("title") or "").strip().lower()
    company = (job.get("company") or "").strip().lower()
    portal = (job.get("portal") or "").strip().lower()

    if not title:
        return False

    if any(term in title for term in EXCLUDED_TITLE_TERMS):
        return False

    if not any(term in title for term in TARGET_TITLE_TERMS):
        return False

    # A title like "Social Media Intern" technically matches "student/intern"
    # patterns elsewhere in the database, but it is not a good auto-submit target
    # for this software/data profile. Require a real technical/data signal.
    if not any(term in title for term in TECH_SIGNAL_TERMS):
        return False

    if auto_submit:
        if company in AUTO_APPLY_COMPANY_BLOCKLIST:
            return False
        if portal not in AUTO_PORTALS:
            return False

    return True


def _hire_probability_score(job: dict) -> float:
    """
    Score 0–100 for likelihood of getting a response/offer within 3-4 weeks.
    Factors: recency, Calgary/remote location, Tier A ATS, startup speed, skill match.
    """
    score = 0.0
    from datetime import datetime, timezone

    # Recency (35 pts) — fresher postings are still open
    posted_at = job.get("posted_at") or job.get("first_seen_at") or ""
    if posted_at:
        try:
            posted = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=timezone.utc)
            days_old = (datetime.now(timezone.utc) - posted).days
            if days_old <= 3:
                score += 35
            elif days_old <= 7:
                score += 28
            elif days_old <= 14:
                score += 20
            elif days_old <= 21:
                score += 12
            elif days_old <= 30:
                score += 6
        except Exception:
            score += 10

    # Location (20 pts) — Calgary or remote Canada = faster local hiring cycle
    loc = (job.get("location") or "").lower()
    desc = (job.get("description_raw") or "").lower()
    loc_text = loc + " " + desc[:200]
    if "calgary" in loc_text or "alberta" in loc_text:
        score += 20
    elif "canada remote" in loc_text or "remote canada" in loc_text or "remote, canada" in loc_text:
        score += 16
    elif "remote" in loc_text:
        score += 12
    elif "canada" in loc_text:
        score += 8
    else:
        score += 4

    # ATS tier (20 pts) — Greenhouse/Lever/Ashby have faster pipelines
    portal = (job.get("portal") or "").lower()
    if portal in ("greenhouse", "lever", "ashby"):
        score += 20
    elif portal == "workday":
        score += 10
    else:
        score += 5

    # Fit score proxy (15 pts) — better fit = higher interview chance
    fit_band = (job.get("fit_band") or "").lower()
    if fit_band == "strong":
        score += 15
    elif fit_band == "good":
        score += 10
    elif fit_band == "weak":
        score += 5

    # Internship/co-op signal (10 pts)
    title = (job.get("title") or "").lower()
    if any(s in title for s in ["intern", "co-op", "coop", "student"]):
        score += 10
    elif any(s in title for s in ["junior", "new grad", "entry"]):
        score += 7

    return round(score, 1)


def select_high_fit_jobs(target_total: int, min_score: float, auto_submit: bool) -> list[dict]:
    eligible_portals = (
        tuple(AUTO_PORTALS)
        if auto_submit
        else (*AUTO_PORTALS, "workday")
    )
    portal_placeholders = ",".join("?" for _ in eligible_portals)
    conn = get_conn()
    rows = conn.execute(
        f"""
        SELECT *
        FROM jobs
        WHERE manual_only=0
          AND apply_mode='ASSISTED_FILL'
          AND COALESCE(url, '') != ''
          AND portal IN ({portal_placeholders})
          AND status NOT IN ('applied')
          AND score >= ?
        ORDER BY
          CASE fit_band
            WHEN 'strong' THEN 0
            WHEN 'good' THEN 1
            WHEN 'weak' THEN 2
            ELSE 3
          END,
          CASE support_tier
            WHEN 'A' THEN 0
            WHEN 'B' THEN 1
            ELSE 2
          END,
          score DESC,
          first_seen_at DESC
        LIMIT ?
        """,
        (*eligible_portals, min_score, max(target_total * 6, 300)),
    ).fetchall()
    conn.close()

    candidates: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        job = dict(row)
        if not _is_auto_apply_target(job, auto_submit):
            continue
        if auto_submit:
            viability = calculate_viability(job, domain_memory=get_domain_memory(job))
            if not should_auto_queue(job, viability):
                continue
        dedupe_key = (
            (job.get("company") or "").strip().lower(),
            (job.get("title") or "").strip().lower(),
            (job.get("url") or "").strip().lower(),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        job["_hire_prob"] = _hire_probability_score(job)
        candidates.append(job)

    # Sort by hire probability descending so highest-chance jobs go first
    candidates.sort(key=lambda j: j["_hire_prob"], reverse=True)
    return candidates[:target_total]


def insert_notification(conn, kind: str, message: str, job_id: str | None = None):
    conn.execute(
        """
        INSERT INTO notifications (id, type, job_id, message, seen, created_at)
        VALUES (?,?,?,?,0,?)
        """,
        (str(uuid.uuid4()), kind, job_id, message, now_iso()),
    )


def persist_artifacts(conn, job_id: str, result: dict):
    for art_type, path_key in [
        ("resume_pdf", "resume_pdf_path"),
        ("cover_pdf", "cover_pdf_path"),
        ("answer_pack", "answer_pack_path"),
        ("job_search", "search_artifact_path"),
        ("jd_md", "jd_path"),
        ("tips_md", "study_plan_path"),
        ("outreach", "outreach_path"),
    ]:
        path = result.get(path_key, "")
        if not path:
            continue
        checksum = ""
        file_path = Path(path)
        if file_path.exists():
            checksum = str(file_path.stat().st_size)
        conn.execute(
            """
            INSERT OR REPLACE INTO artifacts (id, job_id, type, path, checksum, created_at)
            VALUES (?,?,?,?,?,?)
            """,
            (str(uuid.uuid4()), job_id, art_type, path, checksum, now_iso()),
        )


def refresh_campaign_counts(conn, campaign_id: str):
    stage_rows = conn.execute(
        "SELECT stage, COUNT(*) AS count FROM campaign_rows WHERE campaign_id=? GROUP BY stage",
        (campaign_id,),
    ).fetchall()
    stage_counts = {row["stage"]: row["count"] for row in stage_rows}
    assistance_count = sum(
        count for stage, count in stage_counts.items()
        if stage == "needs_assistance" or stage.startswith("assisted_")
    )
    failed_count = sum(
        count for stage, count in stage_counts.items()
        if stage == "failed" or stage.startswith("failed_")
    )
    prepared_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM campaign_rows
        WHERE campaign_id=?
          AND provider_used IS NOT NULL
        """,
        (campaign_id,),
    ).fetchone()[0]
    selected_count = conn.execute(
        "SELECT COUNT(*) FROM campaign_rows WHERE campaign_id=?",
        (campaign_id,),
    ).fetchone()[0]
    conn.execute(
        """
        UPDATE campaigns
        SET selected_count=?,
            prepared_count=?,
            submitted_count=?,
            assistance_count=?,
            failed_count=?
        WHERE id=?
        """,
        (
            selected_count,
            prepared_count,
            stage_counts.get("submitted", 0),
            assistance_count,
            failed_count,
            campaign_id,
        ),
    )


def create_campaign(
    name: str,
    target_total: int,
    openai_target: int,
    gemini_target: int,
    claude_target: int,
    tomorrow_target: int,
    min_score: float,
    auto_submit: bool,
) -> tuple[str, int]:
    jobs = select_high_fit_jobs(target_total, min_score, auto_submit)
    if not jobs:
        raise ValueError("No eligible high-fit jobs found for the requested target.")
    if len(jobs) < target_total:
        raise ValueError(f"Only {len(jobs)} eligible high-fit jobs available for a target of {target_total}.")

    provider_plan = build_provider_plan(openai_target, gemini_target, claude_target)
    if len(provider_plan) != target_total:
        raise ValueError("Provider plan does not match campaign target.")

    campaign_id = str(uuid.uuid4())
    now = now_iso()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO campaigns (
            id, name, state, target_total, target_openai, target_gemini, target_claude, tomorrow_target,
            selected_count, prepared_count, submitted_count, assistance_count, failed_count,
            auto_submit, min_score, notes, started_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            campaign_id,
            name,
            "queued",
            target_total,
            openai_target,
            gemini_target,
            claude_target,
            tomorrow_target,
            len(jobs),
            0,
            0,
            0,
            0,
            1 if auto_submit else 0,
            min_score,
            "High-fit jobs prioritized by score, fit band, and supported ATS.",
            now,
        ),
    )

    for rank, (job, provider_target) in enumerate(zip(jobs, provider_plan), start=1):
        details = json.dumps(
            {
                "selection_reason": "High-fit supported ATS role",
                "score": job.get("score", 0),
                "fit_band": job.get("fit_band", ""),
                "portal": job.get("portal", ""),
            }
        )
        conn.execute(
            """
            INSERT INTO campaign_rows (
                id, campaign_id, job_id, rank, provider_target, stage,
                assistance_required, details, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                campaign_id,
                job["id"],
                rank,
                provider_target,
                "queued",
                0,
                details,
                now,
                now,
            ),
        )
    insert_notification(
        conn,
        "campaign",
        (
            f"Campaign queued: {len(jobs)} high-fit jobs, "
            f"{openai_target} OpenAI, {gemini_target} Gemini, {claude_target} Claude."
        ),
    )
    conn.commit()
    conn.close()
    return campaign_id, len(jobs)


def _mark_row(
    conn,
    row_id: str,
    stage: str,
    provider_used: str = "",
    application_id: str = "",
    error: str = "",
    details: dict | None = None,
    assistance_required: bool = False,
):
    payload = json.dumps(details or {})
    conn.execute(
        """
        UPDATE campaign_rows
        SET stage=?,
            provider_used=CASE WHEN ?='' THEN provider_used ELSE ? END,
            application_id=CASE WHEN ?='' THEN application_id ELSE ? END,
            error=?,
            assistance_required=?,
            details=?,
            updated_at=?
        WHERE id=?
        """,
        (
            stage,
            provider_used,
            provider_used,
            application_id,
            application_id,
            error,
            1 if assistance_required else 0,
            payload,
            now_iso(),
            row_id,
        ),
    )


def run_campaign(
    campaign_id: str,
    progress_callback: ProgressCallback = None,
    stop_requested: StopCallback = None,
):
    conn = get_conn()
    campaign = conn.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
    rows = conn.execute(
        """
        SELECT cr.*, j.title, j.company, j.location, j.score, j.fit_band, j.support_tier,
               j.portal, j.url, j.apply_mode, j.manual_only, j.status, j.description_raw,
               j.description_normalized
        FROM campaign_rows cr
        JOIN jobs j ON j.id = cr.job_id
        WHERE cr.campaign_id=?
        ORDER BY cr.rank ASC
        """,
        (campaign_id,),
    ).fetchall()
    conn.execute("UPDATE campaigns SET state='running' WHERE id=?", (campaign_id,))
    conn.commit()
    conn.close()

    if campaign:
        notify_campaign_started(
            target_total=campaign["target_total"],
            openai_target=campaign["target_openai"],
            gemini_target=campaign["target_gemini"],
            claude_target=campaign["target_claude"],
            tomorrow_target=campaign["tomorrow_target"],
        )

    row_results: list[dict] = []
    for index, row in enumerate(rows, start=1):
        if stop_requested and stop_requested():
            conn = get_conn()
            conn.execute(
                "UPDATE campaigns SET state='cancelled', ended_at=? WHERE id=?",
                (now_iso(), campaign_id),
            )
            insert_notification(conn, "campaign", "Campaign cancelled by user.")
            conn.commit()
            conn.close()
            return

        job = dict(row)
        row_id = job["id"]
        job_id = job["job_id"]
        provider_target = job["provider_target"]

        if progress_callback:
            progress_callback(
                {
                    "campaign_id": campaign_id,
                    "current_rank": index,
                    "current_job": f"{job.get('title', '')} @ {job.get('company', '')}",
                    "provider_target": provider_target,
                }
            )

        conn = get_conn()
        _mark_row(conn, row_id, "preparing", details={"message": "Generating tailored artifacts."})
        conn.commit()
        conn.close()
        print(f"[campaign] [{index}/{len(rows)}] Preparing: {job.get('title','')} @ {job.get('company','')}", flush=True)

        try:
            # Ensure job dict uses the jobs-table id (not the campaign_row id)
            # so _save_application_memory() can satisfy the FOREIGN KEY on application_memory.job_id
            job_for_artifacts = {**job, "id": job_id}
            result = generate_artifacts(
                job_for_artifacts,
                preferred_provider=_artifact_provider_for_target(provider_target),
                allow_fallback=False,
            )
            provider_used = _display_provider(result.get("provider_used", provider_target))
            print(f"[campaign] [{index}/{len(rows)}] Artifacts ready (provider={provider_used})", flush=True)
            conn = get_conn()
            persist_artifacts(conn, job_id, result)
            conn.execute(
                "UPDATE jobs SET status='prepared', updated_at=? WHERE id=?",
                (now_iso(), job_id),
            )
            _mark_row(
                conn,
                row_id,
                "prepared" if not campaign["auto_submit"] else "applying",
                provider_used=provider_used,
                details={
                    "message": "Artifacts tailored and ready.",
                    "provider_used": provider_used,
                },
            )
            refresh_campaign_counts(conn, campaign_id)
            conn.commit()
            conn.close()
        except Exception as exc:
            conn = get_conn()
            _mark_row(
                conn,
                row_id,
                "failed",
                error=str(exc),
                details={"message": "Tailoring failed.", "error": str(exc)},
            )
            insert_notification(
                conn,
                "campaign",
                f"Tailoring failed for {job.get('title', '')} @ {job.get('company', '')}: {exc}",
                job_id=job_id,
            )
            refresh_campaign_counts(conn, campaign_id)
            conn.commit()
            conn.close()
            continue

        if not campaign["auto_submit"]:
            continue

        staged_resume, staged_cover = _stage_artifacts(
            job_id,
            result.get("resume_pdf_path", ""),
            result.get("cover_pdf_path", ""),
        )
        session_id = create_session(
            job_for_artifacts,
            artifacts={
                "resume_pdf_path": staged_resume,
                "cover_pdf_path": staged_cover,
                "answer_pack_path": result.get("answer_pack_path", ""),
            },
            headless=True,
        )
        application_id = str(uuid.uuid4())

        # Insert the application record before launching the browser so
        # the DB always has a row even if the apply attempt crashes.
        conn = get_conn()
        conn.execute(
            """
            INSERT INTO applications (
                id, job_id, stage, apply_mode, browser_session_id,
                review_required, final_confirmation_given, notes, created_at, updated_at
            ) VALUES (?,?,?,?,?,0,1,?,?,?)
            """,
            (
                application_id,
                job_id,
                "campaign_running",
                job.get("apply_mode", "ASSISTED_FILL"),
                session_id,
                f"Campaign {campaign_id} · provider {provider_target}",
                now_iso(),
                now_iso(),
            ),
        )
        conn.commit()
        conn.close()

        try:
            print(f"[campaign] [{index}/{len(rows)}] Browser apply starting: {job.get('url','')[:60]}", flush=True)
            session = get_session(session_id)

            # Route to the correct apply method based on portal
            portal = (job.get("portal") or "").lower()
            apply_result: dict = {}
            if portal == "linkedin" and "linkedin.com" in (job.get("url") or "").lower():
                try:
                    from storage.db import get_setting
                    li_email = get_setting("LINKEDIN_EMAIL", "") or ""
                    li_pass = get_setting("LINKEDIN_PASSWORD", "") or ""
                except Exception:
                    li_email = li_pass = ""
                if li_email and li_pass:
                    apply_result = session.linkedin_easy_apply_full(li_email, li_pass)
                else:
                    apply_result = {"ok": False, "blocker": "linkedin_creds_missing"}
            elif portal == "indeed" and "indeed.com" in (job.get("url") or "").lower():
                try:
                    from storage.db import get_setting
                    in_email = get_setting("INDEED_EMAIL", "") or ""
                    in_pass = get_setting("INDEED_PASSWORD", "") or ""
                except Exception:
                    in_email = in_pass = ""
                if in_email and in_pass:
                    apply_result = session.indeed_easy_apply_full(in_email, in_pass)
                else:
                    apply_result = {"ok": False, "blocker": "indeed_creds_missing"}
            else:
                # auto_apply_full handles the full pipeline:
                # start → map → fill all types (text/select/radio/checkbox/file)
                # → multi-page navigation → unknown-required check → submit → close
                apply_result = session.auto_apply_full()
            print(f"[campaign] [{index}/{len(rows)}] Apply result: ok={apply_result.get('ok')} blocker={apply_result.get('blocker')}", flush=True)

            conn = get_conn()
            if apply_result.get("ok"):
                conn.execute(
                    """
                    UPDATE applications
                    SET stage='submitted', submitted_at=?, final_confirmation_given=1, updated_at=?
                    WHERE id=?
                    """,
                    (now_iso(), now_iso(), application_id),
                )
                conn.execute(
                    "UPDATE jobs SET status='applied', updated_at=? WHERE id=?",
                    (now_iso(), job_id),
                )
                _mark_row(
                    conn,
                    row_id,
                    "submitted",
                    provider_used=provider_used,
                    application_id=application_id,
                    details={"message": "Application submitted via auto_apply_full."},
                )
                _domain_update = ("applied", "submitted")
                row_results.append({"ok": True, "rank": job.get("rank"), "company": job.get("company"), "title": job.get("title"), "portal": job.get("portal"), "stage": "submitted"})
            else:
                reason = apply_result.get("error", "Application failed")
                blocker = apply_result.get("blocker") or (
                    "captcha" if apply_result.get("captcha") else "manual_review"
                )
                needs_assistance = blocker not in ("unsupported_portal", "failed_unsupported")
                next_stage = assisted_status_for_blocker(blocker) if needs_assistance else "failed"
                app_stage = next_stage if needs_assistance else "failed"
                conn.execute(
                    """
                    UPDATE applications
                    SET stage=?, failure_reason=?, updated_at=?
                    WHERE id=?
                    """,
                    (app_stage, reason, now_iso(), application_id),
                )
                _mark_row(
                    conn,
                    row_id,
                    next_stage,
                    provider_used=provider_used,
                    application_id=application_id,
                    error=reason,
                    assistance_required=needs_assistance,
                    details={"message": reason, "blocker": blocker},
                )
                if needs_assistance:
                    insert_notification(
                        conn,
                        "campaign",
                        f"Assistance needed for {job.get('title', '')} @ {job.get('company', '')}: {reason}",
                        job_id=job_id,
                    )
                    notify_campaign_assistance(
                        title=job.get("title", ""),
                        company=job.get("company", ""),
                        reason=reason,
                        progress=f"{index}/{len(rows)}",
                    )
                    # Try OpenClaw tool invocation as a human-assist fallback.
                    # OpenClaw can operate a browser session on your behalf via
                    # its tools/invoke API — useful for CAPTCHA or login gates.
                    _try_openclaw_assist(job, blocker, staged_resume, staged_cover)
                else:
                    insert_notification(
                        conn,
                        "campaign",
                        f"Application failed for {job.get('title', '')} @ {job.get('company', '')}: {reason}",
                        job_id=job_id,
                    )
                _domain_update = (next_stage, reason)
                row_results.append({"ok": False, "rank": job.get("rank"), "company": job.get("company"), "title": job.get("title"), "portal": job.get("portal"), "stage": next_stage, "blocker": blocker})
            refresh_campaign_counts(conn, campaign_id)
            conn.commit()
            conn.close()
            # update_domain_memory opens its own conn — must run AFTER outer conn commits
            update_domain_memory(job, *_domain_update)
        except Exception as exc:
            conn = get_conn()
            conn.execute(
                """
                UPDATE applications
                SET stage='failed', failure_reason=?, updated_at=?
                WHERE id=?
                """,
                (str(exc), now_iso(), application_id),
            )
            _mark_row(
                conn,
                row_id,
                "failed",
                provider_used=provider_used,
                application_id=application_id,
                error=str(exc),
                details={"message": "Application failed.", "error": str(exc)},
            )
            insert_notification(
                conn,
                "campaign",
                f"Application failed for {job.get('title', '')} @ {job.get('company', '')}: {exc}",
                job_id=job_id,
            )
            refresh_campaign_counts(conn, campaign_id)
            conn.commit()
            conn.close()
            row_results.append({"ok": False, "rank": job.get("rank"), "company": job.get("company"), "title": job.get("title"), "portal": job.get("portal"), "stage": "failed", "blocker": str(exc)[:80]})
            update_domain_memory(job, "failed_transient", str(exc))
        finally:
            close_session(session_id)

    _write_run_summary(campaign_id, [dict(r) for r in rows], row_results)
    conn = get_conn()
    refresh_campaign_counts(conn, campaign_id)
    summary = conn.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
    conn.execute(
        "UPDATE campaigns SET state='done', ended_at=? WHERE id=?",
        (now_iso(), campaign_id),
    )
    insert_notification(
        conn,
        "campaign",
        f"Campaign done: {summary['submitted_count']} submitted, {summary['assistance_count']} need help, {summary['failed_count']} failed.",
    )
    conn.commit()
    conn.close()

    notify_campaign_done(
        submitted=summary["submitted_count"],
        assistance=summary["assistance_count"],
        failed=summary["failed_count"],
        tomorrow_target=summary["tomorrow_target"],
    )


def _slug(value: str, fallback: str = "item") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:80] or fallback


def _job_key(job: dict) -> tuple[str, str, str, str]:
    return (
        (job.get("company") or "").strip().lower(),
        (job.get("title") or "").strip().lower(),
        (job.get("location") or "").strip().lower(),
        (job.get("url") or "").strip().lower(),
    )


def _job_id(job: dict) -> str:
    if job.get("id"):
        return str(job["id"])
    seed = "|".join(_job_key(job))
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def _support_for_portal(portal: str) -> tuple[str, str, int, str]:
    portal = (portal or "").lower()
    if portal in {"linkedin", "indeed", "glassdoor"}:
        return "BLOCKED", "PREP_ONLY", 1, f"{portal} is manual-only by policy."
    if portal in {"greenhouse", "lever", "ashby"}:
        return "A", "ASSISTED_FILL", 0, ""
    if portal in {"workday", "amazon", "microsoft", "oracle", "taleo", "successfactors"}:
        return "B", "ASSISTED_FILL", 0, ""
    return "C", "PREP_ONLY", 0, ""


def _normalize_discovered_job(job: dict) -> dict:
    job = dict(job)
    job["id"] = _job_id(job)
    portal = (job.get("portal") or job.get("source") or "unknown").split(":")[0].lower()
    job["portal"] = portal
    score, breakdown, fit_band = score_job(job)
    job["score"] = score
    job["score_breakdown"] = json.dumps(breakdown)
    job["fit_band"] = fit_band
    support_tier, apply_mode, manual_only, restricted_reason = _support_for_portal(portal)
    job.setdefault("source", portal)
    job.setdefault("source_type", "api")
    job.setdefault("remote_type", "")
    job.setdefault("description_normalized", job.get("description_raw", ""))
    job.setdefault("posted_at", "")
    job.setdefault("first_seen_at", now_iso())
    job.setdefault("last_seen_at", now_iso())
    job["support_tier"] = job.get("support_tier") or support_tier
    job["apply_mode"] = job.get("apply_mode") or apply_mode
    job["manual_only"] = int(job.get("manual_only") or manual_only)
    job["restricted_reason"] = job.get("restricted_reason") or restricted_reason
    job.setdefault("status", "DISCOVERED")
    return job


def _coop_upsert_job(conn, job: dict) -> None:
    now = now_iso()
    existing = conn.execute("SELECT first_seen_at, status FROM jobs WHERE id=?", (job["id"],)).fetchone()
    viability = calculate_viability(job, domain_memory=get_domain_memory(job))
    policy = viability["policy"]
    if existing:
        conn.execute(
            """
            UPDATE jobs
            SET last_seen_at=?, score=?, score_breakdown=?, fit_band=?,
                description_raw=?, description_normalized=?, automation_tier=?,
                automation_reason=?, automation_viability_score=?,
                automation_viability_band=?, automation_viability_reasons=?, updated_at=?
            WHERE id=?
            """,
            (
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
                json.dumps(viability.get("reasons", [])),
                now,
                job["id"],
            ),
        )
        return
    conn.execute(
        """
        INSERT INTO jobs (
            id, source, source_type, portal, company, title, location, remote_type,
            url, description_raw, description_normalized, posted_at,
            first_seen_at, last_seen_at, score, score_breakdown, fit_band,
            support_tier, apply_mode, status, manual_only, restricted_reason,
            automation_tier, automation_reason, automation_viability_score,
            automation_viability_band, automation_viability_reasons,
            created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            job["id"],
            job.get("source", ""),
            job.get("source_type", "api"),
            job.get("portal", ""),
            job.get("company", ""),
            job.get("title", ""),
            job.get("location", ""),
            job.get("remote_type", ""),
            job.get("url", ""),
            job.get("description_raw", ""),
            job.get("description_normalized", ""),
            job.get("posted_at", ""),
            job.get("first_seen_at", now),
            job.get("last_seen_at", now),
            job.get("score", 0),
            job.get("score_breakdown", "{}"),
            job.get("fit_band", "unknown"),
            job.get("support_tier", "C"),
            job.get("apply_mode", "PREP_ONLY"),
            job.get("status", "DISCOVERED"),
            int(job.get("manual_only") or 0),
            job.get("restricted_reason", ""),
            policy.get("automation_tier", ""),
            policy.get("reason", ""),
            viability.get("score", 0),
            viability.get("band", ""),
            json.dumps(viability.get("reasons", [])),
            now,
            now,
        ),
    )


def _fetch_coop_source(source: str) -> list[dict]:
    if source == "greenhouse":
        from engine.sources.greenhouse import fetch_all
    elif source == "lever":
        from engine.sources.lever import fetch_all
    elif source == "ashby":
        from engine.sources.ashby import fetch_all
    elif source == "workday":
        from engine.sources.workday import fetch_all
    elif source == "amazon":
        from engine.sources.amazon import fetch_all
    elif source == "microsoft":
        from engine.sources.microsoft import fetch_all
    elif source == "github_repo":
        from engine.sources.github_repo import fetch_all
    elif source == "simplify":
        from engine.sources.simplify import fetch_all
    elif source == "google_jobs":
        from engine.sources.google_jobs import fetch_all
    elif source == "linkedin":
        from engine.sources.linkedin_jobs import fetch_all
    elif source == "indeed":
        from engine.sources.indeed import fetch_all
    elif source == "glassdoor":
        from engine.sources.glassdoor import fetch_all
    else:
        return []
    return fetch_all()


def _discover_coop_jobs(limit: int) -> dict:
    found: list[dict] = []
    errors: list[str] = []
    for source in COOP_DISCOVERY_SOURCES:
        try:
            jobs = [_normalize_discovered_job(j) for j in _fetch_coop_source(source)]
            found.extend(jobs)
            print(f"[coop] {source}: fetched {len(jobs)}", flush=True)
        except Exception as exc:
            errors.append(f"{source}: {exc}")
            print(f"[coop] {source}: error {exc}", flush=True)

    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[dict] = []
    for job in sorted(found, key=lambda j: float(j.get("score") or 0), reverse=True):
        key = _job_key(job)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)
        if len(deduped) >= limit:
            break

    conn = get_conn()
    for job in deduped:
        _coop_upsert_job(conn, job)
    conn.commit()
    conn.close()
    return {"jobs": deduped, "found": len(found), "deduped": len(deduped), "errors": errors}


def _select_coop_jobs(limit: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT *
        FROM jobs
        WHERE COALESCE(url, '') != ''
          AND status NOT IN ('applied', 'SAFE_AUTO_SUBMITTED', 'USER_SUBMITTED_CONFIRMED')
        ORDER BY score DESC, first_seen_at DESC
        LIMIT ?
        """,
        (max(limit * 4, limit),),
    ).fetchall()
    conn.close()
    selected: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        job = dict(row)
        if not _is_auto_apply_target(job, auto_submit=False):
            continue
        key = _job_key(job)
        if key in seen:
            continue
        seen.add(key)
        selected.append(job)
        if len(selected) >= limit:
            break
    return selected


def _latest_artifacts_for_job(job_id: str) -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT type, path FROM artifacts WHERE job_id=? ORDER BY created_at DESC", (job_id,)).fetchall()
    conn.close()
    artifacts: dict[str, str] = {}
    for row in rows:
        artifacts.setdefault(row["type"], row["path"])
    return artifacts


def _load_json_file(path: str) -> dict:
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return {}


def _application_folder(job: dict) -> Path:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    company_slug = _slug(job.get("company", ""), "company")
    job_slug = _slug(job.get("title", ""), "role")
    path = APPLICATIONS_DIR / date / company_slug / job_slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def _copy_if_exists(src: str, dst: Path) -> str:
    if src and Path(src).exists():
        shutil.copy2(src, dst)
        return str(dst)
    return ""


def _write_application_pack(job: dict, result: dict, policy_decision: dict | None = None, screenshot_path: str = "") -> dict:
    folder = _application_folder(job)
    paths = {
        "resume_pdf": _copy_if_exists(result.get("resume_pdf_path", ""), folder / "resume.pdf"),
        "cover_pdf": _copy_if_exists(result.get("cover_pdf_path", ""), folder / "cover_letter.pdf"),
        "answer_pack": _copy_if_exists(result.get("answer_pack_path", ""), folder / "answers.json"),
        "jd_md": _copy_if_exists(result.get("jd_path", ""), folder / "job_description.md"),
        "screenshot": _copy_if_exists(screenshot_path, folder / "screenshot.png"),
    }
    notes = folder / "application_notes.md"
    notes.write_text(
        "\n".join(
            [
                f"# {job.get('title', '')} @ {job.get('company', '')}",
                "",
                f"- Location: {job.get('location', '')}",
                f"- Portal: {job.get('portal', '')}",
                f"- Score: {job.get('score', '')}",
                f"- URL: {job.get('url', '')}",
                f"- Generated: {now_iso()}",
            ]
        )
    )
    if policy_decision is not None:
        policy_path = folder / "policy_decision.json"
        policy_path.write_text(json.dumps(policy_decision, indent=2))
        paths["policy_decision"] = str(policy_path)
    return {"folder": str(folder), **paths}


def _record_coop_application(job: dict, mode: str, status: str, reason: str, paths: dict, submitted: bool = False) -> str:
    app_id = str(uuid.uuid4())
    now = now_iso()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO applications (
            id, job_id, stage, apply_mode, review_required, final_confirmation_given,
            submitted_at, failure_reason, notes, uploaded_resume_path,
            uploaded_cover_letter_path, answers_json, confirmation_screenshot_path,
            created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            app_id,
            job["id"],
            "submitted" if submitted else status,
            mode,
            0 if submitted else 1,
            1 if submitted else 0,
            now if submitted else None,
            "" if submitted else reason,
            f"Co-op emergency runner: {reason}",
            paths.get("resume_pdf", ""),
            paths.get("cover_pdf", ""),
            paths.get("answer_pack", ""),
            paths.get("screenshot", ""),
            now,
            now,
        ),
    )
    conn.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", ("applied" if submitted else status, now, job["id"]))
    conn.commit()
    conn.close()
    return app_id


def _proof_row(job: dict, mode: str, status: str, reason: str, paths: dict, submit_time: str = "", notes: str = "") -> dict:
    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "company": job.get("company", ""),
        "title": job.get("title", ""),
        "location": job.get("location", ""),
        "portal": job.get("portal", ""),
        "job_url": job.get("url", ""),
        "score": job.get("score", ""),
        "mode": mode,
        "status": status,
        "submit_time": submit_time,
        "block_reason": reason,
        "resume_path": paths.get("resume_pdf", ""),
        "cover_letter_path": paths.get("cover_pdf", ""),
        "answer_pack_path": paths.get("answer_pack", ""),
        "screenshot_path": paths.get("screenshot", ""),
        "notes": notes,
    }


def export_coop_proof_log(rows: list[dict], run_id: str) -> str:
    out = LOGS_DIR / f"coop_emergency_proof_{run_id[:8]}.csv"
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PROOF_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    latest = LOGS_DIR / "coop_emergency_latest.csv"
    shutil.copy2(out, latest)
    return str(out)


def _domain_is_penalized(job: dict) -> bool:
    memory = get_domain_memory(job)
    return int(memory.get("captcha_count") or 0) > 0 or (
        int(memory.get("fail_count") or 0) >= 2 and int(memory.get("success_count") or 0) == 0
    )


def _prepare_job_pack(job: dict) -> tuple[dict, dict]:
    result = generate_artifacts(job)
    conn = get_conn()
    persist_artifacts(conn, job["id"], result)
    conn.execute("UPDATE jobs SET status='PREPARED', updated_at=? WHERE id=?", (now_iso(), job["id"]))
    conn.commit()
    conn.close()
    artifacts = {
        "resume_pdf": result.get("resume_pdf_path", ""),
        "cover_pdf": result.get("cover_pdf_path", ""),
        "answer_pack": result.get("answer_pack_path", ""),
        "jd_md": result.get("jd_path", ""),
    }
    return result, artifacts


def _assisted_review(job: dict, paths: dict) -> tuple[str, str]:
    session_id = create_session(
        job,
        artifacts={
            "resume_pdf_path": paths.get("resume_pdf", ""),
            "cover_pdf_path": paths.get("cover_pdf", ""),
            "answer_pack_path": paths.get("answer_pack", ""),
        },
        headless=False,
        keep_open_on_blocker=False,
    )
    screenshot_path = ""
    reason = "ready_for_review"
    try:
        session = get_session(session_id)
        if not session:
            return "", "browser_session_failed"
        start = session.start()
        if not start.get("ok"):
            return "", start.get("error", "browser_open_failed")
        blocker = session.detect_blocker()
        if blocker:
            return session._screenshot(f"blocked_{blocker}"), blocker
        session.map_fields()
        fill = session.fill_safe_fields()
        if fill.get("captcha_detected"):
            return session._screenshot("blocked_captcha"), "captcha_detected"
        review = session.get_review_state()
        screenshot_path = review.get("screenshot_path", "")
    finally:
        close_session(session_id)
    return screenshot_path, reason


def _run_coop_batch(jobs: list[dict], batch_no: int) -> list[dict]:
    proof_rows: list[dict] = []
    print(f"[coop] Starting batch {batch_no} with {len(jobs)} jobs", flush=True)
    for index, job in enumerate(jobs, start=1):
        print(f"[coop] batch {batch_no} [{index}/{len(jobs)}] {job.get('title','')} @ {job.get('company','')}", flush=True)
        try:
            result, artifacts = _prepare_job_pack(job)
            paths = _write_application_pack(job, result)
            if batch_no == 2 and _domain_is_penalized(job):
                decision = {"allowed": False, "mode": MANUAL_ONLY, "reason": "domain_has_recent_failures"}
            else:
                page_state = {}
                if (job.get("portal") or "").lower() in {"lever", "ashby", "greenhouse", "simple"}:
                    from engine.apply.browser_apply import dry_parse_application
                    page_state = dry_parse_application(job, headless=True)
                decision = can_submit_automatically(
                    job,
                    page_state=page_state,
                    artifacts=artifacts,
                    answers=_load_json_file(artifacts.get("answer_pack", "")),
                    domain_memory=get_domain_memory(job),
                )
            paths = _write_application_pack(job, result, decision)
            mode = decision.get("mode", MANUAL_ONLY)
            reason = decision.get("reason", "")
            status = status_for_policy_decision(decision)
            submit_time = ""
            if decision.get("allowed") and mode == SAFE_AUTO_SUBMIT:
                session_id = create_session(
                    job,
                    artifacts={
                        "resume_pdf_path": paths.get("resume_pdf", ""),
                        "cover_pdf_path": paths.get("cover_pdf", ""),
                        "answer_pack_path": paths.get("answer_pack", ""),
                    },
                    headless=True,
                )
                try:
                    session = get_session(session_id)
                    apply_result = session.auto_apply_full() if session else {"ok": False, "error": "session_missing"}
                finally:
                    close_session(session_id)
                if apply_result.get("ok"):
                    status = "SAFE_AUTO_SUBMITTED"
                    submit_time = now_iso()
                    receipt = Path(paths["folder"]) / "submission_receipt.md"
                    receipt.write_text(f"# Submission Receipt\n\nSubmitted: {submit_time}\n\nResult: {json.dumps(apply_result, indent=2)}\n")
                    _record_coop_application(job, mode, status, reason, paths, submitted=True)
                    update_domain_memory(job, "applied", "submitted")
                else:
                    blocker = apply_result.get("blocker") or ("captcha" if apply_result.get("captcha") else "manual_review")
                    reason = apply_result.get("error") or blocker
                    status = assisted_status_for_blocker(blocker)
                    _record_coop_application(job, ASSISTED_REVIEW, status, reason, paths, submitted=False)
                    update_domain_memory(job, status, reason)
            elif mode == ASSISTED_REVIEW:
                screenshot, assisted_reason = _assisted_review(job, paths)
                if screenshot:
                    paths["screenshot"] = _copy_if_exists(screenshot, Path(paths["folder"]) / "screenshot.png")
                if assisted_reason in {"captcha", "captcha_detected"}:
                    status = "BLOCKED_CAPTCHA"
                elif assisted_reason in {"login_required", "email_verification", "account_required"}:
                    status = "BLOCKED_LOGIN"
                else:
                    status = "READY_FOR_REVIEW"
                reason = assisted_reason or reason
                _record_coop_application(job, mode, status, reason, paths, submitted=False)
                update_domain_memory(job, status, reason)
            else:
                _record_coop_application(job, mode, "MANUAL_ONLY", reason, paths, submitted=False)
                update_domain_memory(job, "MANUAL_ONLY", reason)
            proof_rows.append(_proof_row(job, mode, status, reason, paths, submit_time=submit_time))
        except Exception as exc:
            paths = {"resume_pdf": "", "cover_pdf": "", "answer_pack": "", "screenshot": ""}
            proof_rows.append(_proof_row(job, MANUAL_ONLY, "FAILED", str(exc), paths))
            update_domain_memory(job, "FAILED", str(exc))
            print(f"[coop] failed: {exc}", flush=True)
    return proof_rows


def run_coop_emergency(discover: int = 500, prepare: int = 200, batch_size: int = 100) -> dict:
    bootstrap()
    run_id = str(uuid.uuid4())
    discovery = _discover_coop_jobs(discover)
    selected = _select_coop_jobs(prepare)
    if len(selected) < prepare:
        print(f"[coop] Only {len(selected)} eligible jobs available for prepare target {prepare}", flush=True)
    batch1 = selected[:batch_size]
    batch2 = selected[batch_size:batch_size * 2]
    rows: list[dict] = []
    rows.extend(_run_coop_batch(batch1, 1))
    rows.extend(_run_coop_batch(batch2, 2))
    proof_path = export_coop_proof_log(rows, run_id)
    summary = {
        "run_id": run_id,
        "jobs_discovered_raw": discovery["found"],
        "jobs_deduplicated": discovery["deduped"],
        "jobs_scored": discovery["deduped"],
        "top_jobs_selected": len(selected),
        "artifacts_generated": len([r for r in rows if r.get("resume_path")]),
        "safe_auto_submitted": len([r for r in rows if r.get("status") == "SAFE_AUTO_SUBMITTED"]),
        "assisted_review_ready": len([r for r in rows if r.get("status") == "READY_FOR_REVIEW"]),
        "manual_only_saved": len([r for r in rows if r.get("status") == "MANUAL_ONLY"]),
        "blocked": len([r for r in rows if str(r.get("status", "")).startswith("BLOCKED")]),
        "failed": len([r for r in rows if r.get("status") == "FAILED"]),
        "proof_log": proof_path,
        "errors": discovery["errors"],
        "updated_at": now_iso(),
    }
    summary_path = LOGS_DIR / "coop_emergency_latest.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"[coop] Done. Proof log: {proof_path}", flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Job Applier campaign runner")
    parser.add_argument("--mode", choices=["coop_emergency"], required=True)
    parser.add_argument("--discover", type=int, default=500)
    parser.add_argument("--prepare", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if args.mode == "coop_emergency":
        run_coop_emergency(discover=args.discover, prepare=args.prepare, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
