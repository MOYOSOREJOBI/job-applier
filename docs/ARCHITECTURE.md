# Architecture

## Overview

```
job-applier/
├── backend/          FastAPI server (port 7700)
├── engine/
│   ├── sources/      Job discovery adapters (Greenhouse, Lever, Ashby, GitHub, URL, text)
│   ├── scoring/      8-dimension weighted scorer
│   ├── artifacts/    Resume + cover letter + answer pack generator (local/LLM + WeasyPrint)
│   └── apply/        Browser-assisted apply (Playwright)
├── storage/          SQLite persistence (jobs.db)
├── frontend/         React + Vite UI (port 5174)
├── artifacts/        Generated PDFs
└── logs/             Backend log, frontend log, screenshots
```

## Data Flow

```
DISCOVER → score → upsert to DB → notify UI via SSE
EVALUATE → read scored jobs, filter by fit_band/portal
PREPARE  → local engine or LLM provider → resume_md + cover_letter + answer_pack → WeasyPrint → PDFs
ASSIST APPLY → Playwright opens browser → map fields → fill safe fields → confirm → submit
```

## Backend (FastAPI)

- All endpoints under `/api/`
- SQLite via `get_conn()` — synchronous sqlite3 (thread-safe)
- Discovery runs in a background thread, streams logs via SSE at `/api/run/logs`
- Browser sessions stored in-memory dict `_active_sessions` — one per apply workflow

## Database Schema

| Table | Purpose |
|---|---|
| `jobs` | All discovered jobs with score, fit_band, portal, support_tier |
| `applications` | Tracked apply attempts per job |
| `artifacts` | Paths to generated PDFs and answer packs |
| `runs` | Discovery run history |
| `notifications` | Alerts for new jobs, artifact ready, etc. |
| `settings` | Key-value config (MIN_SCORE, etc.) |

## Scoring (8 dimensions, 100 pts max)

| Dimension | Max | Signal |
|---|---|---|
| title_match | 20 | intern/co-op/SWE keywords; penalizes senior |
| seniority_fit | 20 | intern/student/new-grad signals in title + desc |
| location_fit | 15 | Calgary=15, Alberta=12, Remote Canada=12, Remote=9 |
| skill_fit | 20 | Python/Java/AWS/Docker/SQL keyword hits |
| internship_relevance | 10 | "summer 2026", "co-op", "4 months" etc. |
| recency | 5 | Posted within 7 days = 4-5 pts |
| application_friction | 5 | Tier A ATS (greenhouse/lever/ashby) = 5 pts |
| company_signal | 5 | Known tech/Calgary employers bonus |

Fit bands: **strong** ≥75 · **good** ≥55 · **weak** ≥35 · **poor** <35

## Support Tiers

| Tier | Portals | Apply Mode |
|---|---|---|
| A | Greenhouse, Lever, Ashby | ASSISTED_FILL (auto-fill + confirm gate) |
| B | Workday, iCIMS | ASSISTED_FILL (extra checkpoints) |
| C | GitHub repo, text import | PREP_ONLY (PDF prep only) |
| BLOCKED | LinkedIn | Rejected — apply manually |

## LinkedIn Policy

LinkedIn is **permanently disabled** at every layer:
- No LinkedIn source adapter
- No LinkedIn in .env
- `/api/status` returns `linkedin_disabled: true`
- `assist-apply` blocks `linkedin.com` URLs with an error
- UI shows permanent red warning banners
