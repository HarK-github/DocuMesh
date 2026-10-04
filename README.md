# DocuMesh

**DocuMesh** is an interactive web application where users upload text-based PDFs, highlight passages, link highlights with typed relationships visualized as an interactive document mesh, and receive smart highlight and relation suggestions.
![alt text](image.png)
## Key Features
- **PDF Ingestion & Text Extraction**: Extracts clean text, normalizes sentences, and tracks exact character offsets (`POST /documents`, `GET /documents/{id}`, `GET /documents/{id}/text`).
- **Deduplication & Safety**: Instant SHA-256 deduplication and upload size/page limits.
- **Background Jobs**: Tracked jobs with progress tracking and failure logging (`GET /jobs/{id}`).
- **Interactive Annotation**: Full CRUD for annotations with offset verification and quote matching (`GET|POST /documents/{id}/annotations`, `PATCH|DELETE /annotations/{id}`).
- **Relationship Knowledge Graph**: Typed relations and unified graph view with cycle and taxonomy checks (`GET|POST /documents/{id}/relations`, `PATCH|DELETE /relations/{id}`, `GET /documents/{id}/graph`).
- **Taxonomy Management**: Seeded taxonomy labels and relation types (`GET /taxonomy`).
- **Smart Highlights**: Vector embedding similarity to suggest relevant passages based on current annotations and user feedback (`POST /documents/{id}/suggest-highlights`, `POST /suggestions/{id}/accept`, `POST /suggestions/{id}/reject`).
- **Suggested Relations**: LLM-assisted relationship suggestions between annotations (`POST /documents/{id}/suggest-relations`).
- **Job Tracking & Robust Concurrency**: Background job processing with progress tracking, SQLite WAL, and versioned optimistic locking (`409` conflict on stale edits).

## Stack
- **Backend**: Python 3.12+, FastAPI, SQLite (SQLAlchemy WAL mode with optimistic locking), PyMuPDF, pysbd, sentence-transformers, numpy.
- **Frontend**: React 19, Vite, React Flow (`reactflow`), dagre, TanStack Query (`@tanstack/react-query`), lucide-react.

## Environment Variables

All settings are configured via environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/app.db` | SQLAlchemy connection string |
| `DB_PATH` | `./data/app.db` | Path to SQLite database file |
| `UPLOAD_DIR` | `./uploads` | Directory for uploaded PDF files |
| `MAX_UPLOAD_MB` | `15` | Maximum allowed upload size in megabytes |
| `MAX_PDF_PAGES` | `50` | Maximum allowed page count per document |
| `EMBEDDING_MODEL_NAME` | `all-MiniLM-L6-v2` | Sentence transformer model or `fake` |
| `EMBED_BATCH_SIZE` | `32` | Batch size for sentence embedding |
| `SIMILARITY_THRESHOLD` | `0.35` | Minimum cosine similarity score for suggestions |
| `SUGGESTION_COUNT` | `5` | Maximum number of suggestions returned per request |
| `LLM_PROVIDER` | `fake` | Provider: `fake` or `openai` |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model for relationship extraction |
| `LLM_API_KEY` | `""` | API key (required if provider is `openai`) |
| `LLM_MAX_CONCURRENCY` | `3` | Max concurrent LLM requests via Semaphore |
| `LLM_TIMEOUT_SECONDS` | `30.0` | Timeout per LLM completion call |
| `MAX_RELATION_PAIRS` | `10` | Maximum candidate annotation pairs evaluated |
| `MAX_WORKERS` | `4` | Worker threads in ThreadPoolExecutor for background jobs |
| `SQLITE_BUSY_TIMEOUT_MS` | `5000` | SQLite WAL busy timeout in milliseconds |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Permitted CORS origin origins |
| `VITE_API_URL` | `http://localhost:8000` | Frontend API base URL |

## Quick Start

### 1. Backend Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --port 8000 --reload
```

### 2. Seed Sample Data
To ingest the sample PDF (`sample/sample.pdf`) and seed example annotations and relations:
```bash
python backend/seed.py
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

## Running Tests

All tests run cleanly with one command per side:

- **Backend tests** (includes ingestion, cleaning, offsets, ranking, concurrency, jobs, stale edits):
  ```bash
  pytest
  ```
- **Frontend tests** (includes offset mapping, multi-span selections, and API client):
  ```bash
  npm --prefix frontend test
  ```

## Performance & Load Testing

A concurrent benchmark script is included in `backend/load_test.py`:
```bash
python backend/load_test.py --url http://127.0.0.1:8000 -n 200 -c 20
```

