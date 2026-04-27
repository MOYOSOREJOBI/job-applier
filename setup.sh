#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")" && pwd)"
echo "=== Job Applier Setup ==="
echo "Base directory: $BASE"

# 1. Check Python
python3 --version || { echo "ERROR: Python 3 required"; exit 1; }

# 2. Install Python dependencies
echo "Installing Python dependencies..."
pip3 install --break-system-packages --quiet \
  "fastapi>=0.115.0" "uvicorn" "anthropic>=0.40.0" \
  "playwright>=1.44.0" "weasyprint" "requests" "beautifulsoup4" \
  "python-dotenv" "rich" "pyyaml" "aiosqlite" 2>&1 | tail -3

# 3. Install Playwright browser
echo "Installing Playwright Chromium..."
python3 -m playwright install chromium --with-deps 2>&1 | tail -5 || echo "(playwright browser install may need manual: python3 -m playwright install chromium)"

# 4. Install frontend deps
echo "Installing frontend dependencies..."
cd "$BASE/frontend"
npm install --silent 2>&1 | tail -3

# 5. Create .env if missing
cd "$BASE"
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from template. Add your CLAUDE_API_KEY."
fi

# 6. Bootstrap DB
echo "Bootstrapping database..."
cd "$BASE"
python3 -c "
import sys
sys.path.insert(0, '.')
from storage.db import bootstrap, seed_settings
bootstrap()
seed_settings()
print('Database ready.')
"

# 7. Create required directories
mkdir -p artifacts logs storage

echo ""
echo "=== Setup complete ==="
echo ""
echo "NEXT STEPS:"
echo "  1. Add your CLAUDE_API_KEY to .env"
echo "  2. Start backend:  python3 backend/server.py"
echo "  3. Start frontend: cd frontend && npm run dev"
echo "  4. Open: http://localhost:5174"
echo "  5. Go to Discover tab and run discovery"
