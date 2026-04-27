#!/usr/bin/env bash
# START.sh — Launch backend + frontend for job-applier v2
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

mkdir -p "$ROOT/logs"

# Kill any existing instances on our ports
lsof -ti:7700 | xargs kill -9 2>/dev/null || true
lsof -ti:5174 | xargs kill -9 2>/dev/null || true
sleep 1

echo "=== Job Applier — Starting ==="
echo "Backend  -> http://localhost:7700"
echo "Frontend -> http://localhost:5174"
echo ""

# Bootstrap DB
PYTHONPATH="$ROOT" python3 -c "from storage.db import bootstrap; bootstrap(); print('DB ready.')"

# Start backend
PYTHONPATH="$ROOT" python3 -m uvicorn backend.server:app \
  --host 127.0.0.1 --port 7700 \
  > "$ROOT/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo -n "Waiting for backend..."
for i in $(seq 1 20); do
  if curl -sf http://localhost:7700/api/health > /dev/null 2>&1; then
    echo " ready."
    break
  fi
  sleep 1
  echo -n "."
done

# Start frontend
cd "$ROOT/frontend"
npm run dev > "$ROOT/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"
cd "$ROOT"

echo ""
echo "Services started."
echo "  Backend log:  logs/backend.log"
echo "  Frontend log: logs/frontend.log"
echo ""
echo "Open http://localhost:5174 in your browser."
echo "Press Ctrl+C to stop both services."

trap "echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait $BACKEND_PID $FRONTEND_PID
