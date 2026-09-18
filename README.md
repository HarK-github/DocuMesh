# PDF Annotation and Relationship Graph

A web application where users upload text-based PDFs, highlight passages, link highlights with typed relationships visualized as an interactive graph, and receive smart highlight and relation suggestions.

## Key Features
- **PDF Ingestion & Text Extraction**: Extracts clean text, normalizes sentences, and tracks exact character offsets (`POST /documents`, `GET /documents/{id}`, `GET /documents/{id}/text`).
- **Deduplication & Safety**: Instant SHA-256 deduplication and upload size/page limits.
- **Background Jobs**: Tracked jobs with progress tracking and failure logging (`GET /jobs/{id}`).
- **Interactive Annotation**: Full CRUD for annotations with offset verification and quote matching (`GET|POST /documents/{id}/annotations`, `PATCH|DELETE /annotations/{id}`).
- **Relationship Knowledge Graph**: Typed relations and unified graph view with cycle and taxonomy checks (`GET|POST /documents/{id}/relations`, `PATCH|DELETE /relations/{id}`, `GET /documents/{id}/graph`).
- **Taxonomy Management**: Seeded taxonomy labels and relation types (`GET /taxonomy`).
- **Smart Highlights**: Vector embedding similarity to suggest relevant passages based on current annotations and user feedback.
- **Suggested Relations**: LLM-assisted relationship suggestions between annotations.
- **Job Tracking & Robust Concurrency**: Background job processing with progress tracking, SQLite WAL, and versioned optimistic locking.

## Stack
- **Backend**: FastAPI, SQLite (SQLAlchemy WAL mode), PyMuPDF, pysbd, sentence-transformers, numpy.
- **Frontend**: React, Vite, pdfjs-dist, React Flow, dagre, TanStack Query.

## Quick Start

### Backend Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Running Tests
- Backend: `pytest`
- Frontend: `npm test` (inside `frontend/`)