### Benchmark Results (200 requests, Concurrency 20):
- **Throughput**: ~308.2 req/s
- **Errors**: 0 (100% success rate)
- **Latency P50**: 54.77 ms
- **Latency P95**: 102.46 ms
- **Latency P99**: 124.94 ms

## API Reference

### System & Taxonomy
- `GET /health` - Health status check (`{"status": "ok"}`)
- `GET /taxonomy` - List available annotation labels and relation types from database

### Documents
- `POST /documents` - Upload PDF (multipart/form-data). Returns `{document_id, job_id, status, filename}`. Deduplicates instantly via SHA-256 hash.
- `GET /documents/{id}` - Retrieve document metadata.
- `GET /documents/{id}/text` - Retrieve clean segmented document text.
- `GET /documents/{id}/pdf` - Stream raw PDF file for viewer.

### Annotations
- `GET /documents/{id}/annotations` - List all annotations for document.
- `POST /documents/{id}/annotations` - Create annotation. Validates `start < end`, exact match with `clean_text[start:end]`, and taxonomy label.
- `PATCH /annotations/{id}` - Update label, note, position. Requires `version`; returns `409 Conflict` on stale edits.
- `DELETE /annotations/{id}` - Delete annotation; cascades deletion to all attached relations.

### Relations & Graph
- `GET /documents/{id}/relations` - List all relations for document.
- `POST /documents/{id}/relations` - Create relation. Validates taxonomy type and rejects self-links (`422`).
- `PATCH /relations/{id}` - Update relation. Requires `version`; returns `409 Conflict` on stale edits.
- `DELETE /relations/{id}` - Delete relation.
- `GET /documents/{id}/graph` - Combined view of annotations (nodes) and relations (edges).

### Smart Highlights & AI Relations
- `POST /documents/{id}/suggest-highlights` - Rank sentences via embedding similarity to current annotations minus rejected penalties.
- `GET /documents/{id}/suggestions` - List pending/accepted/rejected suggestions.
- `POST /suggestions/{id}/accept` - Accept suggestion (creates annotation, idempotent).
- `POST /suggestions/{id}/reject` - Reject suggestion (idempotent).
- `POST /documents/{id}/suggest-relations` - Launch background LLM relation discovery across annotation pairs. Returns `{"job_id": "..."}`. Returns `503` if LLM is unconfigured.

### Jobs
- `GET /jobs/{id}` - Retrieve job execution status (`queued`, `running`, `done`, `failed`), progress (0-100), result, and error.

## Free Hosting & Deployment

The application is containerized with a multi-stage `Dockerfile` and configured for instant free-tier deployment across multiple platforms.

### Option 1: Hugging Face Spaces (Recommended - 100% Free, 16 GB RAM)
Hugging Face Spaces provides **2 vCPU, 16 GB RAM** on their free tier with **no credit card required**, which is ideal for PyTorch and sentence-transformer embeddings.

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space).
2. Set Space Name (e.g. `pdf-knowledge-graph`).
3. Select **Docker** as the Space SDK (Blank template).
4. In your terminal, link and push your repository:
   ```bash
   git remote add space https://huggingface.co/spaces/<YOUR_HF_USERNAME>/<YOUR_SPACE_NAME>
   git push space main
   ```
5. Your app will automatically build and become live at `https://<YOUR_HF_USERNAME>-<YOUR_SPACE_NAME>.hf.space`.

---

### Option 2: Render Free Tier
1. Push this repository to GitHub.
2. Go to [render.com](https://render.com) and create a **New Web Service**.
3. Connect your repository. Render will automatically detect [`render.yaml`](file:///mnt/DE94962594960067/Users/kandp/Documents/Work/Personal_Git_Files/pdf_analyser_annot/render.yaml) and the [`Dockerfile`](file:///mnt/DE94962594960067/Users/kandp/Documents/Work/Personal_Git_Files/pdf_analyser_annot/Dockerfile).
4. Click **Deploy**. Render will build and deploy the container on their free tier.

---

### Option 3: Local / VPS Production Service
To run the optimized production build (FastAPI serving the unified SPA and API) on any Linux server:
```bash
./scripts/start_production.sh
```
This builds the frontend bundle into `frontend/dist`, initializes the database seed, and serves the complete application on port `8000` (or `$PORT`).

## Known Limitations
- Text-only PDFs: scanned image PDFs without embedded text layers require upstream OCR (out of scope).
- Single-document knowledge graph view (cross-document relations out of scope).

