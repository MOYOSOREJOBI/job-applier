# API Reference

Base URL: `http://localhost:7700`

All endpoints return JSON. LinkedIn is disabled at the API level (`linkedin_disabled: true` in `/api/status`).

---

## Status & Health

### `GET /api/status`
System overview.
```json
{
  "total_jobs": 2435,
  "total_applications": 0,
  "running": false,
  "linkedin_disabled": true,
  "version": "2.0.0"
}
```

### `GET /api/health`
Liveness check.
```json
{"status": "ok", "db": true, "linkedin_disabled": true, "version": "2.0.0"}
```

---

## Jobs

### `GET /api/jobs`
List jobs with optional filters.

Query params:
| Param | Type | Description |
|---|---|---|
| `status` | string | `discovered`, `applied`, `rejected`, etc. |
| `source` | string | Filter by source prefix (e.g., `greenhouse`) |
| `portal` | string | `greenhouse`, `lever`, `ashby` |
| `fit_band` | string | `strong`, `good`, `weak`, `poor` |
| `support_tier` | string | `A`, `B`, `C` |
| `min_score` | float | Minimum score (0–100) |
| `new_only` | bool | Only jobs seen in last 24h |
| `artifact_ready` | bool | Only jobs with generated PDFs |
| `search` | string | Full-text search in title/company/location |
| `limit` | int | Max results (default 200) |
| `offset` | int | Pagination offset |

Response: `{jobs: [...], total: N, returned: N}`

### `GET /api/jobs/{id}`
Single job by ID.

### `GET /api/jobs/{id}/artifacts`
List generated artifacts (PDFs, answer packs) for a job.

### `GET /api/jobs/{id}/application-map`
Return field mapping + proposed values for ASSIST APPLY preview.

### `POST /api/jobs/{id}/prepare`
Generate resume PDF + cover letter PDF + answer pack. The default deterministic engine requires no LLM key. If `ARTIFACT_ENGINE_MODE=llm`, configure `CLAUDE_API_KEY`, `OPENAI_API_KEY`, or `GEMINI_API_KEY`.

Returns: `{ok, resume_md, cover_letter, answer_pack, resume_pdf_path, cover_pdf_path}`

### `POST /api/jobs/{id}/assist-apply`
Open a supervised Playwright browser session.

Body: `{"headless": false}`

Returns: `{ok, session_id, application_id, fields_mapped, fields_filled, fields_skipped, review: {...}}`

The browser opens visibly (or headless if `headless: true`). Fields are auto-filled where safe. A confirmation gate is required before submission.

### `POST /api/jobs/{id}/confirm-submit`
Confirm and trigger final form submission for an active session.

Body: `{"session_id": "...", "confirmed": true}`

---

## Discovery

### `POST /api/discovery/trigger`
Start a background discovery run.

Body: `{"sources": ["greenhouse", "lever", "ashby"]}` (omit to run all)

### `POST /api/discovery/import-url`
Import a single job from a URL.

Body: `{"url": "https://jobs.lever.co/company/..."}`

### `POST /api/discovery/import-text`
Import a job from pasted text.

Body: `{"text": "...", "title_hint": "SWE Intern", "company_hint": "Acme"}`

---

## Run / SSE

### `POST /api/run/start`
Start a discovery run (alias for trigger).

### `POST /api/run/stop`
Stop a running discovery.

### `GET /api/run/logs`
Server-Sent Events stream of discovery log lines.
Subscribe: `const es = new EventSource('/api/run/logs')`

---

## Other

### `GET /api/sources`
List all configured sources with tier, status, enabled/disabled.

### `POST /api/sources/test`
Test a source adapter (returns job count).

### `GET /api/pdfs`
List all generated artifact files.

### `GET /api/notifications`
List all notifications (new jobs, artifact ready, etc.).

### `POST /api/notifications/mark-seen`
Mark notifications as seen. Body: `{"ids": [...]}`

### `GET /api/settings`
Return all configurable settings.

### `POST /api/settings`
Update a setting. Body: `{"key": "MIN_SCORE", "value": "65"}`
