"""
Gmail Inbox Monitor — moyosorejobi@gmail.com
Monitors for job application confirmations, interview invites, rejections,
and follow-up requests. Stores results in DB and fires notifications.

Setup (one-time):
    1. Go to console.cloud.google.com → Create project → Enable Gmail API
    2. Create OAuth 2.0 credentials → Download as config/gmail_credentials.json
    3. Run: python -m engine.email_monitor --auth
       This opens a browser to authorize, saves config/gmail_token.json
    4. From then on email_monitor runs headlessly.

Alternatively: set GMAIL_APP_PASSWORD + GMAIL_EMAIL in .env to use IMAP
(Gmail App Password — simpler, no OAuth needed).
"""
from __future__ import annotations

import email as _email_lib
import imaplib
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CREDENTIALS_PATH = BASE_DIR / "config" / "gmail_credentials.json"
TOKEN_PATH = BASE_DIR / "config" / "gmail_token.json"

APPLICATION_EMAIL = "moyosorejobi@gmail.com"

# Keywords that signal an application confirmation
CONFIRMATION_SIGNALS = [
    "application received",
    "application submitted",
    "thanks for applying",
    "thank you for applying",
    "we received your application",
    "we have received your application",
    "your application has been received",
    "your application is under review",
    "successfully submitted",
    "we'll review your application",
    "we will review your application",
    "application confirmation",
    "applied for",
    "you applied",
]

# Keywords that signal an interview invite
INTERVIEW_SIGNALS = [
    "interview",
    "schedule a call",
    "schedule a chat",
    "phone screen",
    "technical screen",
    "technical interview",
    "coding assessment",
    "take-home",
    "coding challenge",
    "we'd like to meet",
    "we would like to meet",
    "next steps",
    "move forward",
    "invite you",
    "invitation to interview",
    "initial screen",
    "virtual interview",
    "on-site",
    "onsite",
    "video call",
    "zoom call",
    "teams call",
]

# Keywords that signal a rejection
REJECTION_SIGNALS = [
    "we will not be moving forward",
    "we won't be moving forward",
    "not selected",
    "not moving forward",
    "decided to move forward with other candidates",
    "we have decided not to",
    "unfortunately",
    "after careful consideration",
    "we regret to inform",
    "position has been filled",
    "no longer considering",
    "pursued other candidates",
    "not a match",
    "decline",
    "unsuccessful",
]

# Keywords for follow-up needed
FOLLOWUP_SIGNALS = [
    "please provide",
    "we need",
    "complete your application",
    "additional information",
    "missing information",
    "respond to",
    "action required",
    "urgent",
]


def _classify_email(subject: str, body: str) -> str:
    text = (subject + " " + body).lower()
    if any(s in text for s in INTERVIEW_SIGNALS):
        return "interview"
    if any(s in text for s in REJECTION_SIGNALS):
        return "rejected"
    if any(s in text for s in CONFIRMATION_SIGNALS):
        return "confirmed"
    if any(s in text for s in FOLLOWUP_SIGNALS):
        return "action_required"
    return "other"


def _extract_company_from_email(sender: str, subject: str) -> str:
    """Best-effort company name from sender domain or subject."""
    domain_match = re.search(r"@([\w-]+)\.", sender or "")
    if domain_match:
        domain = domain_match.group(1).lower()
        if domain not in ("gmail", "yahoo", "hotmail", "outlook", "mail", "greenhouse", "lever", "workday", "ashby"):
            return domain.replace("-", " ").title()
    subject_match = re.search(r"(?:from|at|@)\s+([\w\s&]+?)(?:\s+(?:team|careers|recruiting|hr))?[\.,!]", subject or "", re.I)
    if subject_match:
        return subject_match.group(1).strip()
    return "Unknown Company"


def _imap_connect() -> imaplib.IMAP4_SSL | None:
    """Connect to Gmail via IMAP using App Password."""
    app_password = os.getenv("GMAIL_APP_PASSWORD", "")
    email_addr = os.getenv("GMAIL_EMAIL", APPLICATION_EMAIL)
    if not app_password:
        try:
            from storage.db import get_setting
            app_password = get_setting("GMAIL_APP_PASSWORD", "")
            email_addr = get_setting("GMAIL_EMAIL", APPLICATION_EMAIL)
        except Exception:
            pass
    if not app_password:
        return None
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(email_addr, app_password)
        return mail
    except Exception as exc:
        print(f"[email_monitor] IMAP connect failed: {exc}", flush=True)
        return None


