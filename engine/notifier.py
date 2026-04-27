"""
Job Applier — Notifier
Sends alerts via Telegram and/or OpenClaw (multi-channel: WhatsApp, Discord, Slack, etc.).

Config (DB settings or env):
    TELEGRAM_BOT_TOKEN      — from @BotFather
    TELEGRAM_CHAT_ID        — your personal chat ID (get from @userinfobot)
    OPENCLAW_GATEWAY_URL    — e.g. http://localhost:18789 (OpenClaw gateway)
    OPENCLAW_TOKEN          — Bearer token for OpenClaw gateway (if auth enabled)
    OPENCLAW_MODEL          — OpenClaw agent to use (default: openclaw/default)
"""
import os
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


# ── OpenClaw Notifier ─────────────────────────────────────────────────────────

def _openclaw_settings() -> dict:
    try:
        from storage.db import all_settings
        return all_settings()
    except Exception:
        return {}


def _send_openclaw(message: str, settings: dict | None = None) -> dict:
    """
    Push a notification message through the local OpenClaw gateway.
    OpenClaw routes it to whatever channel(s) you have connected
    (WhatsApp, Discord, Slack, Telegram, iMessage, etc.).
    Gateway runs at OPENCLAW_GATEWAY_URL (default localhost:18789).
    """
    s = settings or _openclaw_settings()
    base_url = (s.get("OPENCLAW_GATEWAY_URL") or os.getenv("OPENCLAW_GATEWAY_URL", "")).rstrip("/")
    token = s.get("OPENCLAW_TOKEN") or os.getenv("OPENCLAW_TOKEN", "")
    model = s.get("OPENCLAW_MODEL") or os.getenv("OPENCLAW_MODEL", "openclaw/default")

    if not base_url:
        logger.debug("OpenClaw not configured — skipping")
        return {"ok": False, "error": "not_configured"}

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "stream": False,
    }
    try:
        resp = requests.post(f"{base_url}/v1/chat/completions", json=payload, headers=headers, timeout=10)
        data = resp.json()
        return {"ok": resp.status_code == 200, "data": data}
    except Exception as exc:
        logger.error("OpenClaw send error: %s", exc)
        return {"ok": False, "error": str(exc)}


def notify(message: str, settings: dict | None = None, reply_markup: dict | None = None) -> dict:
    """
    Send via all configured channels (Telegram + OpenClaw).
    Returns the Telegram result (primary); OpenClaw is fire-and-forget.
    """
    _send_openclaw(message, settings)
    return send(message, settings, reply_markup)


def _get_settings() -> dict:
    """Pull Telegram settings from DB at call time."""
    try:
        from storage.db import all_settings
        return all_settings()
    except Exception:
        return {}


def _token_and_chat(settings: dict | None = None) -> tuple[str, str]:
    s = settings or _get_settings()
    token = s.get("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = s.get("TELEGRAM_CHAT_ID")   or os.getenv("TELEGRAM_CHAT_ID", "")
    return token, chat


def _inline_keyboard(*rows: list[tuple[str, str]]) -> dict:
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": data} for label, data in row]
            for row in rows
        ]
    }


def send(message: str, settings: dict | None = None, reply_markup: dict | None = None) -> dict:
    token, chat = _token_and_chat(settings)
    if not token or not chat:
        logger.debug("Telegram not configured — skipping notification")
        return {"ok": False, "error": "not_configured"}

    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    body: dict = {"chat_id": chat, "text": message, "parse_mode": "HTML"}
    if reply_markup:
        body["reply_markup"] = reply_markup

    try:
        resp = requests.post(url, json=body, timeout=10)
        data = resp.json()
        if not data.get("ok"):
            logger.warning("Telegram send failed: %s", data)
        return data
    except Exception as exc:
        logger.error("Telegram error: %s", exc)
        return {"ok": False, "error": str(exc)}


# ── Milestone ─────────────────────────────────────────────────────────────────

def notify_milestone(count: int, settings: dict | None = None) -> dict:
    msg = (
        f"🎯 <b>Job Milestone — {count} Applications!</b>\n\n"
        f"You've submitted <b>{count} applications</b> total.\n"
        f"⏰ {datetime.now().strftime('%b %d %Y, %H:%M')}\n\n"
        f"Keep pushing 💪"
    )
    return send(msg, settings)


