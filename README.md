# DocuMesh

**DocuMesh** is an interactive web application where users upload text-based PDFs, highlight passages, link highlights with typed relationships visualized as an interactive document mesh, and receive smart highlight and relation suggestions.
![alt text](image.png)
## Key Features
- **Inline Highlights Reader View**: Native text reader rendering `clean_text` with non-overlapping inline highlight marks (`<mark>`), taxonomy-driven styling, pending suggestion accept/reject controls, DOM `data-start` selection coordinates, bidirectional graph synchronization (click highlight -> select node in graph; select node in graph -> scroll and flash highlight in reader), and view toggle between Reader and original PDF.
- **Graph-Aware Document Chat**: Answer questions grounded in document text and relationship graph edges (`POST /documents/{id}/chat`), with clickable citation chips that jump/flash in the reader, highlight graph nodes/edges, and allow saving cited sentences as annotations.
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
| `VECTOR_STORE` | `chroma` | Vector store backend: `chroma` or `fake` |
| `VECTOR_STORE_PATH` | `./data/chroma` | Persistent directory for Chroma vector store |
| `CANDIDATE_POOL_SIZE` | `30` | Number of candidate sentence vectors retrieved before MMR |
| `NEG_WEIGHT` | `0.5` | Penalty multiplier for rejected suggestions of the same label |
| `MMR_LAMBDA` | `0.7` | MMR diversity balance (0 = maximum diversity, 1 = maximum relevance) |
| `MAX_PENDING_PER_SEED` | `10` | Maximum pending suggestions allowed per seed annotation |
| `LLM_PROVIDER` | `fake` | Provider: `fake`, `huggingface`, or `openai` |
| `LLM_MODEL` | `meta-llama/Llama-3.2-1B-Instruct` | Model identifier (e.g. `meta-llama/Llama-3.2-1B-Instruct`, `Qwen/Qwen2.5-1.5B-Instruct`, `gpt-4o-mini`) |
| `HF_TOKEN` | `""` | Hugging Face User Access Token (for `LLM_PROVIDER=huggingface`) |
| `LLM_API_KEY` | `""` | API key (required if provider is `openai`, or fallback for `huggingface`) |
| `HF_ENDPOINT` | `https://router.huggingface.co/hf-inference/v1/chat/completions` | Hugging Face OpenAI-compatible inference router |
| `LLM_MAX_CONCURRENCY` | `3` | Max concurrent LLM requests via Semaphore |
| `LLM_TIMEOUT_SECONDS` | `30.0` | Timeout per LLM completion call |
| `MAX_RELATION_PAIRS` | `10` | Maximum candidate annotation pairs evaluated |
| `CHAT_TOP_K_SENTENCES` | `5` | Top sentence count retrieved for chat context |
| `CHAT_TOP_K_ANNOTATIONS` | `5` | Top annotation count retrieved for chat context |
| `CHAT_NEIGHBOR_HOPS` | `2` | Max graph hops traversed from retrieved seed annotations |
| `CHAT_MAX_HISTORY` | `5` | Max dialogue turns kept in chat history context |
| `CHAT_MAX_CONTEXT_CHARS` | `3000` | Max character budget for compacted context passed to LLM |
| `MAX_WORKERS` | `4` | Worker threads in ThreadPoolExecutor for background jobs |
| `SQLITE_BUSY_TIMEOUT_MS` | `5000` | SQLite WAL busy timeout in milliseconds |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Permitted CORS origin origins |
| `VITE_API_URL` | `http://localhost:8000` | Frontend API base URL |

> [!NOTE]
> **Architecture Distinction**: **Smart Highlights** is an embedding retrieval system with human feedback (active learning loop), not generative RAG. The system never generates hallucinated text; it scores and ranks verbatim document sentences against user seeds. **Document Chat** is the graph-augmented RAG feature that uses an LLM to answer questions and ground claims in graph relations.

## Scoped Smart Highlights & Vector Store

DocuMesh features an active-learning highlight discovery loop designed around human agency:

1. **Rebuildable Vector Store Index**:
   - SQLite remains the authoritative source of truth. Sentence vectors are stored in SQLite as raw byte BLOBs.
   - Chroma (`chromadb`, cosine distance) acts as a high-performance rebuildable index.
   - On server startup (`main.py`), DocuMesh inspects all documents in `ready` state. If the vector store collection is missing or empty for a document, it immediately rebuilds the index from the SQLite BLOBs without re-running the embedding model.
   - When running tests, the system seamlessly uses an in-memory `FakeVectorStore` selected via `VECTOR_STORE=fake`.

2. **Highlight Rules & Boundary Hygiene**:
   - **Word Boundary Snapping**: Selection offsets automatically snap outward to the nearest word boundary via `snap_to_word_boundaries`, shared between client (`offsets.js`) and server (`clean.py`).
   - **Idempotent Duplicates**: A composite unique constraint on `(document_id, start, end, label)` ensures duplicate creation attempts return the existing annotation (`200 OK`) instead of erroring, protecting against double-clicks and retries.
   - **Overlaps & Multi-Layering**: Multiple annotations over overlapping or nested character spans are fully supported. Clicking overlapping text selects the innermost (most specific) annotation, and a layers indicator allows switching between overlapping annotations in the details panel.
   - **Boundary Adjustments**: Start and end boundaries can be nudged directly in the details panel via `PATCH /annotations/{id}`, guarded by optimistic version locking (`409 Conflict` on concurrent edits).
   - **Superseded Suggestions**: When a confirmed annotation is created over a pending suggestion's range, that suggestion is marked `superseded` and excluded from pending views.

