#!/usr/bin/env bash
BASE="$(cd "$(dirname "$0")" && pwd)"
echo "=== Job Applier Doctor ==="
PASS=0; FAIL=0

check() {
  local label="$1"
  local cmd="$2"
  if eval "$cmd" > /dev/null 2>&1; then
    echo "  ✓ $label"
    ((PASS++))
  else
    echo "  ✗ $label"
    ((FAIL++))
  fi
}

echo "Python environment:"
check "Python 3" "python3 --version"
check "FastAPI" "python3 -c 'import fastapi'"
check "Uvicorn" "python3 -c 'import uvicorn'"
check "Anthropic" "python3 -c 'import anthropic'"
check "Playwright" "python3 -c 'from playwright.sync_api import sync_playwright'"
check "WeasyPrint" "python3 -c 'import weasyprint'"
check "Requests" "python3 -c 'import requests'"
check "BeautifulSoup" "python3 -c 'from bs4 import BeautifulSoup'"
check "PyYAML" "python3 -c 'import yaml'"

echo ""
echo "Frontend:"
check "Node.js" "node --version"
check "npm" "npm --version"
check "node_modules" "test -d '$BASE/frontend/node_modules'"

echo ""
echo "Files:"
check ".env exists" "test -f '$BASE/.env'"
check "backend/server.py" "test -f '$BASE/backend/server.py'"
check "storage/db.py" "test -f '$BASE/storage/db.py'"
check "engine/sources/greenhouse.py" "test -f '$BASE/engine/sources/greenhouse.py'"
check "engine/artifacts/generator.py" "test -f '$BASE/engine/artifacts/generator.py'"
check "artifacts/ dir" "test -d '$BASE/artifacts'"
check "logs/ dir" "test -d '$BASE/logs'"

echo ""
echo "Database:"
check "DB bootstrap" "cd '$BASE' && python3 -c \"import sys; sys.path.insert(0,'.'); from storage.db import bootstrap, seed_settings; bootstrap(); seed_settings(); print('ok')\""

echo ""
echo "Artifact engine:"
if (cd "$BASE" && python3 - <<'PY' >/dev/null 2>&1
import os
from dotenv import load_dotenv
from storage.db import get_setting

load_dotenv(".env")
mode = (get_setting("ARTIFACT_ENGINE_MODE", "") or os.getenv("ARTIFACT_ENGINE_MODE", "deterministic")).strip().lower()
if mode not in {"deterministic", "llm"}:
    raise SystemExit(f"Unknown ARTIFACT_ENGINE_MODE: {mode}")
if mode == "llm":
    keys = [
        os.getenv("CLAUDE_API_KEY", ""),
        os.getenv("ANTHROPIC_API_KEY", ""),
        os.getenv("OPENAI_API_KEY", ""),
        os.getenv("GEMINI_API_KEY", ""),
        os.getenv("GOOGLE_API_KEY", ""),
    ]
    if not any(k and not k.startswith("PASTE_YOUR_") for k in keys):
        raise SystemExit("LLM mode requires an API key")
PY
); then
  echo "  ✓ Artifact engine configured"
  ((PASS++))
else
  echo "  ✗ Artifact engine not configured. Use deterministic mode or add a Claude, OpenAI, or Gemini key."
  ((FAIL++))
fi

echo ""
echo "Playwright browser:"
check "Chromium browser launch" "python3 -c 'from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); b.close(); p.stop()'"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [ $FAIL -eq 0 ]; then echo "System is ready."; else echo "Fix the items above, then re-run doctor.sh"; fi
