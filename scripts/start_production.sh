#!/usr/bin/env bash
set -e

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

echo "=========================================================="
echo " Starting PDF Annotation & Knowledge Graph in Production "
echo "=========================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

# 1. Check Python virtual environment
if [ -d ".venv" ]; then
    PYTHON_BIN=".venv/bin/python"
    UVICORN_BIN=".venv/bin/uvicorn"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
    UVICORN_BIN="uvicorn"
else
    echo "Error: Python 3 not found."
    exit 1
fi

# 2. Build frontend if dist doesn't exist
if [ ! -d "frontend/dist" ] || [ ! -f "frontend/dist/index.html" ]; then
    echo "Building React frontend production bundle..."
    cd frontend
    npm install
    npm run build
    cd "${ROOT_DIR}"
fi

# 3. Seed database if not yet initialized
if [ ! -f "data/app.db" ]; then
    echo "Seeding initial document and annotations..."
    "${PYTHON_BIN}" backend/seed.py || echo "Warning: Seed step skipped or already present."
fi

echo "Serving unified application on http://${HOST}:${PORT}"
echo "Press Ctrl+C to terminate."
exec "${UVICORN_BIN}" backend.app.main:app --host "${HOST}" --port "${PORT}"
