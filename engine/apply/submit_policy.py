"""
Central submit policy for all automatic submission paths.

The policy is intentionally conservative: it decides whether the system may
submit without a human click. Anything uncertain becomes assisted/manual.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from engine.apply.portal_policy import job_domain, normalize_portal

SAFE_AUTO_SUBMIT = "SAFE_AUTO_SUBMIT"
ASSISTED_REVIEW = "ASSISTED_REVIEW"
MANUAL_ONLY = "MANUAL_ONLY"

MANUAL_ONLY_PORTALS = {"linkedin", "indeed", "glassdoor"}
SAFE_AUTO_PORTALS = {"lever", "ashby", "simple"}
ASSISTED_PORTALS = {
    "greenhouse",
    "workday",
    "amazon",
    "microsoft",
    "oracle",
    "taleo",
    "successfactors",
    "custom",
    "unknown",
}

REQUIRED_AUTO_ARTIFACTS = {
    "resume_pdf": "missing_resume_pdf",
    "cover_pdf": "missing_cover_letter_pdf",
    "answer_pack": "incomplete_answer_pack",
}


def _exists(path: str | None) -> bool:
    return bool(path) and Path(str(path)).exists()


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _answer_values(answers: dict | None) -> dict:
    if not isinstance(answers, dict):
        return {}
    nested = answers.get("answers")
    if isinstance(nested, dict):
        return nested
    return answers


def _has_answer(answers: dict, *keys: str) -> bool:
    values = _answer_values(answers)
    for key in keys:
        value = values.get(key)
        if isinstance(value, dict):
            if value.get("needs_user_review") or value.get("status") == "needs_user_review":
                return False
            value = value.get("answer") or value.get("value")
        if str(value or "").strip() and _lower(value) not in {"unknown", "n/a", "needs_user_review"}:
            return True
    return False


def _question_text(page_state: dict | None) -> str:
    if not isinstance(page_state, dict):
        return ""
    parts: list[str] = []
    for key in ("required_questions", "unknown_required_fields", "fields"):
        value = page_state.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    parts.append(" ".join(str(item.get(k, "")) for k in ("label", "name", "question")))
                else:
                    parts.append(str(item))
    return " ".join(parts).lower()


def _mode_for_blocked_portal(portal: str) -> str:
    if portal in MANUAL_ONLY_PORTALS:
        return MANUAL_ONLY
    return ASSISTED_REVIEW


def can_submit_automatically(
    job: dict,
    page_state: dict | None,
    artifacts: dict | None,
    answers: dict | None,
    domain_memory: dict | None,
) -> dict:
    """
    Return a policy decision:
      {allowed: bool, mode: SAFE_AUTO_SUBMIT|ASSISTED_REVIEW|MANUAL_ONLY, reason: str}
    """
    page_state = page_state or {}
    artifacts = artifacts or {}
    answers = answers or {}
    domain_memory = domain_memory or {}

    portal = normalize_portal(job)
    url = _lower(job.get("url"))
    score = float(job.get("score") or 0)

    if portal in MANUAL_ONLY_PORTALS or any(host in url for host in ("linkedin.com", "indeed.com", "glassdoor.")):
        return {"allowed": False, "mode": MANUAL_ONLY, "reason": "manual_only_platform"}

    blocker = _lower(page_state.get("blocker"))
    if page_state.get("captcha") or blocker == "captcha":
        return {"allowed": False, "mode": MANUAL_ONLY, "reason": "captcha_detected"}
    if blocker == "login_required":
        return {"allowed": False, "mode": MANUAL_ONLY, "reason": "login_required"}
    if blocker == "account_required":
        return {"allowed": False, "mode": MANUAL_ONLY, "reason": "account_creation_required"}
    if blocker == "email_verification":
        return {"allowed": False, "mode": MANUAL_ONLY, "reason": "email_verification_required"}
    if blocker == "unknown_required_field" or page_state.get("unknown_required_fields"):
        return {"allowed": False, "mode": MANUAL_ONLY, "reason": "unknown_required_questions"}
    if blocker:
        return {"allowed": False, "mode": _mode_for_blocked_portal(portal), "reason": blocker}

    for field in page_state.get("fields") or []:
        if not isinstance(field, dict):
            continue
        label = _lower(" ".join(str(field.get(k, "")) for k in ("label", "name", "canonical_key")))
        field_type = _lower(field.get("type"))
        if field.get("required") and field_type in {"checkbox", "radio"} and any(
            token in label for token in ("certify", "attest", "acknowledge", "confirm", "authorize")
        ):
            return {"allowed": False, "mode": ASSISTED_REVIEW, "reason": "manual_attestation_required"}

    for art_type, reason in REQUIRED_AUTO_ARTIFACTS.items():
        if not _exists(artifacts.get(art_type)):
            return {"allowed": False, "mode": ASSISTED_REVIEW, "reason": reason}

    if score < 55:
        return {"allowed": False, "mode": ASSISTED_REVIEW, "reason": "job_score_too_low"}

    if _int(domain_memory.get("captcha_count")) > 0:
        return {"allowed": False, "mode": ASSISTED_REVIEW, "reason": "domain_has_recent_failures"}
    if _int(domain_memory.get("fail_count")) >= 2 and _int(domain_memory.get("success_count")) == 0:
        return {"allowed": False, "mode": ASSISTED_REVIEW, "reason": "domain_has_recent_failures"}
    if _lower(domain_memory.get("last_status")) in {
        "assisted_captcha",
        "assisted_login_required",
        "assisted_email_verification",
        "assisted_account_required",
        "failed_unsupported",
    }:
        return {"allowed": False, "mode": ASSISTED_REVIEW, "reason": "domain_has_recent_failures"}

    questions = _question_text(page_state)
    if ("work authorization" in questions or "authorized to work" in questions) and not _has_answer(
        answers, "work_authorization", "canada_work_auth", "us_work_auth"
    ):
        return {"allowed": False, "mode": ASSISTED_REVIEW, "reason": "work_authorization_unknown"}
    if ("salary" in questions or "compensation" in questions or "pay expectation" in questions) and not _has_answer(
        answers, "salary_expectation"
    ):
        return {"allowed": False, "mode": ASSISTED_REVIEW, "reason": "salary_answer_unknown"}
    if ("location" in questions or "relocat" in questions or "hybrid" in questions) and not _has_answer(
        answers, "location_preference", "relocation", "remote_hybrid"
    ):
        return {"allowed": False, "mode": ASSISTED_REVIEW, "reason": "location_mismatch"}

    if portal == "greenhouse":
        if page_state.get("official_application_api") and page_state.get("questions_complete"):
            return {"allowed": True, "mode": SAFE_AUTO_SUBMIT, "reason": "safe_auto_submit_allowed"}
        return {"allowed": False, "mode": ASSISTED_REVIEW, "reason": "official_api_not_available"}

    if portal == "workday":
        return {"allowed": False, "mode": ASSISTED_REVIEW, "reason": "unsupported_portal"}

    if portal in SAFE_AUTO_PORTALS:
        return {"allowed": True, "mode": SAFE_AUTO_SUBMIT, "reason": "safe_auto_submit_allowed"}

    if portal in ASSISTED_PORTALS:
        return {"allowed": False, "mode": ASSISTED_REVIEW, "reason": "unsupported_portal"}

    return {"allowed": False, "mode": MANUAL_ONLY, "reason": "unsupported_portal"}


def status_for_policy_decision(decision: dict) -> str:
    if decision.get("allowed"):
        return "SAFE_AUTO_SUBMITTED"
    reason = decision.get("reason")
    if reason == "captcha_detected":
        return "BLOCKED_CAPTCHA"
    if reason in {"login_required", "email_verification_required", "account_creation_required"}:
        return "BLOCKED_LOGIN"
    if reason == "unknown_required_questions":
        return "BLOCKED_UNKNOWN_QUESTION"
    if decision.get("mode") == MANUAL_ONLY:
        return "MANUAL_ONLY"
    return "READY_FOR_REVIEW"
