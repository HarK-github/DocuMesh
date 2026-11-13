# DocuMesh: GraphRAG for Academic & Technical Documents

**DocuMesh** transforms static PDF literature into structured, interactive relational knowledge graphs. Instead of passively reading linear text or relying on ungrounded vector search, DocuMesh unites dense semantic embeddings with an in-memory **NetworkX knowledge graph projection**, providing active-learning highlight suggestions, automated top-down extraction, canonical entity resolution, and **Tri-Mode GraphRAG (Vector | Graph | Hybrid via Reciprocal Rank Fusion)** with span-grounded citations.

### Visual Interface & Interactive Knowledge Graph

| Radial Knowledge Graph | Synchronized Split Reader |
| :---: | :---: |
| ![DocuMesh Radial Knowledge Graph](docs/images/radial_graph.png) | ![Annotated PDF and Graph](docs/images/radial_graph_annotated_split.png) |

| GraphRAG Conversational Q&A with Clickable Citations |
| :---: |
| ![Graph-Aware Chat with Grounded Citations](docs/images/chat_llm_answering.png) |

> Detailed technical specifications, benchmark methodology, and cost analysis are documented in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/BENCHMARK_RESULTS.md](docs/BENCHMARK_RESULTS.md), and [docs/GRAPHRAG_PLAN.md](docs/GRAPHRAG_PLAN.md).

---

## Architecture & Design

DocuMesh operates on a core epistemological principle: **the knowledge graph is a live, typed, grounded view over raw document text**, not a synthetic hallucination. Every concept node and relation edge grounds directly to exact character offsets in the source literature.

```mermaid
flowchart TD
    subgraph Ingestion ["Ingestion & Preprocessing"]
        PDF["Uploaded PDF"] --> PyMuPDF["PyMuPDF Layout & Text Extraction"]
        PyMuPDF --> CleanText["Context-Aware Dehyphenation & Header/Footer Normalization"]
        CleanText --> Segmentation["Sentence Segmentation (pysbd) & Chunker (500 tokens)"]
        Segmentation --> Embedder["all-MiniLM-L6-v2 Embeddings & Sentence Mean-Pooling"]
    end

    subgraph DataLayer ["Unified Data & Storage Core (PostgreSQL + pgvector)"]
        DB[("Database (Single Source of Truth)\nDocuments · Sentences · Chunks\nUnified Nodes · Aliases · Mentions\nGraph Relations · Relation Evidence\npgvector HNSW Cosine Index")]
    end
    Ingestion --> DB

    subgraph GraphEngine ["Graph & Retrieval Engine (NetworkX GraphRAG)"]
        Projector["In-Memory nx.MultiDiGraph Projection Service"]
        Traversal["1-2 Hop Bidirectional BFS Traversal"]
        Dampening["Super-Node Degree Dampening & Edge Scoring"]
        RRF["Reciprocal Rank Fusion (k = 60)"]
    end
    DB --> Projector
    Projector --> Traversal --> Dampening --> RRF

    subgraph UI ["Interactive Synchronized Interface"]
        Reader["Synchronized Reader (Text + PDF + Gold Pulse Highlight)"]
        Graph["React Flow Knowledge Graph (Dagre Layout)"]
        Chat["ChatPanel (Tri-Mode Selector: Vector | Graph | Hybrid)"]
    end
    DB <--> Reader
    DB <--> Graph
    Reader <-->|Bidirectional Focus Sync| Graph
    RRF --> Chat
    Chat <-->|Click Grounded Citation| Reader
    Chat <-->|Focus Relation Edge| Graph
```

### Core Design Principles
1. **Verbatim Text Grounding**: Every node in the knowledge graph maps to exact character start and end offsets (`start`, `end`) in the cleaned document text. Quotes are automatically snapped to word boundaries and verified against document text.
2. **PostgreSQL + pgvector as the Authoritative Single Source of Truth**: All annotations, relations, and embeddings are stored durably in PostgreSQL with connection pooling and transactional safety. Vector storage and similarity retrieval are powered natively in-database via `pgvector` with HNSW cosine distance indexing (`<=>`), eliminating external vector databases.
3. **Polymorphic Unified Nodes & Canonical Entity Resolution**: Entities support universal global concepts (`is_global = true`) and document-scoped claims (`is_global = false`). Exact-match aliases and scoped LLM adjudication ($\ge 0.70$) unify cross-document terminology with fully reversible tombstone merges (`entity_merge_log`).
4. **Sentence Mean-Pooled Chunking**: 500-token chunks with 100-token overlap, aligned to sentence boundaries, bypass transformer truncation limits using sentence mean-pooling ($\mathbf{v}_{chunk} = \frac{\sum \mathbf{v}_s}{\|\sum \mathbf{v}_s\|_2}$) with zero extra inference calls.
5. **Tri-Mode Cited Retrieval with RRF**: Users can dynamically toggle between `Vector` (fast dense cosine similarity), `Graph` (relational BFS over NetworkX projection), and `Hybrid` (Reciprocal Rank Fusion combining vector hits and relation evidence sentences).
6. **Optimistic Locking & Concurrency**: Annotations and relations utilize version-tracked optimistic locking (`version_id_col`), returning `409 Conflict` on concurrent or stale edits.

