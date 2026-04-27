"""
SQLite database bootstrap and connection management.
Single file — no ORM, no migrations framework. Schema is created fresh if absent.
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "jobs.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA wal_autocheckpoint=400")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id                    TEXT PRIMARY KEY,
    source                TEXT NOT NULL,
    source_type           TEXT NOT NULL DEFAULT 'api',
    portal                TEXT,
    company               TEXT,
    title                 TEXT,
    location              TEXT,
    remote_type           TEXT,
    url                   TEXT,
    description_raw       TEXT,
    description_normalized TEXT,
    posted_at             TEXT,
    first_seen_at         TEXT NOT NULL,
    last_seen_at          TEXT NOT NULL,
    score                 REAL DEFAULT 0,
    score_breakdown       TEXT DEFAULT '{}',
    fit_band              TEXT DEFAULT 'unknown',
    support_tier          TEXT DEFAULT 'C',
    apply_mode            TEXT DEFAULT 'PREP_ONLY',
    status                TEXT DEFAULT 'discovered',
    manual_only           INTEGER DEFAULT 0,
    restricted_reason     TEXT,
    automation_tier       TEXT DEFAULT '',
    automation_reason     TEXT DEFAULT '',
    automation_viability_score REAL DEFAULT 0,
    automation_viability_band  TEXT DEFAULT '',
    automation_viability_reasons TEXT DEFAULT '[]',
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS applications (
    id                       TEXT PRIMARY KEY,
    job_id                   TEXT NOT NULL REFERENCES jobs(id),
    stage                    TEXT DEFAULT 'prep',
    apply_mode               TEXT DEFAULT 'PREP_ONLY',
    browser_session_id       TEXT,
    submitted_at             TEXT,
    failure_reason           TEXT,
    review_required          INTEGER DEFAULT 1,
    final_confirmation_given INTEGER DEFAULT 0,
    confirmation_text       TEXT DEFAULT '',
    confirmation_screenshot_path TEXT DEFAULT '',
    uploaded_resume_path    TEXT DEFAULT '',
    uploaded_cover_letter_path TEXT DEFAULT '',
    answers_json            TEXT DEFAULT '{}',
    notes                    TEXT,
    created_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    id          TEXT PRIMARY KEY,
    job_id      TEXT NOT NULL REFERENCES jobs(id),
    type        TEXT NOT NULL,
    path        TEXT NOT NULL,
    checksum    TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id              TEXT PRIMARY KEY,
    mode            TEXT NOT NULL,
    state           TEXT DEFAULT 'running',
    source_scope    TEXT,
    counters        TEXT DEFAULT '{}',
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    config_snapshot TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS notifications (
    id         TEXT PRIMARY KEY,
    type       TEXT NOT NULL,
    job_id     TEXT REFERENCES jobs(id),
    message    TEXT NOT NULL,
    seen       INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaigns (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    state             TEXT DEFAULT 'running',
    target_total      INTEGER NOT NULL,
    target_openai     INTEGER DEFAULT 0,
    target_gemini     INTEGER DEFAULT 0,
    target_claude     INTEGER DEFAULT 0,
    tomorrow_target   INTEGER DEFAULT 0,
    selected_count    INTEGER DEFAULT 0,
    prepared_count    INTEGER DEFAULT 0,
    submitted_count   INTEGER DEFAULT 0,
    assistance_count  INTEGER DEFAULT 0,
    failed_count      INTEGER DEFAULT 0,
    auto_submit       INTEGER DEFAULT 0,
    min_score         REAL DEFAULT 0,
    notes             TEXT DEFAULT '',
    started_at        TEXT NOT NULL,
    ended_at          TEXT
);

CREATE TABLE IF NOT EXISTS campaign_rows (
    id                  TEXT PRIMARY KEY,
    campaign_id         TEXT NOT NULL REFERENCES campaigns(id),
    job_id              TEXT NOT NULL REFERENCES jobs(id),
    rank                INTEGER NOT NULL,
    provider_target     TEXT NOT NULL,
    provider_used       TEXT,
    stage               TEXT DEFAULT 'queued',
    assistance_required INTEGER DEFAULT 0,
    application_id      TEXT,
    error               TEXT,
    details             TEXT DEFAULT '{}',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS application_memory (
    id                          TEXT PRIMARY KEY,
    job_id                      TEXT NOT NULL REFERENCES jobs(id),
    company                     TEXT NOT NULL,
    title                       TEXT NOT NULL,
    resume_md                   TEXT DEFAULT '',
    cover_letter                TEXT DEFAULT '',
    answer_pack                 TEXT DEFAULT '{}',
    study_plan                  TEXT DEFAULT '',
    key_claims                  TEXT DEFAULT '',
    linkedin_connection_request TEXT DEFAULT '',
    linkedin_inmail             TEXT DEFAULT '',
    recruiter_email             TEXT DEFAULT '',
    submitted                   INTEGER DEFAULT 0,
    created_at                  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS domain_memory (
    domain                   TEXT PRIMARY KEY,
    portal                   TEXT,
    success_count            INTEGER DEFAULT 0,
    fail_count               INTEGER DEFAULT 0,
    assisted_count           INTEGER DEFAULT 0,
    captcha_count            INTEGER DEFAULT 0,
    login_required_count     INTEGER DEFAULT 0,
    email_verification_count INTEGER DEFAULT 0,
    avg_duration_sec         REAL,
    last_status              TEXT,
    last_reason              TEXT,
    selectors_json           TEXT DEFAULT '{}',
    updated_at               TEXT
);

CREATE TABLE IF NOT EXISTS email_events (
    id           TEXT PRIMARY KEY,
    subject      TEXT,
    sender       TEXT,
    status       TEXT NOT NULL,
    received_at  TEXT NOT NULL,
    body_snippet TEXT,
    job_id       TEXT REFERENCES jobs(id),
    seen         INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_jobs_status        ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_score         ON jobs(score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_source        ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen    ON jobs(first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_artifacts_job      ON artifacts(job_id);
CREATE INDEX IF NOT EXISTS idx_notifications_seen ON notifications(seen, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_campaigns_started   ON campaigns(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_rows_run   ON campaign_rows(campaign_id, rank);
CREATE INDEX IF NOT EXISTS idx_campaign_rows_stage ON campaign_rows(stage, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_memory_company ON application_memory(company, title);
CREATE INDEX IF NOT EXISTS idx_domain_memory_portal ON domain_memory(portal, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_events_status ON email_events(status, received_at DESC);
"""


