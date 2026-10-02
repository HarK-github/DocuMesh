# Multi-stage Dockerfile for PDF Annotation & Knowledge Graph Web App
# Stage 1: Build the React single-page frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci || npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python runtime
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch to minimize container size and RAM footprint
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install application requirements
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend codebase, taxonomy configuration, and sample files
COPY backend/ ./backend/
COPY config/ ./config/
COPY sample/ ./sample/

# Copy compiled frontend assets from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create storage directories with write permissions
RUN mkdir -p uploads data && chmod -R 777 uploads data

# Copy entrypoint script
COPY scripts/entrypoint.sh ./scripts/entrypoint.sh
RUN chmod +x ./scripts/entrypoint.sh

EXPOSE 7860

ENTRYPOINT ["./scripts/entrypoint.sh"]