---

## Key Features

### 1. Tri-Mode GraphRAG Q&A (Single Document & Corpus-Wide)
- **Mode Selector**: Seamlessly switch between `Vector (Fast)`, `Graph (Relational)`, and `Hybrid (Comprehensive)` modes directly from the chat interface.
- **Corpus-Wide Cross-Document Chat**: Query across all uploaded documents simultaneously via `POST /chat`. The NetworkX graph projection traverses cross-document bridge relations, connecting premises in one paper with conclusions in another.
- **Verbatim Span-Grounded Citations**: Citations (`[s*]` for sentences, `[r*]` for relations) are strictly validated. Clicking a relation citation `[r5]` selects the edge in the graph and pulses the underlying evidence passage gold in the reader.
- **100% Grounding Faithfulness**: Rigorous context restriction ensures generated claims are directly substantiated by retrieved text spans, eliminating hallucinated statements and invalid citations.

### 2. Interactive Document Mesh (Knowledge Graph)
- **Visual Canvas**: Powered by React Flow and Dagre layout, rendering annotations as concept cards and relations as directed semantic arrows.
- **Taxonomy Driven**: Seeded taxonomy categories (`Claim`, `Evidence`, `Definition`, `Method`, `Result`, `Problem`, `Solution`) and relationship types (`supports`, `refutes`, `defines`, `elaborates`, `causes`, `solves`, `similar_to`, `contrasts_with`, `conditional_on`, `precedes`).
- **Ghost Suggestion Nodes**: Pending AI suggestions render as semi-transparent "ghost nodes" directly in the graph canvas with inline match scores and one-click Accept/Reject controls.
- **Relational Integrity**: Enforces strict cycle prevention, disallows self-referential links, and cascades edge deletion when an annotation is deleted.

### 3. Dual-View Synchronized Reader
- **Inline Highlighting**: Renders non-overlapping inline `<mark>` tags styled with high-contrast taxonomy badges directly over the text.
- **Bidirectional Graph Synchronization**:
  - Clicking any highlight in the reader centers and selects its node in the graph view.
  - Clicking a node in the graph view scrolls the reader smoothly to the exact passage and flashes the highlight.
- **Multi-Layering & Overlaps**: Fully supports overlapping character spans, allowing users to toggle between overlapping annotations in the details drawer.
- **PDF Mode Toggle**: Instantly switch between the native structured text reader and the page-targeted rendered PDF canvas.

### 4. Canonical Entity Resolution & Reversible Merging
- **Scoped Auto-Aliasing**: Exact-match alias indexing scoped by `node_type` unifies surface variants (e.g. abbreviations, acronyms) into a canonical node.
- **Similarity Adjudication**: LLM-assisted verification merges concepts with cosine similarity $\ge 0.70$ while queuing ambiguous cases for review.
- **Tombstone Lifecycle**: Merges repoint relations and mentions to the canonical target while recording full reversal snapshots in `entity_merge_log`.

### 5. Top-Down Document Auto-Highlighting
- **End-to-End Extraction**: Sweeps through an entire PDF in document order to construct a knowledge graph with a single click.
- **Batch Classification**: Analyzes sentence chunks against the project taxonomy using either an LLM or local zero-shot prototype vector embeddings.
- **Calibrated Prototype Fallback**: If an LLM is offline or uncredited, the engine automatically falls back to embedding prototype classification with calibrated similarity scoring (`AUTO_HIGHLIGHT_PROTO_THRESHOLD = 0.18`), ensuring highlights are generated without API dependencies.
- **Background Job Tracking**: Runs asynchronously with live percentage progress tracking (`GET /jobs/{id}`) and non-blocking background workers.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.12+, FastAPI, SQLAlchemy, PostgreSQL (`pgvector/pgvector:pg16`, `pgvector`, `psycopg2-binary`), Alembic, PyMuPDF (`fitz`), `pysbd`, `sentence-transformers`, `numpy`, `networkx` |
| **Graph Projection** | In-memory `networkx.MultiDiGraph` with BFS multi-hop expansion and Reciprocal Rank Fusion ($k=60$) |
| **Embeddings & Vector Engine** | Local `all-MiniLM-L6-v2` (384-dim), in-database `pgvector` with HNSW cosine distance indexing (`<=>`), sentence mean-pooling |
| **Frontend** | React 19, Vite, React Flow (`reactflow`), Dagre, TanStack Query (`@tanstack/react-query`), Lucide Icons |
| **LLM Services** | Hugging Face Serverless (`huggingface_hub`), OpenAI API, or Deterministic Offline Client |
| **Testing** | `pytest` (**Backend - 100 tests**), `vitest` (**Frontend - 50 tests**) |

