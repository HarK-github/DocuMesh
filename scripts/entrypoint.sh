#!/bin/sh
set -e

PORT="${PORT:-7860}"

# Render Free Tier provides 512MB RAM. PyTorch SentenceTransformers requires >800MB RSS.
# Default to FakeEmbedder to prevent OOM SIGKILL unless explicitly overridden.
if [ -n "$RENDER" ] && [ -z "$EMBEDDING_MODEL_NAME" ]; then
    echo "Running on Render. Defaulting EMBEDDING_MODEL_NAME=fake to stay within 512MB RAM limit."
    export EMBEDDING_MODEL_NAME="fake"
fi

echo "Starting PDF Annotation & Knowledge Graph application on port ${PORT}..."

echo "Applying database migrations..."
python3 -m alembic upgrade head || echo "Warning: Alembic migration step completed or skipped."

echo "Seeding initial data (idempotent)..."
python3 backend/seed.py || echo "Warning: Seed script completed or skipped."

exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT}"
