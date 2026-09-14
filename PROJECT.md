# Project plan: PDF annotation and relationship graph app

Build this end to end, one phase at a time. Keep the code simple and readable. Do not add features that are not listed here.

## 1. What we are building

A web app where a user uploads a text-based PDF, highlights passages, links highlights with typed relationships shown as a graph, and gets "smart highlight" suggestions for similar passages.

- Annotations are graph nodes. Relations are graph edges. The graph is a view over two tables, never a separate structure.
- Text-only PDFs. No OCR, no images, no tables.

## 2. Working rules (follow throughout)

**Design principles**
- Keep it simple (KISS). Prefer a plain function over a class, and a class over a framework.
- One responsibility per module. Routes only handle HTTP, services hold logic, and the DB layer only talks to the DB.
- No premature abstraction. Add an interface only where the plan says to (the embedder and the LLM client).
- Small functions (about 30 lines or less), clear names, and short docstrings that explain why.

**No hardcoding**
- All settings come from environment variables via one `settings.py`: DB path, upload dir, embedding model name, LLM provider/model/key, CORS origins, suggestion count, similarity threshold.
- Provide `.env.example`. Never commit `.env` or secrets.
- Label names and relation types live in `config/taxonomy.json` and are seeded into the DB. The UI loads them from the API. Do not write them into code.
- The frontend reads the API base URL from `VITE_API_URL`.

**Testing**
- After every step, run the tests. Do not move on until they pass.
- Backend: `pytest`, with a temporary SQLite DB per test. Frontend: `vitest` for the offset-to-highlight helper and the API client.
- Tests must not call real external services. Use a fake embedder and a fake LLM client.
- Add at least one test per endpoint (success case and one error case).

**Git**
- `git init` in phase 0 and commit after every completed step, at least once per step.
- Use conventional messages: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`.
- One logical change per commit. Tests go in the same commit as the code they cover, or immediately after.
- Use the real current timestamp. Do not set or alter commit dates.

## 3. Stack

- Backend: Python, FastAPI, SQLite (via SQLAlchemy or plain `sqlite3`, pick one), PyMuPDF (text extraction), pysbd (sentence split), sentence-transformers (embeddings), numpy.
- Frontend: React + Vite, `pdfjs-dist` (or `react-pdf`) for rendering, React Flow for the graph, dagre for auto-layout, TanStack Query (`@tanstack/react-query`) for all server requests.
- LLM: one small client behind an interface, configured by env. Used only for suggested relations.
- Concurrency uses only the standard library and the tools above (`ThreadPoolExecutor`, `asyncio.Semaphore`, SQLite WAL, SQLAlchemy versioning). Do not add Redis, Celery, or other extra infrastructure, and do not add `slowapi` or `tenacity`.

## 4. Repo layout

```
backend/
  app/
    main.py            # app creation, router includes, CORS
    settings.py        # env-driven config
    db.py              # connection, schema creation
    models.py          # table definitions / row helpers
    schemas.py         # request/response models
    routes/            # documents.py, annotations.py, relations.py, suggestions.py, taxonomy.py
    services/          # extract.py, clean.py, sentences.py, embedder.py, ranker.py, llm.py, jobs.py
  tests/
  requirements.txt
frontend/
  src/
    api/               # client.js (fetch wrapper), queryClient.js
    hooks/             # useDocument, useAnnotations, useRelations, useJob, ... (TanStack Query)
    components/        # PdfViewer, GraphView, AnnotationPanel, SuggestionList
    lib/               # offsets.js (offset <-> text-layer mapping)
    App.jsx
  package.json
