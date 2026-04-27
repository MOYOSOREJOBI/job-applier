"""
Portal policy and automation viability scoring.

This module is intentionally conservative: it improves throughput by refusing
doomed portals before the browser spends time on them.
"""

from __future__ import annotations

from urllib.parse import urlparse

# Greenhouse-hosted domains always show reCAPTCHA before the form.
# Branded career sites (hootsuite, pinterest) are fine — they embed Greenhouse
# in an iframe without a CAPTCHA gate.
# Rule: any subdomain of greenhouse.io is hosted by Greenhouse = CAPTCHA.
def _is_greenhouse_hosted(domain: str) -> bool:
    """Return True for any Greenhouse-hosted domain (*.greenhouse.io)."""
    return domain == "greenhouse.io" or domain.endswith(".greenhouse.io")

# Greenhouse has reCAPTCHA on ALL their forms (hosted and embed) — excluded from auto-submit.
# Lever and Ashby have no CAPTCHA gate on application forms.
AUTO_PORTALS = ["lever", "ashby", "simple"]
AUTO_PORTALS_GREENHOUSE_INCLUDED = ["greenhouse", "lever", "ashby", "simple"]  # for assisted/prep only
ASSISTED_PORTALS = ["workday", "oracle", "taleo", "successfactors", "amazon", "microsoft"]
# LinkedIn and Indeed move to "easy_apply" tier when credentials are configured.
# They stay MANUAL_ONLY if no creds are set.
EASY_APPLY_PORTALS = ["linkedin", "indeed"]
MANUAL_ONLY_PORTALS: list[str] = []  # nothing is permanently manual-only now


def _easy_apply_creds_configured(portal: str) -> bool:
    """Return True if credentials for the portal's Easy Apply are stored."""
    try:
        from storage.db import get_setting
        if portal == "linkedin":
            return bool(get_setting("LINKEDIN_EMAIL", "") and get_setting("LINKEDIN_PASSWORD", ""))
        if portal == "indeed":
            return bool(get_setting("INDEED_EMAIL", "") and get_setting("INDEED_PASSWORD", ""))
    except Exception:
        pass
    import os
    if portal == "linkedin":
        return bool(os.getenv("LINKEDIN_EMAIL") and os.getenv("LINKEDIN_PASSWORD"))
    if portal == "indeed":
        return bool(os.getenv("INDEED_EMAIL") and os.getenv("INDEED_PASSWORD"))
    return False

AUTO_QUEUE_THRESHOLD = 85
BACKFILL_QUEUE_THRESHOLD = 15
ASSISTED_THRESHOLD = 10

ASSISTED_BLOCKERS = {
    "login_required",
    "email_verification",
    "captcha",
    "account_required",
    "unknown_required_field",
    "manual_review",
}

PORTAL_DOMAIN_HINTS = {
    "greenhouse.io": "greenhouse",
    "lever.co": "lever",
    "ashbyhq.com": "ashby",
    "myworkdayjobs.com": "workday",
    "workdayjobs.com": "workday",
    "linkedin.com": "linkedin",
    "oraclecloud.com": "oracle",
    "taleo.net": "taleo",
    "successfactors.com": "successfactors",
    "amazon.jobs": "amazon",
    "careers.microsoft.com": "microsoft",
}


def job_domain(job: dict) -> str:
    url = (job.get("url") or "").strip()
    if not url:
        return ""
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def normalize_portal(job: dict) -> str:
    portal = (job.get("portal") or "").strip().lower()
    if portal:
        return portal
    domain = job_domain(job)
    for hint, mapped in PORTAL_DOMAIN_HINTS.items():
        if hint in domain:
            return mapped
    return "unknown"


def _memory_count(domain_memory: dict | None, key: str) -> int:
    if not domain_memory:
        return 0
    try:
        return int(domain_memory.get(key) or 0)
    except Exception:
        return 0