---

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+ and `npm`
- Docker (optional, for running local PostgreSQL)

### 1. Clone & Configure
```bash
git clone https://github.com/your-username/documesh.git
cd documesh
cp .env.example .env
```

### 2. Database Setup (Local PostgreSQL)
You can start a local PostgreSQL container using Docker Compose:
```bash
docker compose up -d db
```
Or use an existing PostgreSQL instance and configure `DATABASE_URL` in `.env`.

### 3. Backend Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Run database migrations
python3 -m alembic upgrade head

# Start backend server
uvicorn backend.app.main:app --port 8000 --reload
```
The API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 4. Frontend Setup
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### 5. Seed Demo Data (Optional)
To pre-populate a sample document with annotations and relations:
```bash
python backend/seed.py
```

---

## Configuration Reference

All application parameters are configured via environment variables in `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql://user:password@localhost:5432/documesh` | SQLAlchemy PostgreSQL connection string |
| `DB_POOL_SIZE` | `5` | PostgreSQL connection pool size |
| `DB_MAX_OVERFLOW` | `10` | PostgreSQL connection pool max overflow |
| `UPLOAD_DIR` | `./uploads` | Storage directory for uploaded PDF files |
| `MAX_UPLOAD_MB` | `15` | Maximum PDF file upload size limit (MB) |
| `MAX_PDF_PAGES` | `50` | Maximum page count allowed per document |
| `EMBEDDING_MODEL_NAME` | `all-MiniLM-L6-v2` | Sentence-transformers model identifier |
| `VECTOR_STORE` | `chroma` | Vector index implementation (`chroma` or `fake`) |
| `VECTOR_STORE_PATH` | `./data/chroma` | Persistent Chroma storage directory |
| `SIMILARITY_THRESHOLD` | `0.35` | Minimum cosine similarity score for suggestions |
| `SUGGESTION_COUNT` | `5` | Maximum suggestions returned per recommendation run |
| `NEG_WEIGHT` | `0.5` | Penalty factor for rejected suggestions |
| `MMR_LAMBDA` | `0.7` | MMR balance (0 = maximum diversity, 1 = maximum relevance) |
| `AUTO_HIGHLIGHT_BATCH_SIZE` | `20` | Sentence chunk batch size during auto-highlighting |
| `AUTO_HIGHLIGHT_MAX_PAIRS` | `100` | Max candidate pairs evaluated for full graph building |
| `AUTO_HIGHLIGHT_PROTO_THRESHOLD` | `0.18` | Minimum similarity floor for zero-shot prototype fallback |
| `LLM_PROVIDER` | `fake` | LLM client backend: `fake`, `huggingface`, or `openai` |
| `LLM_MODEL` | `meta-llama/Llama-3.2-1B-Instruct` | Model identifier for relations and chat |
| `HF_TOKEN` | `""` | Hugging Face API token (if using `huggingface`) |
| `LLM_API_KEY` | `""` | OpenAI API key (if using `openai`) |
| `CHAT_TOP_K_SENTENCES` | `5` | Sentences retrieved for document chat context |
| `CHAT_TOP_K_ANNOTATIONS` | `5` | Seed annotations retrieved for document chat |
| `CHAT_NEIGHBOR_HOPS` | `2` | Graph edge hops traversed for chat context |
| `CHAT_MAX_CONTEXT_CHARS` | `3000` | Maximum character budget for LLM chat context |
| `VITE_API_URL` | `http://localhost:8000` | Frontend backend API URL |

---

## REST API Overview