3. **Scoped Suggestions & Diversity Loop**:
   - Triggered from the reader popup or annotation panel with scope selection:
     - **This passage**: Positives are restricted to the seed annotation's vector.
     - **This category**: Positives include all annotations sharing the seed's label.
     - **Default Scope Rule**: Automatically defaults to *This category* if the label already has $\ge 3$ confirmed annotations, or *This passage* otherwise.
   - **Negative Feedback**: Rejected suggestions under the same label serve as negative vectors ($\text{NEG\_WEIGHT} = 0.5$). Rejections under one label do not penalize suggestions under other labels.
   - **Maximal Marginal Relevance (MMR)**: Candidates retrieved from Chroma are scored and re-ranked with greedy MMR ($\text{MMR\_LAMBDA} = 0.7$) to prevent redundant near-duplicate suggestions.
   - **Pending Cap & Thresholding**: Enforces `SIMILARITY_THRESHOLD = 0.35` (returns "No more similar passages found" if no candidate clears) and `MAX_PENDING_PER_SEED = 10` (returns a cap warning without bloating the graph).
   - **Atomic Acceptance**: Accepting a suggestion creates the confirmed annotation and a `similar_to` relation back to the seed annotation in a single atomic database transaction. Accepting twice is idempotent.
   - **AI Safety Rule**: The AI never continues or seeds from its own unconfirmed suggestions; only confirmed annotations can be seeds.

4. **Graph Ghost Nodes**:
   - Pending suggestions are returned in `GET /documents/{id}/graph` as nodes with `status = "suggested"`.
   - Ghost nodes render with dashed borders, faded opacity (0.72), match score percentages, and inline Accept/Reject buttons.
   - A dashed `similar_to` edge connects the ghost node to its seed annotation.
   - `similar_to` edges are hidden by default to prevent visual hub-and-spoke clutter, with an interactive toolbar switch to toggle their visibility.
   - Selecting a ghost node scrolls the reader to its faded highlight, and vice versa.

## How Document Chat Uses the Graph

DocuMesh features a graph-augmented QA pipeline (`POST /documents/{id}/chat`) designed for grounding answers in both raw text and semantic relationships:

1. **Dual Vector Retrieval**: When a question is asked, the query is embedded using the configured embedder (`all-MiniLM-L6-v2` or deterministic fake). It computes cosine similarity across both document sentences (returning top `CHAT_TOP_K_SENTENCES`) and existing annotations (returning top `CHAT_TOP_K_ANNOTATIONS` as seeds).
2. **In-Memory Graph Expansion**: From each seed annotation, DocuMesh traverses the document's relationship graph in memory up to `CHAT_NEIGHBOR_HOPS` hops. This incorporates neighbor nodes and connecting relations (e.g. `supports`, `refutes`, `defines`), retaining both confirmed and suggested relations.
3. **Compact Context Budgeting**: Retrieved sentences, annotations, and relations are assigned stable identifiers (`[s..]`, `[a..]`, `[r..]`) and ranked by relevance. They are packed into a compact context string strictly capped at `CHAT_MAX_CONTEXT_CHARS`, dropping lowest-ranked items first.
4. **Citation Validation**: The LLM is instructed via system prompt to answer strictly from the provided context and cite bracketed IDs (e.g. `[s3]`, `[a1]`, `[r2]`). The server parses all bracketed citations, verifies that they were present in the delivered context, resolves their character offsets, and strips any hallucinated citations while preserving the answer text.
5. **No-Context Shortcut**: If retrieval yields no context above the minimal relevance threshold (`0.15`), the system returns `"I couldn't find this in the document."` with `used_context: false` immediately, without making an unnecessary LLM call.
6. **Interactive UI Navigation**: In the frontend chat panel, citations render as clickable chips. Clicking a sentence or annotation citation scrolls the reader directly to the passage and flashes it. For annotations, the corresponding graph node is selected; for relations, the edge in the graph is focused. Sentences can also be saved as new annotations with one click.

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

### Graph-Aware Document Chat
- `POST /documents/{id}/chat` - Query document and relationship mesh with grounded citations.
  - **Request**: `{"question": "string", "history": [{"role": "user", "content": "..."}]}` (history is trimmed to `CHAT_MAX_HISTORY` turns).
  - **Response**: `{"answer": "string", "citations": [{"type": "sentence" | "annotation" | "relation", "id": 1, "start": 0, "end": 20}], "used_context": true}`.
  - **Status codes**: `200` on success (including `used_context: false` on no-context shortcut), `404` for unknown document, `422` for empty question, `503` if LLM service is unconfigured.

### Jobs
- `GET /jobs/{id}` - Retrieve job execution status (`queued`, `running`, `done`, `failed`), progress (0-100), result, and error.

## Demo Script

A dedicated graph-aware chat demonstration script is included at `scripts/demo_chat.py`. It tests three questions exploring definitions, support chains, and contradiction relations on `sample.pdf`:

```bash
python scripts/demo_chat.py
```

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