def _fetch_recent_emails(mail: imaplib.IMAP4_SSL, since_days: int = 3) -> list[dict]:
    """Fetch emails from the last N days."""
    from email.header import decode_header
    emails = []
    try:
        mail.select("INBOX")
        since_date = datetime.now(timezone.utc)
        from datetime import timedelta
        since_str = (since_date - timedelta(days=since_days)).strftime("%d-%b-%Y")
        _, msg_ids = mail.search(None, f'(SINCE "{since_str}")')
        ids = msg_ids[0].split() if msg_ids and msg_ids[0] else []
        for msg_id in ids[-200:]:  # cap at 200 most recent
            try:
                _, data = mail.fetch(msg_id, "(RFC822)")
                raw = data[0][1] if data and data[0] else b""
                msg = _email_lib.message_from_bytes(raw)

                subject_parts = decode_header(msg.get("Subject", ""))
                subject = ""
                for part, enc in subject_parts:
                    if isinstance(part, bytes):
                        subject += part.decode(enc or "utf-8", errors="replace")
                    else:
                        subject += part

                sender = msg.get("From", "")
                date_str = msg.get("Date", "")
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        ct = part.get_content_type()
                        if ct == "text/plain":
                            body += part.get_payload(decode=True).decode("utf-8", errors="replace")[:2000]
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="replace")[:2000]

                emails.append({
                    "msg_id": msg_id.decode(),
                    "subject": subject,
                    "sender": sender,
                    "date": date_str,
                    "body": body,
                })
            except Exception:
                continue
    except Exception as exc:
        print(f"[email_monitor] fetch error: {exc}", flush=True)
    return emails


def _save_email_event(conn, email_data: dict, classification: str, company: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO email_events
                (id, msg_id, classification, company, subject, sender, received_at, created_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                email_data["msg_id"],
                classification,
                company,
                email_data["subject"][:300],
                email_data["sender"][:200],
                email_data["date"][:100],
                now,
            ),
        )
    except Exception as exc:
        print(f"[email_monitor] DB save error: {exc}", flush=True)


def _ensure_email_events_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_events (
            id TEXT PRIMARY KEY,
            msg_id TEXT UNIQUE,
            classification TEXT,
            company TEXT,
            subject TEXT,
            sender TEXT,
            received_at TEXT,
            created_at TEXT
        )
    """)
    conn.commit()


def run_check(since_days: int = 3) -> dict:
    """
    Check Gmail inbox for application-related emails.
    Classifies each email, stores events in DB, fires notifications for interviews.
    Returns summary dict.
    """
    from storage.db import get_conn
    from engine.notifier import notify_interview, send as notify_send

    mail = _imap_connect()
    if not mail:
        print("[email_monitor] IMAP not configured. Set GMAIL_APP_PASSWORD in .env or Settings.", flush=True)
        return {"ok": False, "error": "imap_not_configured"}

    emails = _fetch_recent_emails(mail, since_days)
    mail.logout()

    conn = get_conn()
    _ensure_email_events_table(conn)

    summary = {"confirmed": 0, "interview": 0, "rejected": 0, "action_required": 0, "other": 0}
    interview_alerts = []

    for e in emails:
        classification = _classify_email(e["subject"], e["body"])
        company = _extract_company_from_email(e["sender"], e["subject"])
        _save_email_event(conn, e, classification, company)
        summary[classification] = summary.get(classification, 0) + 1

        if classification == "interview":
            interview_alerts.append((company, e["subject"]))

    conn.commit()
    conn.close()

    # Fire interview notifications
    for company, subject in interview_alerts:
        try:
            notify_interview(
                title="Interview Invite",
                company=company,
                details=subject,
            )
        except Exception as exc:
            print(f"[email_monitor] notify error: {exc}", flush=True)

    if summary.get("action_required", 0) > 0:
        try:
            notify_send(
                f"⚠️ Action Required\n\n"
                f"{summary['action_required']} application email(s) need your attention.\n"
                f"Check moyosorejobi@gmail.com."
            )
        except Exception:
            pass

    print(f"[email_monitor] checked {len(emails)} emails: {summary}", flush=True)
    return {"ok": True, "emails_checked": len(emails), **summary}


def get_recent_events(limit: int = 50) -> list[dict]:
    """Return recent classified email events from DB."""
    try:
        from storage.db import get_conn
        conn = get_conn()
        _ensure_email_events_table(conn)
        rows = conn.execute(
            "SELECT * FROM email_events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3, help="Check emails from last N days")
    args = parser.parse_args()
    result = run_check(since_days=args.days)
    print(json.dumps(result, indent=2))
