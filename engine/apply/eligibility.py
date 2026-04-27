"""Compatibility wrapper around portal_policy."""

from engine.apply.portal_policy import AUTO_PORTALS, classify_portal, job_domain
from storage.db import get_conn

SUPPORTED_AUTO_APPLY_PORTALS = tuple(portal for portal in AUTO_PORTALS if portal != "simple")


def explain_auto_apply_eligibility(job: dict) -> tuple[bool, str]:
    policy = classify_portal(job)
    if policy["portal"] == "workday" and job_domain(job):
        conn = get_conn()
        row = conn.execute("SELECT last_status FROM domain_memory WHERE domain=?", (job_domain(job),)).fetchone()
        conn.close()
        if row and (row["last_status"] or "").lower() == "workday_session_ready":
            policy = {**policy, "should_auto_apply": True, "reason": "Workday session is prepared for this domain."}
    if not policy["should_auto_apply"]:
        return False, policy["reason"]
    if (job.get("apply_mode") or "").strip().upper() != "ASSISTED_FILL":
        return False, "Job is not configured for assisted form filling."
    return True, ""


def is_auto_apply_eligible(job: dict) -> bool:
    eligible, _reason = explain_auto_apply_eligibility(job)
    return eligible