# ── CAPTCHA / Robot checks ────────────────────────────────────────────────────

def notify_captcha(
    job_title: str,
    company: str,
    url: str,
    indicators: list[str] | None = None,
    settings: dict | None = None,
) -> dict:
    ind_str = ", ".join(indicators or ["captcha"])
    msg = (
        f"🤖 <b>CAPTCHA Detected — Action Needed</b>\n\n"
        f"Job: <b>{job_title}</b>\n"
        f"Company: {company}\n"
        f"Detected: <code>{ind_str}</code>\n"
        f"URL: <code>{url[:100]}</code>\n\n"
        f"Please solve it in the browser, then tap your choice:"
    )
    return send(msg, settings, reply_markup=_inline_keyboard(
        [("✅ Done, continue", "captcha:done"), ("⏭ Skip this job", "captcha:skip"), ("❌ Abort", "captcha:abort")]
    ))


def notify_robot_question(
    question: str,
    job_title: str,
    company: str,
    settings: dict | None = None,
) -> dict:
    msg = (
        f"❓ <b>Application Question Needs You</b>\n\n"
        f"Job: <b>{job_title}</b> @ {company}\n\n"
        f"Question:\n<i>{question[:300]}</i>\n\n"
        f"Please answer in the open browser."
    )
    return send(msg, settings)


# ── LinkedIn jobs ─────────────────────────────────────────────────────────────

def notify_linkedin_jobs_found(
    jobs: list[dict],
    settings: dict | None = None,
) -> dict:
    if not jobs:
        return {"ok": True, "skipped": True}

    easy_apply = [j for j in jobs if j.get("linkedin_apply_type") == "easy_apply"]
    link_apply = [j for j in jobs if j.get("linkedin_apply_type") == "link"]

    lines = [f"🔵 <b>LinkedIn Jobs Found — {len(jobs)} new</b>\n"]

    if easy_apply:
        lines.append(f"\n⚡ <b>Easy Apply ({len(easy_apply)})</b>")
        for j in easy_apply[:5]:
            lines.append(f"  • {j.get('title','')} @ {j.get('company','')}")
        if len(easy_apply) > 5:
            lines.append(f"  … +{len(easy_apply)-5} more")

    if link_apply:
        lines.append(f"\n🔗 <b>Link Apply (→ ATS) ({len(link_apply)})</b>")
        for j in link_apply[:5]:
            lines.append(f"  • {j.get('title','')} @ {j.get('company','')}")
        if len(link_apply) > 5:
            lines.append(f"  … +{len(link_apply)-5} more")

    lines.append(f"\n⏰ {datetime.now().strftime('%H:%M')}")
    return send("\n".join(lines), settings)


# ── Glassdoor jobs ────────────────────────────────────────────────────────────

def notify_glassdoor_jobs_found(
    jobs: list[dict],
    settings: dict | None = None,
) -> dict:
    if not jobs:
        return {"ok": True, "skipped": True}
    msg = (
        f"🟢 <b>Glassdoor Jobs Found — {len(jobs)} new</b>\n\n"
        + "\n".join(f"  • {j.get('title','')} @ {j.get('company','')}" for j in jobs[:8])
        + (f"\n  … +{len(jobs)-8} more" if len(jobs) > 8 else "")
        + f"\n\n⏰ {datetime.now().strftime('%H:%M')}"
    )
    return send(msg, settings)


# ── GitHub repo jobs ──────────────────────────────────────────────────────────

def notify_github_jobs_found(
    jobs: list[dict],
    settings: dict | None = None,
) -> dict:
    if not jobs:
        return {"ok": True, "skipped": True}
    msg = (
        f"🐙 <b>GitHub Repo Jobs — {len(jobs)} found</b>\n\n"
        + "\n".join(f"  • {j.get('title','')} @ {j.get('company','')}" for j in jobs[:8])
        + (f"\n  … +{len(jobs)-8} more" if len(jobs) > 8 else "")
        + f"\n\n⏰ {datetime.now().strftime('%H:%M')}"
    )
    return send(msg, settings)