def classify_portal(job: dict) -> dict:
    portal = normalize_portal(job)
    url = (job.get("url") or "").strip()
    status = (job.get("status") or "").strip().lower()
    reason = ""
    tier = "skip"

    if status == "applied":
        reason = "Already applied."
    elif not url:
        reason = "No direct apply URL."
    elif job.get("manual_only"):
        reason = job.get("restricted_reason") or "Job is marked manual-only."
    elif portal in EASY_APPLY_PORTALS:
        if _easy_apply_creds_configured(portal):
            tier = "easy_apply"
            reason = f"{portal.title()} Easy Apply — credentials configured."
        else:
            tier = "manual"
            reason = f"{portal.title()} Easy Apply requires credentials in Settings (LINKEDIN_EMAIL/PASSWORD or INDEED_EMAIL/PASSWORD)."
    elif portal in AUTO_PORTALS:
        tier = "auto"
        reason = "Automation-friendly portal."
    elif portal in ASSISTED_PORTALS:
        tier = "assisted"
        if portal == "workday":
            reason = "Workday is account-first/email-verification prone; assisted only."
        else:
            reason = f"{portal} is treated as assisted until proven safe."
    else:
        tier = "assisted"
        reason = "Unknown/custom portal requires dry-parse before auto-submit."

    return {
        "portal": portal,
        "automation_tier": tier,
        "reason": reason,
        "should_auto_apply": tier == "auto",
    }