config/taxonomy.json
sample/                # one small public-domain text PDF for the demo
README.md
.env.example
```

## 5. Data model

- `documents`: id, filename, file_hash (unique), status (`processing` | `ready` | `failed`), clean_text, created_at
- `sentences`: id, document_id, idx, start, end, page, embedding (BLOB)
- `annotations`: id, document_id, start, end, quote, label, note, x, y, version, created_at
- `relations`: id, document_id, source_id, target_id, type, status (`suggested` | `confirmed`), reason, version
- `suggestions`: id, document_id, sentence_id, score, status (`pending` | `accepted` | `rejected`)
- `jobs`: id, type, document_id, status (`queued` | `running` | `done` | `failed`), progress (0-100), result (JSON), error, created_at
- `labels` and `relation_types`: name, seeded from `config/taxonomy.json`

Rules enforced in code: `start < end`; the stored quote must equal `clean_text[start:end]`; deleting an annotation deletes its relations; a relation cannot link an annotation to itself; `file_hash` is unique so the same PDF is never processed twice.

## 6. API

- `POST /documents` (returns `{document_id, job_id}` immediately; returns the existing document if the hash matches), `GET /documents/{id}`, `GET /documents/{id}/text`
- `GET|POST /documents/{id}/annotations`, `PATCH|DELETE /annotations/{id}`
- `GET|POST /documents/{id}/relations`, `PATCH|DELETE /relations/{id}`
- `GET /documents/{id}/graph` (annotations + relations in one response)
- `POST /documents/{id}/suggest-highlights`, `POST /suggestions/{id}/accept`, `POST /suggestions/{id}/reject`
- `POST /documents/{id}/suggest-relations` (returns a `job_id`)
- `GET /jobs/{id}` (status, progress, result, error)
- `GET /taxonomy` (labels and relation types)

Return clear errors with correct status codes (404, 409 for stale edits, 422, 503 when the LLM is not configured).

## 7. Phases

Each phase ends with passing tests, a short README update, and a commit.

### Phase 0: Setup
1. Init repo, `.gitignore`, folder layout, `README.md` skeleton.
2. Backend: `settings.py`, `.env.example`, FastAPI app with `GET /health`, pytest wired up with one passing test.
3. Frontend: Vite React app that calls `/health` using `VITE_API_URL`. Install `@tanstack/react-query`, create one `QueryClient` in `api/queryClient.js` with sensible defaults (limited retries, a short `staleTime`), wrap the app in `QueryClientProvider`, and fetch `/health` through a `useQuery` hook as the first example.

### Phase 1: Ingestion
1. `db.py` creates the schema on startup. Test it with a temp DB.
2. `extract.py`: PDF to text per page with PyMuPDF. Test with the sample PDF.
3. `clean.py`: remove repeated headers/footers and page numbers, fix hyphenated line breaks, rejoin lines into paragraphs. Test each rule with small input strings.
4. `sentences.py`: split with pysbd and store start/end offsets plus page. Test that `clean_text[start:end]` equals the stored sentence.
5. `POST /documents`, `GET /documents/{id}`, `GET /documents/{id}/text`. Hash the file first and return the existing document if it was already uploaded. Otherwise save it, run ingestion with a FastAPI `BackgroundTask` for now (Phase 7 replaces this with the tracked job runner and returns a `job_id`), and set the document status to `ready` or `failed`. Reject files over the size and page limits from settings with a clear 422.

### Phase 2: Annotations and relations (core CRUD)
1. Taxonomy loader and `GET /taxonomy`.
2. Annotation endpoints with the validation rules above. Tests for the bad-offset and mismatched-quote cases.
3. Relation endpoints with type validation against the taxonomy, no self-links, and cascade delete. Tests for each.
4. `GET /documents/{id}/graph`.

### Phase 3: Frontend PDF viewer and annotating
1. `PdfViewer`: render pages with the text layer.
2. `lib/offsets.js`: map a text selection to character offsets in `clean_text`, and map stored offsets back to highlight spans. This is the riskiest part, so write unit tests first (multi-span selections, selection across line breaks).
3. Create an annotation from a selection (label dropdown loaded from `/taxonomy`, optional note). Render saved highlights. Edit and delete from `AnnotationPanel`.
4. Use TanStack Query for all of this: `useQuery` for documents, annotations, and taxonomy, and `useMutation` for create, edit, and delete. After each mutation, invalidate the related query key so the UI refetches instead of managing state by hand. Keep query keys in one place (for example `['annotations', documentId]`). Handle a `409` response from a stale edit by refetching and showing a short "this was changed elsewhere" message.

### Phase 4: Graph view
1. `GraphView` with React Flow: nodes from annotations, edges from relations, auto-layout with dagre on first load.
2. Create an edge by dragging between nodes, then choose the relation type from a menu loaded from `/taxonomy`.
3. Save node positions with `PATCH /annotations/{id}` when a drag ends. Use saved positions on later loads.
4. Click a node to scroll the PDF to that highlight. Click a highlight to select its node.
5. Filters: by label, by relation type, and "show neighbors of selected node".

### Phase 5: Smart highlight
1. `embedder.py`: a small interface (`embed(list[str]) -> array`) with a sentence-transformers implementation (model name from settings) and a fake one for tests.
2. Compute and store sentence embeddings at the end of ingestion.
3. `ranker.py`: score each sentence by mean cosine similarity to the accepted/selected examples minus a weighted similarity to rejected ones. Exclude sentences already covered by annotations. Return the top N above a threshold (both from settings). Unit-test with the fake embedder and known vectors.
4. Endpoints `suggest-highlights`, `accept`, `reject`. Accepting creates an annotation, and each call re-ranks on the next request.
5. `SuggestionList` UI: faded highlights in the PDF with accept/reject buttons. Never auto-apply.

### Phase 6: Suggested relations
1. `llm.py`: an interface (`complete_json(prompt) -> dict`) with one real provider chosen by env and a fake for tests. Return 503 if no key is configured.
2. `suggest-relations`: take a bounded set of annotation pairs (cap from settings), ask for `{type, reason}` per pair constrained to the taxonomy, validate the response, and save as `status = suggested`. Run it as a job and return a `job_id`. Give each LLM call a timeout from settings and cap concurrent calls with a semaphore (see Phase 7). If some pairs fail, save the successful ones and report the failures in the job result.
3. Draw suggested edges dashed. Confirm or delete them from the UI.
4. Tests: valid response, malformed JSON, type not in taxonomy, and no API key.

### Phase 7: Handling many requests

Keep this simple. No new infrastructure, and the only new package is TanStack Query on the frontend.

Backend (standard library and existing tools only)
1. `services/jobs.py`: a small job runner. It uses one `ThreadPoolExecutor` with `MAX_WORKERS` from settings, creates the job row, runs the function, updates progress, status, result, and error, and catches exceptions so a failed job is recorded rather than lost. On startup, mark any jobs left in `running` as `failed`. Tests: success, failure, and the startup cleanup.
2. `GET /jobs/{id}` returns status, progress, result, and error. Test the 404 case too.
3. SQLite safety: on every new connection set `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout` (value from settings). Use one short-lived session per request, and never keep a transaction open during an LLM call or an embedding run.
4. Load the embedding model once at app startup (FastAPI `lifespan`) and embed sentences in batches (batch size from settings).
5. Cap concurrent LLM calls with one shared `asyncio.Semaphore` (size from settings), and run the pair checks concurrently with `asyncio.gather` under it. Use plain `def` routes or the job runner for CPU-heavy work so the event loop is never blocked.
6. Stale edits: use SQLAlchemy's `version_id_col` on annotations and relations (or an explicit `version` check if not using SQLAlchemy). A `PATCH` for an out-of-date record returns `409`.
7. Idempotency: accept and reject are safe to repeat (check the current status, and return the existing result instead of creating a second annotation). The unique `file_hash` makes duplicate uploads safe even when two arrive at once.
8. Concurrency tests: 20 parallel annotation creates with no lost writes and no "database is locked" errors; a stale `PATCH` returns `409`; two simultaneous uploads of the same PDF produce one document.

Frontend (TanStack Query)
9. `useJob(jobId)`: a `useQuery` that polls `GET /jobs/{id}` with `refetchInterval`, and stops polling when the status is `done` or `failed`. Show a progress bar and an error message. Use it for upload processing and for suggested relations.
10. Make sure identical simultaneous requests are deduplicated by sharing query keys, and disable submit buttons while a mutation is pending so double-clicks don't send duplicates.
11. On mutation success, invalidate only the affected keys (for example annotations, or the graph). On `409`, refetch and tell the user.
12. A quick load test script (`hey` or `locust`) against the read endpoints. Put the numbers and the command in the README.

Add these settings to `.env.example`: `MAX_WORKERS`, `LLM_MAX_CONCURRENCY`, `LLM_TIMEOUT_SECONDS`, `SQLITE_BUSY_TIMEOUT_MS`, `EMBED_BATCH_SIZE`, `MAX_UPLOAD_MB`, `MAX_PDF_PAGES`, `MAX_RELATION_PAIRS`.

### Phase 8: Polish and delivery
1. Loading and error states in the UI (processing, failed, empty document).
2. A seed script that loads the sample PDF with a few example annotations and relations.
3. README: what it does, setup, env variables, how to run tests, API list, known limitations.
4. A final full test run, a manual walkthrough of the demo flow, and a final cleanup commit.

## 8. Definition of done

- All tests pass with one command per side (`pytest`, `npm test`).
- Fresh clone runs by following only the README and `.env.example`.
- Upload, annotate, link, filter, smart highlight, and suggested relations work on the sample PDF.
- Slow work (ingestion, suggested relations) runs as tracked jobs, and the UI shows progress via TanStack Query polling.
- Concurrent writes, stale edits (`409`), and duplicate uploads are covered by passing tests.
- No secrets, magic strings, or magic numbers in the code. Config comes from env or `taxonomy.json`.
- Git history shows small, meaningful commits per step.

## 9. Out of scope

OCR, images/tables, user accounts, real-time collaboration, multi-document graphs, and anything not listed above.