# ── Discovery complete ────────────────────────────────────────────────────────

def notify_discovery_complete(
    new: int,
    updated: int,
    sources: list[str],
    errors: int = 0,
    settings: dict | None = None,
) -> dict:
    src_str = ", ".join(sources)
    msg = (
        f"🔍 <b>Discovery Complete</b>\n\n"
        f"Sources: <code>{src_str}</code>\n"
        f"New jobs: <b>+{new}</b>\n"
        f"Updated: {updated}\n"
        + (f"Errors: {errors}\n" if errors else "")
        + f"⏰ {datetime.now().strftime('%H:%M')}"
    )
    return send(msg, settings)


# ── Apply events ──────────────────────────────────────────────────────────────

def notify_apply_started(
    title: str,
    company: str,
    portal: str,
    settings: dict | None = None,
) -> dict:
    msg = (
        f"▶️ <b>Applying Now</b>\n\n"
        f"<b>{title}</b>\n"
        f"@ {company} · <code>{portal}</code>\n"
        f"⏰ {datetime.now().strftime('%H:%M')}"
    )
    return send(msg, settings)


def notify_apply_done(
    title: str,
    company: str,
    status: str,
    settings: dict | None = None,
) -> dict:
    emoji = "✅" if status == "submitted" else "⚠️"
    msg = (
        f"{emoji} <b>Application {status.replace('_',' ').title()}</b>\n\n"
        f"<b>{title}</b> @ {company}\n"
        f"⏰ {datetime.now().strftime('%H:%M')}"
    )
    return send(msg, settings)


def notify_prepare_done(
    title: str,
    company: str,
    settings: dict | None = None,
) -> dict:
    msg = (
        f"📄 <b>Artifacts Ready</b>\n\n"
        f"Resume + cover letter generated for:\n"
        f"<b>{title}</b> @ {company}\n"
        f"⏰ {datetime.now().strftime('%H:%M')}"
    )
    return send(msg, settings)


def notify_campaign_started(
    target_total: int,
    openai_target: int,
    gemini_target: int,
    claude_target: int,
    tomorrow_target: int,
    settings: dict | None = None,
) -> dict:
    msg = (
        f"🚀 Campaign Started\n\n"
        f"Target: {target_total} jobs\n"
        f"OpenAI: {openai_target} | Gemini: {gemini_target} | Claude: {claude_target}\n"
        f"Tomorrow target: {tomorrow_target}\n"
        f"High-fit ATS roles are being tailored and submitted."
    )
    _send_openclaw(msg, settings)
    return send(msg.replace("\n", "\n"), settings)


def notify_campaign_assistance(
    title: str,
    company: str,
    reason: str,
    progress: str,
    settings: dict | None = None,
) -> dict:
    msg = (
        f"🛟 ACTION NEEDED — Campaign Blocked\n\n"
        f"Progress: {progress}\n"
        f"{title} @ {company}\n"
        f"Reason: {reason[:220]}\n\n"
        f"Open job-applier to resolve."
    )
    _send_openclaw(msg, settings)
    return send(msg, settings)


def notify_campaign_done(
    submitted: int,
    assistance: int,
    failed: int,
    tomorrow_target: int,
    settings: dict | None = None,
) -> dict:
    msg = (
        f"✅ Campaign Done\n\n"
        f"Submitted: {submitted}\n"
        f"Need assistance: {assistance}\n"
        f"Failed: {failed}\n"
        f"Tomorrow target: {tomorrow_target}\n\n"
        f"Check moyosorejobi@gmail.com for confirmations."
    )
    _send_openclaw(msg, settings)
    return send(msg, settings)


def notify_interview(
    title: str,
    company: str,
    details: str = "",
    settings: dict | None = None,
) -> dict:
    """Fire when an interview invite is detected in email."""
    msg = (
        f"🎯 INTERVIEW INVITE DETECTED\n\n"
        f"{title} @ {company}\n"
        f"{details[:300]}\n\n"
        f"Check moyosorejobi@gmail.com immediately."
    )
    _send_openclaw(msg, settings)
    return send(msg, settings)
