#!/usr/bin/env bash
# Launches the VARUNA app: FastAPI backend serving the built React frontend
# as a single process on http://localhost:8000
set -e
cd "$(dirname "$0")"

if [ ! -d "frontend/dist" ]; then
  echo "Frontend not built yet — building now..."
  (cd frontend && npm install && npm run build)
fi

if [ ! -d ".venv" ]; then
  echo "Python venv not found — creating one and installing requirements..."
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -r requirements.lock
else
  . .venv/bin/activate
fi

echo "Starting VARUNA at http://localhost:8000"
uvicorn backend.app:app --host 0.0.0.0 --port 8000