def bootstrap():
    """Create schema if not exists. Safe to call on every startup."""
    conn = get_conn()
    conn.executescript(SCHEMA)
    campaign_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(campaigns)").fetchall()
    }
    if "target_claude" not in campaign_columns:
        conn.execute("ALTER TABLE campaigns ADD COLUMN target_claude INTEGER DEFAULT 0")
    job_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
    }
    for column, definition in {
        "automation_tier": "TEXT DEFAULT ''",
        "automation_reason": "TEXT DEFAULT ''",
        "automation_viability_score": "REAL DEFAULT 0",
        "automation_viability_band": "TEXT DEFAULT ''",
        "automation_viability_reasons": "TEXT DEFAULT '[]'",
    }.items():
        if column not in job_columns:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} {definition}")
    application_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(applications)").fetchall()
    }
    for column, definition in {
        "confirmation_text": "TEXT DEFAULT ''",
        "confirmation_screenshot_path": "TEXT DEFAULT ''",
        "uploaded_resume_path": "TEXT DEFAULT ''",
        "uploaded_cover_letter_path": "TEXT DEFAULT ''",
        "answers_json": "TEXT DEFAULT '{}'",
    }.items():
        if column not in application_columns:
            conn.execute(f"ALTER TABLE applications ADD COLUMN {column} {definition}")
    # Force-update mutable defaults so existing DBs pick up the new values
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('DAILY_CAP','120')")
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('DRY_RUN_DEFAULT','false')")
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('MIN_SCORE','30')")
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('ARTIFACT_ENGINE_MODE','deterministic')")
    conn.commit()
    conn.close()


def default_settings() -> dict:
    return {
        "CLAUDE_API_KEY": "",
        "CLAUDE_MODEL": "claude-sonnet-4-6",
        "DAILY_CAP": "120",
        "DRY_RUN_DEFAULT": "false",
        "TARGET_LOCATIONS": "Calgary,Alberta,Canada Remote",
        "TARGET_ROLES": "Software Engineer Intern,Software Developer Intern,Backend Engineer Intern,Full Stack Developer Intern,Data Science Intern,Machine Learning Intern,AI Engineer Intern,Cloud Engineer Intern,DevOps Intern,Data Engineer Intern,QA Automation Intern",
        "NEGATIVE_KEYWORDS": "senior,staff,principal,director,manager,physician,nurse,accountant,civil technician",
        "MIN_SCORE": "30",
        "BROWSER_HEADLESS": "false",
        "ARTIFACTS_DIR": str(Path(__file__).parent.parent / "artifacts"),
        "ARTIFACT_ENGINE_MODE": "deterministic",
        "PROFILE_QA_JSON": "{}",
        # OpenAI (fallback — uses o3)
        "OPENAI_API_KEY": "",
        # Gemini (fallback — uses gemini-2.5-pro)
        "GEMINI_API_KEY": "",
        # Telegram notifications
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
    }


def seed_settings():
    """Insert default settings if not already present."""
    conn = get_conn()
    defaults = default_settings()
    for k, v in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
        )
    conn.commit()
    conn.close()


def get_setting(key: str, fallback: str = "") -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else fallback


def set_setting(key: str, value: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
    )
    conn.commit()
    conn.close()


def all_settings() -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}