def calculate_viability(job: dict, domain_memory: dict | None = None, dry_parse: dict | None = None) -> dict:
    policy = classify_portal(job)
    portal = policy["portal"]
    reasons: list[str] = []
    score = 0
    blocker = (dry_parse or {}).get("blocker")
    title = (job.get("title") or "").lower()
    location = (job.get("location") or "").lower()
    description = ((job.get("description_raw") or "") + " " + (job.get("description_normalized") or "")).lower()
    combined = f"{title} {location} {description[:2500]}"
    workday_session_ready = (
        portal == "workday"
        and ((domain_memory or {}).get("last_status") or "").lower() == "workday_session_ready"
    )
    if workday_session_ready:
        policy = {**policy, "automation_tier": "auto", "should_auto_apply": True, "reason": "Workday session is prepared for this domain."}

    if policy["automation_tier"] == "easy_apply":
        score += 35
        reasons.append(f"{portal} Easy Apply credentials configured")
    elif portal in AUTO_PORTALS or workday_session_ready:
        score += 35
        reasons.append("automation-friendly portal" if not workday_session_ready else "prepared Workday browser session")
    if job.get("url"):
        score += 15
        reasons.append("direct apply URL")

    has_resume_upload = (dry_parse or {}).get("has_resume_upload")
    if has_resume_upload is True or portal in AUTO_PORTALS or workday_session_ready:
        score += 10
        reasons.append("resume upload expected")

    has_cover_upload = (dry_parse or {}).get("has_cover_upload")
    if has_cover_upload is True or has_cover_upload is False or portal in AUTO_PORTALS or workday_session_ready:
        score += 10
        reasons.append("cover letter optional/uploadable")

    field_count = (dry_parse or {}).get("field_count")
    if field_count is None:
        if portal in AUTO_PORTALS or workday_session_ready:
            score += 10
            reasons.append("field count expected low/medium")
    else:
        try:
            field_count_i = int(field_count)
        except Exception:
            field_count_i = 99
        if field_count_i <= 24:
            score += 10
            reasons.append(f"field count {field_count_i}")
        elif field_count_i > 45:
            score -= 15
            reasons.append(f"high field count {field_count_i}")

    if _memory_count(domain_memory, "success_count") > 0:
        score += 10
        reasons.append("previous success on domain")

    if not blocker:
        score += 5
        reasons.append("no visible blocker detected")

    role_terms = [
        "software", "backend", "front end", "frontend", "full stack", "full-stack",
        "developer", "devops", "cloud", "site reliability", "sre", "data engineer",
        "data analyst", "data scientist", "machine learning", " ml ", "ai ",
        "quant", "trading", "automation", "cad", "mechanical", "civil", "engineering",
    ]
    if any(term in combined for term in role_terms):
        score += 30
        reasons.append("role family matches target profile")

    level_terms = ["intern", "internship", "co-op", "coop", "student", "new grad", "junior", "entry level", "entry-level", "early career"]
    if any(term in combined for term in level_terms):
        score += 25
        reasons.append("student-friendly level")

    if any(term in location for term in ["calgary", "vancouver", "toronto", "remote canada", "remote, canada", "canada remote"]):
        score += 15
        reasons.append("target location")

    if any(term in combined for term in ["summer 2026", "may 2026", "june 2026", "summer internship", "2026 internship"]):
        score += 15
        reasons.append("target start window")

    if any(term in combined for term in ["$25", "$26", "$27", "$28", "$29", "$30", "$31", "$32", "$33", "$34", "$35", "$40", "competitive pay", "paid internship"]):
        score += 15
        reasons.append("pay likely meets target or paid")
    elif "unpaid" in combined or "commission only" in combined or "commission-only" in combined or "volunteer" in combined:
        score -= 20
        reasons.append("low-quality pay signal")
    else:
        reasons.append("pay_unknown")

    skill_terms = ["python", "java", "typescript", "javascript", "react", "fastapi", "sql", "postgres", "aws", "docker", "kubernetes", "terraform", "machine learning", "pytorch", "data pipeline", "analytics"]
    if sum(1 for term in skill_terms if term in combined) >= 2:
        score += 10
        reasons.append("strong keyword match")

    senior_terms = ["senior", "staff", "principal", "manager", "director", "lead "]
    if any(term in title for term in senior_terms) and not any(term in title for term in ["intern", "co-op", "coop", "new grad", "junior"]):
        score -= 50
        reasons.append("senior/staff/manager role")

    if portal in ("workday", "oracle", "taleo", "successfactors") and not workday_session_ready:
        score -= 40
        reasons.append(f"{portal} is account-first/risky")
    if blocker == "login_required":
        score -= 50
        reasons.append("login required before form access")
    if blocker == "email_verification":
        score -= 50
        reasons.append("email verification required")
    if blocker == "captcha":
        score -= 60
        reasons.append("visible CAPTCHA")
    if blocker == "account_required":
        score -= 50
        reasons.append("account creation required")
    if blocker == "unknown_required_field":
        score -= 30
        reasons.append("unknown required questions")
    if _memory_count(domain_memory, "fail_count") >= 2:
        score -= 30
        reasons.append("previous failures on domain")
    assisted_count = _memory_count(domain_memory, "assisted_count")
    success_count = _memory_count(domain_memory, "success_count")
    if assisted_count >= 2 and success_count == 0:
        score -= 30
        reasons.append("repeated assisted outcomes on domain")
    last_status = ((domain_memory or {}).get("last_status") or "").lower()
    last_reason = ((domain_memory or {}).get("last_reason") or "").lower()
    if last_status == "assisted_manual_review":
        penalty = 25 if ("submit button" in last_reason or "confirmation" in last_reason) else 15
        score -= penalty
        reasons.append("recent manual-review outcome on domain")
    _override_captcha = job.get("_override_captcha_count", None)
    _captcha_hits = int(_override_captcha if _override_captcha is not None else _memory_count(domain_memory, "captcha_count"))
    if _captcha_hits >= 2:
        score -= 100
        reasons.append(f"domain blocked: {_captcha_hits} CAPTCHA hits, no successes")
    elif _captcha_hits == 1:
        score -= 25
        reasons.append("domain has 1 CAPTCHA incident")
    if (portal == "linkedin" or "linkedin.com" in (job.get("url") or "").lower()) and policy.get("automation_tier") != "easy_apply":
        score -= 100
        reasons.append("LinkedIn: no Easy Apply credentials configured")
    _url_domain = job_domain(job)
    if _is_greenhouse_hosted(_url_domain):
        score -= 100
        reasons.append(f"{_url_domain} is Greenhouse-hosted — always shows reCAPTCHA")

    if policy["automation_tier"] == "manual":
        score = min(score, 25)
    elif policy["automation_tier"] in ("skip", "assisted"):
        score = min(score, 69)

    score = max(0, min(100, int(score)))
    if score >= 85:
        band = "excellent"
    elif score >= 70:
        band = "good"
    elif score >= 50:
        band = "risky"
    else:
        band = "manual"

    return {
        "score": score,
        "band": band,
        "reasons": reasons,
        "policy": policy,
    }


def assisted_status_for_blocker(blocker: str | None) -> str:
    return {
        "login_required": "assisted_login_required",
        "email_verification": "assisted_email_verification",
        "captcha": "assisted_captcha",
        "account_required": "assisted_account_required",
        "unknown_required_field": "assisted_unknown_required_field",
        "manual_review": "assisted_manual_review",
        "unsupported_portal": "failed_unsupported",
    }.get(blocker or "", "assisted_manual_review")


def should_auto_queue(job: dict, viability: dict | None = None, allow_backfill: bool = False) -> bool:
    viability = viability or calculate_viability(job)
    tier = viability.get("policy", {}).get("automation_tier", "")
    if tier not in ("auto", "easy_apply"):
        return False
    threshold = BACKFILL_QUEUE_THRESHOLD if allow_backfill else AUTO_QUEUE_THRESHOLD
    return int(viability.get("score") or 0) >= threshold
