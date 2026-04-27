# Job Applier v2

A production-ready local job application assistant for Moyosore Ogunjobi.

**What it does:**
- Discovers real software internship/co-op postings from Greenhouse, Lever, and Ashby job boards
- Scores each job on 8 dimensions with Calgary-first weighting
- Generates tailored resume PDFs, cover letters, and answer packs with the deterministic local engine by default, or LLM providers in LLM mode
- Opens a supervised Playwright browser to assist with form filling (you confirm before any submit)
- Runs Co-op Emergency Mode for high-volume deadline pushes: discover up to 500 jobs, prepare up to 200 application packs, split into two 100-job batches, auto-submit only where the central safety policy allows it, and export a school proof CSV

**LinkedIn is permanently disabled.** This system does not touch LinkedIn in any form.

---

## Quick Start

```bash
# Install dependencies
pip3 install --break-system-packages fastapi uvicorn requests playwright anthropic python-dotenv weasyprint beautifulsoup4
python3 -m playwright install chromium
cd frontend && npm install && cd ..

# Configure environment
cp .env.example .env
# Default ARTIFACT_ENGINE_MODE=deterministic works without an LLM key.
# For LLM mode, add CLAUDE_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY.

# Start
./START.sh
# Then open http://localhost:5174
```

### Co-op Emergency Runner

```bash
python -m engine.campaign_runner --mode coop_emergency --discover 500 --prepare 200 --batch-size 100
```

The runner creates clean application folders under `applications/YYYY-MM-DD/company_slug/job_slug/` and writes `logs/coop_emergency_latest.csv` for school/co-op proof. The dashboard also has a **Co-op Emergency** tab with a CSV proof log button.

Safety policy: no CAPTCHA bypassing, no LinkedIn/Indeed/Glassdoor apply automation, no login/account/email-verification submission, no guessed required answers, and no auto-submit without resume PDF, cover letter PDF, answer pack, high score, clean page state, and clean domain memory.

See [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md) for detailed instructions.
See [docs/WORKSPACE_HYGIENE.md](docs/WORKSPACE_HYGIENE.md) for the cleaned workspace layout and profile source-of-truth rules.

---

## Workflow

### 1. DISCOVER
Click **Start Discovery** in the Discover tab. The system fetches live job postings from Greenhouse, Lever, and Ashby. Logs stream in real time via SSE. Jobs are scored and stored in SQLite.

### 2. EVALUATE
Browse the Jobs tab. Filter by score, fit band (strong/good/weak/poor), portal, or support tier. Top picks today: Cloudflare SWE Intern (score=75), Hootsuite Co-op (score=78), Cohere ML Intern (score=71).

### 3. PREPARE
For any job, click **PREPARE**. The system writes a tailored resume and cover letter for that specific job, then renders them as PDFs. Files are saved to `artifacts/`.

### 4. ASSIST APPLY
For supported jobs, click **ASSIST APPLY**. A visible browser opens on the job application page. The system maps form fields, proposes values from your profile, fills safe known fields, uploads clean PDFs, saves a screenshot, and stops before submit unless the central policy gate classifies the job as `SAFE_AUTO_SUBMIT`.

---

## Architecture

- **Backend:** FastAPI (port 7700) + SQLite
- **Frontend:** React + Vite (port 5174), proxies `/api/*` to backend
- **Discovery:** Greenhouse, Lever, Ashby public APIs + GitHub repo parser + URL/text import
- **Scoring:** 8-dimension weighted score, max 100 pts
- **Artifacts:** deterministic local tailoring by default, optional Claude/OpenAI/Gemini LLM mode → markdown → WeasyPrint PDF
- **Apply:** Playwright sync browser with asyncio isolation fix

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full details.

---

## Files

```
job-applier/
├── START.sh              One-command launcher
├── backend/server.py     FastAPI — all API endpoints
├── engine/
│   ├── sources/          Greenhouse, Lever, Ashby, GitHub, URL, text adapters
│   ├── scoring/scorer.py Weighted 8-dimension scorer
│   ├── artifacts/        Local/LLM + WeasyPrint PDF generator
│   └── apply/            Playwright browser session
├── storage/db.py         SQLite bootstrap and helpers
├── frontend/src/App.jsx  React UI
├── artifacts/            Generated PDFs (gitignored)
├── logs/                 backend.log, frontend.log, screenshots/
└── docs/                 Architecture, API, Apply Modes, Setup, Go-Live checklist
```

---

## Acceptance Test Results

14/15 tests pass. Run `python3 smoke_test.py` for a quick check.

Full results: [docs/GO_LIVE_CHECKLIST.md](docs/GO_LIVE_CHECKLIST.md)

---

## Current Verdict: B+ (Ready For Local Supervised Use)

All core infrastructure is built and working. Deterministic artifact generation works without an LLM key; LLM mode requires a Claude, OpenAI, or Gemini API key in `.env` or Settings.
