#!/bin/sh
set -e

PORT="${PORT:-7860}"

echo "Starting PDF Annotation & Knowledge Graph application on port ${PORT}..."

# Initialize and seed database if data/app.db does not exist
if [ ! -f "data/app.db" ]; then
    echo "Initializing database and seeding sample document..."
    python3 backend/seed.py || echo "Warning: Seed script completed or skipped."
fi

exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT}"