### Documents & Ingestion
- `POST /documents`: Upload PDF (`multipart/form-data`). Instant SHA-256 deduplication returns existing documents immediately.
- `GET /documents/{id}`: Fetch document metadata and processing status (`processing`, `ready`, `failed`).
- `GET /documents/{id}/text`: Retrieve clean, segmented text with sentence index mapping.
- `GET /documents/{id}/pdf`: Stream raw PDF binary for embedded viewer with page-targeted highlight burn-in.
- `GET /documents/{id}/chunks`: Retrieve token-bounded chunks (500 tokens, 100 overlap) and constituent sentence ranges.

### Unified Canonical Nodes & Entity Resolution
- `GET /nodes`: List active canonical nodes across corpus or document (filter by `node_type`, `document_id`).
- `GET /nodes/{id}`: Fetch full entity details, surface aliases, and grounded text mentions.
- `POST /nodes/merge`: Atomically execute a canonical entity merge with reversible audit logging (`entity_merge_log`).
- `POST /nodes/revert-merge/{id}`: Revert a previous entity merge, restoring original node references and evidence links.
- `GET /nodes/merge-pending`: List ambiguous candidate pairs queued for review.

### Annotations & Graph
- `GET /documents/{id}/annotations`: List all confirmed annotations for a document.
- `POST /documents/{id}/annotations`: Create an annotation. Verifies exact quote substring matching and snaps to word boundaries.
- `PATCH /annotations/{id}`: Update label, note, or coordinates. Enforces optimistic locking (`version`).
- `DELETE /annotations/{id}`: Delete annotation and cascade delete attached relations.
- `GET /documents/{id}/relations`: List all directional relations for a document.
- `POST /documents/{id}/relations`: Create typed relation between two annotations. Validates taxonomy and blocks self-links.
- `PATCH /relations/{id}`: Update relation type or status.
- `DELETE /relations/{id}`: Remove relation edge.
- `GET /documents/{id}/graph`: Unified endpoint returning both nodes (annotations + ghost suggestions) and edges.
- `GET /documents/{id}/graph/evidence`: Fetch exact verbatim supporting text spans for a given relation edge.

### GraphRAG Q&A & Intelligence
- `POST /documents/{id}/chat`: Document-scoped GraphRAG Q&A supporting `mode: 'vector' | 'graph' | 'hybrid'` with clickable citations (`[s*]`, `[r*]`).
- `POST /chat`: Corpus-wide cross-document GraphRAG Q&A navigating multi-hop relationships across papers.
- `POST /documents/{id}/auto-highlight`: Trigger asynchronous top-down sequential document annotation and full knowledge graph building.
- `POST /documents/{id}/suggest-highlights`: Discover similar passages via scoped active learning and MMR.
- `GET /documents/{id}/suggestions`: Fetch pending, accepted, and rejected suggestions.
- `POST /suggestions/{id}/accept`: Atomically convert a suggestion into an annotation and link it to the seed.
- `POST /suggestions/{id}/reject`: Reject suggestion and update negative feedback weights.
- `POST /documents/{id}/suggest-relations`: Trigger background LLM relation discovery between existing annotations.
- `GET /jobs/{id}`: Poll background task status, progress (0-100%), and results.

---

## Testing & Quantitative Benchmarks

Both backend and frontend test suites run locally with isolated test fixtures and zero external service dependencies:

```bash
# Run all backend unit and integration tests (100 passed)
pytest

# Run all frontend component and hook tests (50 passed)
cd frontend && npm test -- --run

# Run full 4-way quantitative evaluation benchmark (32 questions across 5 papers)
python3 benchmark/eval_runner.py
```

### Load Testing
A concurrent load test benchmark script is included in `backend/load_test.py`:
```bash
python backend/load_test.py --url http://127.0.0.1:8000 -n 200 -c 20
```

---

## Deployment

### Docker Compose (Recommended for Full Stack)
Run PostgreSQL and the unified DocuMesh application together:
```bash
docker compose up -d
```

### Docker Deployment
Build and run the standalone production container with an external PostgreSQL database:
```bash
docker build -t documesh .
docker run -p 7860:7860 -e DATABASE_URL="postgresql://user:password@host:5432/documesh" -v $(pwd)/uploads:/app/uploads documesh
```

### Hugging Face Spaces (Free Tier)
DocuMesh is configured to run on a Hugging Face Docker Space (16 GB RAM, 2 vCPU):
1. Create a new Space at [huggingface.co/new-space](https://huggingface.co/new-space) selecting **Docker** SDK.
2. Link your repository:
   ```bash
   git remote add space https://huggingface.co/spaces/<USERNAME>/<SPACE_NAME>
   git push space main
   ```
3. Set any necessary environment variables under Space Settings.

---

## License & Contributing
MIT License. Contributions and issue reports are welcome via pull requests and GitHub Issues.
