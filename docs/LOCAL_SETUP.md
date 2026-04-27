# Local Setup Guide

## Prerequisites

- macOS (tested on macOS 14+)
- Python 3.10+
- Node.js 18+
- Git

## Quick Start

```bash
cd job-applier

# 1. Install Python dependencies
pip3 install --break-system-packages \
  fastapi uvicorn aiofiles aiosqlite requests \
  playwright anthropic python-dotenv weasyprint \
  beautifulsoup4

# 2. Install Playwright browser
python3 -m playwright install chromium

# 3. Install frontend dependencies
cd frontend && npm install && cd ..

# 4. Configure environment
cp .env.example .env
# Default ARTIFACT_ENGINE_MODE=deterministic works without an LLM key.
# For LLM mode, add CLAUDE_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY.

# 5. Start
./START.sh
```

Then open http://localhost:5174 in your browser.

## Manual Start (alternative)

```bash
# Terminal 1 — Backend
PYTHONPATH=$(pwd) python3 -m uvicorn backend.server:app --host 127.0.0.1 --port 7700

# Terminal 2 — Frontend
cd frontend && npm run dev
```

## Configuration (.env)

| Variable | Required | Description |
|---|---|---|
| `ARTIFACT_ENGINE_MODE` | No | `deterministic` by default. Use `llm` to generate with external providers. |
| `CLAUDE_API_KEY` | Only for LLM mode | Anthropic API key from console.anthropic.com |
| `OPENAI_API_KEY` | Only for LLM mode | OpenAI API key for OpenAI artifact generation |
| `GEMINI_API_KEY` | Only for LLM mode | Gemini API key for Gemini artifact generation |
| `CLAUDE_MODEL` | No | Override Claude model when using Claude |

## Verify Setup

```bash
# Health check
curl http://localhost:7700/api/health

# Smoke test
python3 smoke_test.py
```

## Common Issues

**`No module named 'backend'`**
Run with `PYTHONPATH=$(pwd) python3 -m uvicorn backend.server:app ...` from the project root.

**Frontend blank page**
Check `logs/frontend.log`. Reinstall: `cd frontend && rm -rf node_modules && npm install`.

**Playwright crashes in async context**
This is handled automatically — the apply engine resets the event loop before launching Playwright.

**WeasyPrint missing**
`pip3 install --break-system-packages weasyprint`
