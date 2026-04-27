"""Persistence helpers for per-domain apply outcomes."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from engine.apply.portal_policy import classify_portal, job_domain
from storage.db import get_conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_domain_memory(job_or_domain: dict | str) -> dict:
    domain = job_domain(job_or_domain) if isinstance(job_or_domain, dict) else job_or_domain
    if not domain:
        return {}
    conn = get_conn()
    row = conn.execute("SELECT * FROM domain_memory WHERE domain=?", (domain,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def update_domain_memory(
    job: dict,
    status: str,
    reason: str = "",
    duration_sec: float | None = None,
    selectors: dict | None = None,
) -> None:
    domain = job_domain(job)
    if not domain:
        return
    conn = get_conn()
    try:
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
        conn.commit()
    finally:
        conn.close()
