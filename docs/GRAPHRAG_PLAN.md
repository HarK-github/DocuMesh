# DocuMesh GraphRAG Evolution Plan: From Document Annotation to Epistemological Knowledge Graph GenAI

**Author:** Senior Systems & AI Engineer  
**Date:** November 2026 (Revision 2)  
**Status:** PROPOSED (Pending Review & Approval)  
**Target Repository:** `pdf_analyser_annot` (DocuMesh)  

---

## Revision Changelogs

### Revision 2 Changelog (Current)

| Item | Requirement & Architectural Change | Status |
| :--- | :--- | :--- |
| **1. Grounding & Offset Mapping** | Proximity checks applied to concept endpoints only; a claim node's own span is its evidence. Formulated offset mapping from normalized matches back to `clean_text` using whitespace-tolerant regex with start/end bounds and deterministic multi-match disambiguation. | **ADDRESSED** |
| **2. Chunk Extraction Schema** | Mentions assigned local chunk-scoped IDs (`m1`, `m2`, ...). Relations reference local IDs (`source_mention_id`, `target_mention_id`), eliminating fragile name-string matching in extraction. | **ADDRESSED** |
| **3. Entity Merges & Auditability** | Absorbed nodes retained as tombstones (`merged_into_id`). Formalized repointing of mentions and relations, evidence set union, and triple deduplication. Added `entity_merge_pending` table for ambiguous pairs. Scoped exact-match auto-merges strictly by `node_type`. | **ADDRESSED** |
| **4. Schema & Partial Unique Indexes** | Replaced all NULL-vulnerable standard UNIQUE constraints with PostgreSQL partial unique indexes for global concepts, document-local claims, and document-scoped/cross-document relations. | **ADDRESSED** |
| **5. Migration & SSOT Governance** | Mapped all 7 legacy labels explicitly (`Claim`, `Evidence`, `Definition`, `Method`, `Result`, `Problem`, `Solution`) with a `legacy_label` column. Created claim nodes for legacy annotations. Migrated legacy relations via `mentions.node_id`. Assigned legacy `relates_to`/`similar_to` a reduced traversal weight ($\gamma = 0.5$) and excluded them from new extractions. Formulated new schema behavior for manual annotation/relation endpoints. | **ADDRESSED** |
| **6. Chunk Embeddings & Context Limits** | Documented that `all-MiniLM-L6-v2` has a 256-token context window that truncates 500-token chunks. Implemented sentence-embedding mean pooling for chunks, achieving an un-truncated, zero-compute 384-dimensional chunk embedding. | **ADDRESSED** |
| **7. Retrieval & Citation Refinement** | Defined formal `SeedScore` for query lexical/embedding matches and vector-linked entities. Formalized RRF handling for items absent from a branch ($\text{Rank} = \infty \implies 0$). Added dense embedding query-to-node matching. Removed `[e*]` as an answer citation type; all answer citations resolve directly to text spans (`[s*]` and `[r*]` shorthand). | **ADDRESSED** |
| **8. Benchmark Subdivision** | Split benchmark into (1) Within-Document Multi-Hop (4-way: Pure Sentence RAG vs Current Chat Baseline vs Graph-Only vs Hybrid) and (2) Cross-Document Multi-Hop (Graph/Hybrid vs a newly constructed Corpus-Wide Sentence RAG baseline). | **ADDRESSED** |
| **9. Phase 1 Isolation & Go/No-Go Gate** | Confined Phase 1 extraction and audit outputs entirely to JSONL files with zero database schema mutations. Converted 80% grounding and 75% precision thresholds into an explicit Go/No-Go decision gate before Phase 2 schema migration. | **ADDRESSED** |
| **10. Official Pricing & Cost Recalibration** | Verified pricing from official pages (November 2026: `gpt-4o-mini` at $\$0.150/\$0.600$ per 1M tokens; `claude-3-5-haiku` at $\$0.800/\$4.000$ per 1M tokens). Explicitly scheduled adjudication volume calibration based on Phase 1 empirical name similarity distributions. | **ADDRESSED** |

---

### Revision 1 Changelog

| Item | Requirement & Architectural Change | Status |
| :--- | :--- | :--- |
| **1. Resolution Policy** | Disallowed auto-merges on embedding similarity alone; restricted auto-merge to exact normalized name/alias; pairs $\ge 0.70$ sent to LLM adjudication; added `entity_merge_log`. | **ADDRESSED** |
| **2. Dynamic Migration** | Derived `mentions.page` dynamically from sentence covering annotation start offset. | **ADDRESSED** |
| **3. Grounding Verification** | Removed fuzzy match fallback; required exact match after whitespace normalization. | **ADDRESSED** |
| **4. Unified Node Schema** | Unified concepts and claims into a polymorphic `nodes` table; relations strictly `node -> node`. | **ADDRESSED** |
| **5. Retrieval Seeds** | Seeds defined as query entities $\cup$ entities linked to top-$k$ vector sentences. | **ADDRESSED** |
| **6. Benchmark Strategy** | Mandated 30+ hand-written multi-hop questions over 5–10 papers written prior to tuning. | **ADDRESSED** |
| **7. Token Sizing & Polish** | Sized chunks to tokens (500 tokens, 100 overlap); labeled all latency figures as estimates; removed overclaims. | **ADDRESSED** |

---

## 1. Executive Summary & Architectural Vision

DocuMesh today is a focused PDF research and annotation tool with single-document semantic vector search and a local relational prototype graph. While it already features clean character-offset provenance (`clean_text`), an in-memory 1-hop BFS traversal for document chat, and active recommendation heuristics (MMR + negative mining), it faces key structural limits:
1. **Isolated Document Silos**: Knowledge is strictly trapped within individual `document_id` scopes. Concepts like *"Transformer"*, *"Adam Optimizer"*, or *"Cross-Entropy Loss"* cannot connect across multiple uploaded papers.
2. **Flat Chunking Gap**: Retrieval is anchored exclusively to individual micro-sentences (`sentences` table) or manual spans (`annotations`). There is no higher-level contextual chunk layer to frame extraction.
3. **Absence of Canonical Entity Resolution**: The platform lacks concept identity. Two papers discussing the same algorithm with slightly different surface names (e.g. *"FlashAttention-2"* and *"FlashAttention v2"*) remain disconnected.
4. **Unbenchmarked Retrieval**: Q&A operates without a verifiable evaluation harness comparing vector retrieval against graph-guided retrieval.

### The GraphRAG Target State
This plan details the evolutionary upgrade of DocuMesh into a robust **GraphRAG Knowledge-Graph GenAI System**:
- **Backward-Compatible Coexistence**: The existing sentence-level vector Q&A and existing chat flow are retained as baseline systems for rigorous comparative evaluation.
- **Hierarchical Provenance**: Token-bounded chunks sit atop sentences; every graph edge and extracted claim is anchored to exact `[start, end)` character offsets in canonical `clean_text`.
- **Unified Node Epistemology**:
  - A unified `nodes` table hosting both global **Concepts** (Methods, Datasets, Metrics, Tasks) resolved across documents and local **Claims** (Propositions, Findings, Hypotheses) anchored to specific document spans.
  - All relationships are strictly `node -> node`, allowing rich relational topologies (e.g., Concept $\to$ Claim, Claim $\to$ Claim).
- **Multi-Mode Retrieval Engine**: A user-toggleable engine offering `vector` (baseline), `graph` (entity traversal + evidence harvesting), and `hybrid` (Reciprocal Rank Fusion) retrieval.
- **Strict Grounding & Citation Verification**: Every LLM extraction requires verbatim exact-match quotes and entity proximity verification. Citations in answers resolve directly to underlying text spans (`[s*]` and `[r*]`).
- **Robust Infrastructure**: Preserves the core DocuMesh design philosophy—relying on PostgreSQL with pgvector (HNSW cosine index) and NetworkX in memory, strictly avoiding redundant distributed vector database dependencies.
- **Phase 1 Isolation**: Phase 1 extraction and audits write strictly to disk JSONL files, proving edge precision and grounding viability before any schema migrations occur.

---

## 2. Step 1: Codebase Audit & Truth Verification

We inspected the actual implementation across backend and frontend services. Below is the itemized verdict for every assumption and suspected defect.

| Audit Target / Assumption | Verdict | Concrete Code Evidence & Operational Reality |
| :--- | :--- | :--- |
| **Current Q&A Architecture**<br>*(Top-k sentences by cosine similarity into prompt? Per document or across documents? Returns citations?)* | **CONFIRMED** *(with nuance)* | In `backend/app/routes/chat.py` and `backend/app/services/chat_context.py`: Query is strictly scoped to `document_id`. Top sentences (`settings.chat_top_k_sentences`, default 5) and top annotations (`chat_top_k_annotations`, default 3) are retrieved by cosine similarity against the question. An in-memory 1-hop BFS traverses `relations` for that document. Stable IDs `[s{id}]`, `[a{id}]`, `[r{id}]` are fed to the prompt. Regex `\[([sar]\d+)\]` extracts citations, which are validated against the context budget and returned as `{type, id, start, end}`. There is zero cross-document search capability. |
| **Node & Edge Creation**<br>*(Manual vs Automatic)* | **CONFIRMED** *(Hybrid)* | Nodes (`annotations`) and edges (`relations`) support two creation paths: (1) **Manual**: Selection in `ReaderView.jsx` / `PdfViewer.jsx` via `POST /documents/{id}/annotations`; drag-and-drop linking in `GraphView.jsx` via `POST /documents/{id}/relations`. (2) **Automated**: `backend/app/services/auto_highlighter.py` uses either LLM batch classification or cosine similarity against 7 hardcoded `LABEL_PROTOTYPES` to create `status="suggested"` nodes; `backend/app/services/relation_suggester.py` uses heuristic pair pruning, SHA-256 caching, and LLM few-shot prompting to create `status="suggested"` edges ("ghost nodes/edges"). |
| **Suspected Bug (a)**<br>*(`clean.py` hyphenation regex corrupts compounds at line breaks)* | **CONFIRMED** | In `backend/app/services/clean.py` (lines 14–17):<br>`pattern = re.compile(r'(\b[a-zA-Z]+)-\s*\n\s*([a-zA-Z]+\b)')`<br>`return pattern.sub(r'\1\2', text)`<br>This unconditionally deletes the hyphen. Genuine compound terms broken across line breaks (e.g. `"multi-\nhop"`, `"cross-\nvalidation"`, `"state-\nof-the-art"`) are corrupted into `"multihop"`, `"crossvalidation"`, and `"stateof-the-art"`. |
| **Suspected Bug (b)**<br>*(Header/footer removal uses exact string count $\ge 2$, failing on page numbers & small docs)* | **CONFIRMED** | In `backend/app/services/clean.py` (lines 35–51):<br>`repeated_headers = {line for line, count in Counter(top_lines).items() if count >= 2}`<br>`repeated_footers = {line for line, count in Counter(bot_lines).items() if count >= 2}`<br>(1) It matches exact stripped strings. Footers containing changing page numbers (e.g. `"- 14 -"` vs `"- 15 -"`, or `"DocuMesh | Page 1"`) each have `count == 1` and are never removed. (2) For short documents ($\le 2$ pages), coincidental line matches are aggressively stripped. For 50-page documents, `count >= 2` represents a 4% threshold, causing false positives on common section titles ("Introduction", "References") that appear as first/last lines. |
| **Suspected Bug (c)**<br>*(Annotated PDF export matches first occurrence with `search_for(quote)` and breaks)* | **CONFIRMED** | In `backend/app/routes/documents.py` (lines 158–170):<br>`for page in pdf_doc:`<br>`    rects = page.search_for(a.quote)`<br>`    if rects:`<br>`        h_annot = page.add_highlight_annot(rects)`<br>`        ...`<br>`        break`<br>(1) If a quoted phrase appears on page 1 (e.g. Abstract) and was annotated on page 8 (Conclusion), the loop highlights page 1 and immediately `break`s, leaving page 8 unannotated. (2) `a.quote` is sliced from `clean_text` (normalized spaces, stripped hyphens). When `page.search_for` runs against raw PDF streams containing soft line breaks or original hyphens, it fails completely. |
| **Suspected Bug (d)**<br>*(Embedding search is brute-force NumPy; will not scale to cross-document)* | **CONFIRMED** | In `backend/app/services/chat_context.py` (lines 79–93): Retrieval loops through all sentences in Python: `cosine_similarity(q_emb, s_emb)`. In `backend/app/services/ranker.py`: `vectors @ q_vec` loads all sentence BLOBs for a single document. While estimated at $< 0.3\text{ ms}$ for 1,000 sentences, across a corpus of 500 documents ($500{,}000$ sentences $\times$ 384 dimensions $\times$ 4 bytes $\approx 768\text{ MB}$ raw BLOBs), loading and calculating unindexed dot products in Python blocks the GIL and causes elevated query latency (estimated $> 800\text{ ms}$). |

---

## 3. Target System Architecture & Epistemological Design

### 3.1 Architectural Principles
1. **Preserve Provenance**: Every entity mention and semantic edge must trace back to exact character offsets `[start, end)` in canonical `clean_text`.
2. **Unified Node Graph**: All entities (concepts) and propositions (claims) share a single node representation, allowing uniform directional relationships (`node -> node`).
3. **Rigorous Verbatim Grounding**: LLMs extract relational candidates, but no candidate is committed to the knowledge graph unless its `evidence_quote` matches `clean_text` exactly (modulo whitespace) and concept endpoints pass proximity checks.
4. **Conservative Entity Resolution**: No automated merges on embedding similarity alone. Merges occur solely on exact normalized names/aliases scoped by `node_type`, or via explicit LLM adjudication. All merges write tombstones and reversible logs.
5. **Robust Infrastructure**: Rely on PostgreSQL with pgvector, an in-memory NetworkX projection, and indexed vector search. Avoid external distributed graph or vector database dependencies unless operationally justified.

```
+----------------------------------------------------------------------------------------------------+
|                                      DOCUMESH GRAPHRAG ENGINE                                      |
+----------------------------------------------------------------------------------------------------+
                                                  │
                    ┌─────────────────────────────┴─────────────────────────────┐
                    ▼                                                           ▼
       [ INGESTION & EXTRACTION ]                                     [ MULTI-MODE RETRIEVAL ]
  ┌───────────────────────────────────┐                          ┌──────────────────────────────────┐
  │ PDF Upload & SHA-256 Dedup        │                          │ User Query / Question            │
  │ Normalization & clean_text        │                          └─────────────────┬────────────────┘
  │ pysbd Sentence Segmentation       │                                            │
  │ Chunking (500 tokens, 100 ovlp)   │                    ┌───────────────────────┼───────────────────────┐
  │ Sentence Mean-Pooled Embeddings   │                    ▼                       ▼                       ▼
  │ Local-ID Mentions & Relations     │             [ Vector Mode ]         [ Graph Mode ]          [ Hybrid Mode ]
  │ Verbatim Evidence Grounding       │             - Sentence/Chunk        - Entity Seed Match     - RRF Reciprocal
  │ Exact & Adjudicated Resolution    │               Dense Search          - 1-2 Hop Bidirectional   Rank Fusion
  │ PostgreSQL + pgvector (ACID)         │             - Top-K Passages          NetworkX Traversal    - Deduplication
  └─────────────────┬─────────────────┘                                     - Evidence Harvesting   - Token Budgeting
                    │                                                              │
                    ▼                                                              │
  ┌───────────────────────────────────┐                                            │
  │       POSTGRESQL + PGVECTOR DB         │ ◄──────────────────────────────────────────┘
  │ nodes    | mentions | relations   │                                            │
  │ evidence | chunks   | sentences   │                                            ▼
  │ entity_merge_log / pending        │                               ┌─────────────────────────────┐
  └─────────────────┬─────────────────┘                               │ Context Assembler & LLM     │
                    │ (Projection)                                    │ Stable IDs: [s1], [r3]      │
                    ▼                                                 │ Citation Verifier & Parser  │
  ┌───────────────────────────────────┐                               └──────────────┬──────────────┘
  │   NetworkX MultiDiGraph Cache     │                                              │
  │ (In-memory, bidirectional hops)   │                                              ▼
  └───────────────────────────────────┘                                     [ Verified Cited Answer ]
                                                                            - Citations resolve to spans
                                                                            - Jump & flash in ReaderView
```

---

## 4. Target Data Model & Migration Strategy

### 4.1 Unified Node Ontology & Schema Design

#### Unified Ontology
* **Node Types**:
  - Global Concepts (`is_global = 1`): `Method`, `Dataset`, `Metric`, `Task`, `System`, `Problem`, `Solution`
  - Document-Local Claims (`is_global = 0`): `Claim`, `Result`, `Evidence`, `Definition`
* **Relation Types (Disambiguated & Restricted)**:
  - `supports`, `refutes`, `defines`, `elaborates`, `causes`, `solves`, `contrasts_with`, `conditional_on`, `precedes`, `evaluates_with`
  - *(Generic `relates_to` and `similar_to` are strictly removed from LLM extraction targets)*.

---

### 4.2 Target Database Schema (SQL DDL with Partial Indexes)

To prevent PostgreSQL `UNIQUE` constraint failure modes where `NULL` values bypass deduplication, all uniqueness is enforced via **partial unique indexes**.

```sql
-- 1. Chunk Layer (Token-bounded contextual parent for sentences)
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    start INTEGER NOT NULL,             -- Character offset start in clean_text
    end INTEGER NOT NULL,               -- Character offset end in clean_text
    first_sentence_idx INTEGER NOT NULL,
    last_sentence_idx INTEGER NOT NULL,
    token_count INTEGER NOT NULL,       -- Strictly tokens (target: 500)
    embedding BLOB,                     -- 384-dim float32 vector BLOB (Sentence mean-pooling)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_chunk_doc_idx UNIQUE (document_id, chunk_index),
    CHECK (start < end)
);
CREATE INDEX idx_chunks_doc_offsets ON chunks(document_id, start, end);

-- 2. Unified Nodes Table (Entities, Claims, and Tombstones)
CREATE TABLE nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,          -- Canonical name or concise claim summary
    normalized_name VARCHAR(255) NOT NULL, -- Lowercase, stripped punctuation
    node_type VARCHAR(64) NOT NULL,      -- Method, Dataset, Metric, Task, System, Problem, Solution, Claim, Result, Evidence, Definition
    description TEXT,                    -- Synthesized canonical summary
    is_global BOOLEAN NOT NULL DEFAULT 1,-- 1 for Concepts (corpus-wide); 0 for Claims (document-bound)
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE, -- Set for claims/results; NULL for global concepts
    legacy_label VARCHAR(64),            -- Preserves original annotation label for 100% backward fidelity
    merged_into_id INTEGER REFERENCES nodes(id) ON DELETE SET NULL, -- Tombstone pointer to surviving node
    embedding BLOB,                      -- 384-dim vector for resolution candidate blocking
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_nodes_name ON nodes(name);
CREATE INDEX idx_nodes_type ON nodes(node_type);
CREATE INDEX idx_nodes_merged ON nodes(merged_into_id);

-- Partial Unique Indexes for Nodes (Prevents NULL-bypass bugs)
CREATE UNIQUE INDEX uq_global_nodes 
ON nodes(normalized_name, node_type) 
WHERE is_global = 1 AND merged_into_id IS NULL;

CREATE UNIQUE INDEX uq_doc_claim_nodes 
ON nodes(document_id, normalized_name, node_type) 
WHERE is_global = 0 AND document_id IS NOT NULL AND merged_into_id IS NULL;

-- 3. Node Aliases (Exact surface forms and synonyms)
CREATE TABLE node_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    alias VARCHAR(255) NOT NULL,
    normalized_alias VARCHAR(255) NOT NULL,
    source VARCHAR(32) DEFAULT 'extracted', -- 'extracted' | 'adjudicated' | 'manual'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_node_alias UNIQUE (node_id, normalized_alias)
);
CREATE INDEX idx_aliases_norm ON node_aliases(normalized_alias);

-- 4. Entity Merge Log (Reversible merge audit trail)
CREATE TABLE entity_merge_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    surviving_node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    absorbed_node_id INTEGER NOT NULL,   -- Historical tombstone ID
    absorbed_name VARCHAR(255) NOT NULL,
    absorbed_type VARCHAR(64) NOT NULL,
    adjudication_reason TEXT NOT NULL,
    adjudicated_by VARCHAR(32) NOT NULL, -- 'exact_match' | 'llm' | 'manual'
    confidence FLOAT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    reverted_at DATETIME                -- NULL if active; timestamp if reverted
);
CREATE INDEX idx_merge_surviving ON entity_merge_log(surviving_node_id);

-- 5. Entity Merge Pending Review (Queue for uncertain pairs)
CREATE TABLE entity_merge_pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_a_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    candidate_b_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    similarity FLOAT NOT NULL,
    llm_adjudication_verdict VARCHAR(32), -- 'uncertain' | 'conflict'
    llm_reason TEXT,
    status VARCHAR(32) DEFAULT 'pending', -- 'pending' | 'resolved' | 'dismissed'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_merge_pending_pair UNIQUE (candidate_a_id, candidate_b_id)
);

-- 6. Mentions Table (Extends and supersedes raw annotations)
CREATE TABLE mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id INTEGER REFERENCES chunks(id) ON DELETE SET NULL,
    node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    quote TEXT NOT NULL,                 -- Exact verbatim text quote
    start INTEGER NOT NULL,              -- Character offset in clean_text
    end INTEGER NOT NULL,                -- Character offset in clean_text
    page INTEGER NOT NULL,               -- Exact physical PDF page (derived from sentence)
    note TEXT,
    x FLOAT DEFAULT 0.0,
    y FLOAT DEFAULT 0.0,
    version INTEGER DEFAULT 1,
    status VARCHAR(32) DEFAULT 'confirmed', -- 'confirmed' | 'suggested'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CHECK (start < end)
);
CREATE INDEX idx_mentions_doc_offsets ON mentions(document_id, start, end);
CREATE INDEX idx_mentions_node ON mentions(node_id);
CREATE UNIQUE INDEX uq_mentions_doc_span_node ON mentions(document_id, start, end, node_id);

-- 7. Typed Semantic Relations (Node-to-Node)
CREATE TABLE graph_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE, -- NULL for cross-document inferred relations
    source_node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target_node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    relation_type VARCHAR(64) NOT NULL,  -- supports, refutes, defines, elaborates, causes, solves, contrasts_with, conditional_on, precedes, evaluates_with, relates_to (legacy)
    confidence FLOAT NOT NULL DEFAULT 1.0,
    status VARCHAR(32) DEFAULT 'confirmed', -- 'confirmed' | 'suggested'
    is_legacy BOOLEAN NOT NULL DEFAULT 0,-- 1 for legacy relates_to/similar_to
    reason TEXT,
    version INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CHECK (source_node_id != target_node_id)
);
CREATE INDEX idx_rel_src_tgt ON graph_relations(source_node_id, target_node_id);
CREATE INDEX idx_rel_doc ON graph_relations(document_id);

-- Partial Unique Indexes for Relations
CREATE UNIQUE INDEX uq_doc_graph_relations 
ON graph_relations(document_id, source_node_id, target_node_id, relation_type) 
WHERE document_id IS NOT NULL;

CREATE UNIQUE INDEX uq_cross_doc_graph_relations 
ON graph_relations(source_node_id, target_node_id, relation_type) 
WHERE document_id IS NULL;

-- 8. Verbatim Relation Evidence (Anchor to source text)
CREATE TABLE relation_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    relation_id INTEGER NOT NULL REFERENCES graph_relations(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    sentence_id INTEGER REFERENCES sentences(id) ON DELETE CASCADE,
    verbatim_quote TEXT NOT NULL,
    start INTEGER NOT NULL,
    end INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_evidence_relation ON relation_evidence(relation_id);
CREATE INDEX idx_evidence_sentence ON relation_evidence(sentence_id);
CREATE UNIQUE INDEX uq_evidence_relation_span ON relation_evidence(relation_id, start, end);
```

---

### 4.3 Database Migration Strategy & Single Source of Truth (SSOT)

#### Step 1: Mentions Page Calculation & Node Backfill
The migration maps every legacy annotation to a new row in `nodes` and a linked row in `mentions`. `mentions.page` is dynamically derived from `sentences`:

```sql
-- A. Backfill nodes from annotations
INSERT INTO nodes (name, normalized_name, node_type, is_global, document_id, legacy_label, created_at)
SELECT 
    quote,
    lower(trim(quote)),
    label,
    CASE WHEN label IN ('Method', 'Problem', 'Solution') THEN 1 ELSE 0 END,
    CASE WHEN label IN ('Method', 'Problem', 'Solution') THEN NULL ELSE document_id END,
    label,
    created_at
FROM annotations;

-- B. Backfill mentions linked to newly created nodes
INSERT INTO mentions (id, document_id, node_id, quote, start, end, page, note, x, y, version, status, created_at)
SELECT 
    a.id,
    a.document_id,
    n.id,
    a.quote,
    a.start,
    a.end,
    COALESCE(
        (SELECT s.page FROM sentences s WHERE s.document_id = a.document_id AND s.start <= a.start AND s.end >= a.start LIMIT 1),
        (SELECT s.page FROM sentences s WHERE s.document_id = a.document_id ORDER BY ABS(s.start - a.start) LIMIT 1),
        1
    ) AS page,
    a.note, a.x, a.y, a.version, 'confirmed', a.created_at
FROM annotations a
JOIN nodes n ON n.document_id IS a.document_id AND n.name = a.quote AND n.legacy_label = a.label;

-- C. Migrate relations using mentions.node_id
INSERT INTO graph_relations (document_id, source_node_id, target_node_id, relation_type, confidence, status, is_legacy, reason, version)
SELECT 
    r.document_id,
    m_src.node_id,
    m_tgt.node_id,
    r.type,
    coalesce(r.cos_score, 1.0),
    r.status,
    CASE WHEN r.type IN ('relates_to', 'similar_to') THEN 1 ELSE 0 END,
    r.reason,
    r.version
FROM relations r
JOIN mentions m_src ON m_src.id = r.source_id
JOIN mentions m_tgt ON m_tgt.id = r.target_id;
```

#### Step 2: Policy for Legacy `relates_to` / `similar_to`
- Preserved in historical database rows with `is_legacy = 1`.
- When calculating graph traversal weights, legacy relations receive a discounted decay factor ($\gamma = 0.50$ instead of $0.80$).
- Strictly excluded from new LLM extraction prompts.

#### Step 3: Manual Endpoints Behavior on New Schema
- `POST /documents/{id}/annotations`: Creates an unlinked document-local node in `nodes` (`is_global = 0`, `node_type = payload.label`, `legacy_label = payload.label`) and inserts a row in `mentions`.
- `POST /documents/{id}/relations`: Resolves `source_mention = mentions.get(payload.source_id)` and `target_mention = mentions.get(payload.target_id)` and inserts a row into `graph_relations` with `source_node_id = source_mention.node_id` and `target_node_id = target_mention.node_id`.

#### Step 4: SSOT Governance
- *During Migration*: `nodes`, `mentions`, and `graph_relations` are the active write targets. SQLAlchemy query models for `Annotation` and `Relation` are repointed to read from `mentions` and `graph_relations`.
- *Post Migration*: Legacy tables `annotations` and `relations` are dropped after Phase 3 verification.

---

## 5. Algorithmic Upgrades & Pipeline Mechanics

### 5.1 Chunk Sizing & Embedding Strategy
1. **Token Sizing**: Exactly **500 tokens** per chunk with **100 tokens** overlap (measured with BPE `cl100k_base`), aligned to `pysbd` sentence boundaries.
2. **Embedder Context Limit Resolution**:
   - `SentenceTransformer("all-MiniLM-L6-v2")` enforces `max_seq_length = 256` tokens. Passing a 500-token chunk directly silently truncates 244 tokens.
   - **Resolution Strategy: Sentence Mean Pooling**:
     $$\mathbf{v}_{chunk} = \frac{\sum_{s \in \text{sentences}} \mathbf{v}_s}{\left\|\sum_{s \in \text{sentences}} \mathbf{v}_s\right\|_2}$$
     Each sentence in the chunk is already embedded ($\le 256$ tokens) and unit-normalized. Calculating the normalized vector sum of constituent sentences yields a truncation-free, semantically balanced 384-dimensional chunk embedding with **zero extra inference calls**.

---

### 5.2 Structured Chunk Extraction Schema (Local Mentions)
Extraction outputs local chunk-scoped IDs (`m1`, `m2`, ...) to eliminate ambiguous string-based edge referencing.

```python
class LocalMention(BaseModel):
    mention_id: str = Field(..., description="Local chunk ID: m1, m2, etc.")
    surface_form: str
    node_type: Literal["Method", "Dataset", "Metric", "Task", "System", "Problem", "Solution", "Claim", "Result"]
    is_claim: bool = False
    evidence_quote: str

class LocalRelation(BaseModel):
    source_mention_id: str = Field(..., description="References mention_id (e.g. m1)")
    target_mention_id: str = Field(..., description="References mention_id (e.g. m2)")
    relation_type: Literal[
        "supports", "refutes", "defines", "elaborates", 
        "causes", "solves", "contrasts_with", "conditional_on", 
        "precedes", "evaluates_with"
    ]
    evidence_quote: str
    reason: str

class ChunkExtractionResult(BaseModel):
    mentions: List[LocalMention]
    relations: List[LocalRelation]
```

---

### 5.3 Exact Grounding & Offset Mapping

#### 1. Verbatim Grounding Rule
- Normalization: $\text{norm}(s) = \text{re.sub}(r'\s+', '\ ', s).\text{strip}()$.
- Verification: `norm(evidence_quote)` must be an exact substring of `norm(chunk_text)`. No fuzzy fallbacks.

#### 2. Mapping Back to `clean_text` Offsets
To translate the matched quote back to exact $[start, end)$ indices in `clean_text`:
1. Split `norm(evidence_quote)` into words: `words = norm(evidence_quote).split(' ')`.
2. Construct a whitespace-tolerant regex:
   `pattern = re.compile(r'\s+'.join(re.escape(w) for w in words))`
3. Execute `pattern.finditer(clean_text[chunk.start : chunk.end])`.
4. **Disambiguation on Multiple Matches**:
   - If multiple occurrences exist within the chunk slice:
     1. Prioritize the match overlapping or closest to the constituent sentence containing the concept mention.
     2. If still tied, select the first occurrence within `[chunk.start, chunk.end]`.
     3. Reject any match whose span extends outside `[chunk.start, chunk.end]`.

#### 3. Endpoint Proximity Rules
- **Concept Endpoints**: Both source and target entity names (or their surface aliases) must appear within the evidence sentence or within $\pm 1$ adjacent sentence.
- **Claim Endpoints**: If an endpoint is a Claim/Result node, proximity checks are waived because the claim's own span *is* its evidence.

---

### 5.4 Reversible Entity Merges & Tombstone Lifecycle

#### 1. Scoped Exact-Match Auto-Merge
An auto-merge occurs **if and only if**:
$$\text{norm}(alias) == \text{norm}(node.name) \quad \text{AND} \quad candidate.node\_type == node.node\_type$$
*(A `Dataset` named "CNN" will never auto-merge with a `Method` named "CNN")*.

#### 2. Candidate Blocking & LLM Adjudication
Any pair sharing the same `node_type` with embedding cosine similarity $\ge 0.70$ is routed to LLM adjudication:
- **BERT-Base vs BERT-Large Test**: Cosine similarity is $\sim 0.84$. Under this policy, they do not auto-merge. The LLM adjudicator reviews parameters (12 layers vs 24 layers) and outputs `DISTINCT`.
- If LLM verdict is `UNCERTAIN` or confidence $< 0.75$, the pair is written to `entity_merge_pending`.

#### 3. Repointing & Tombstone Handling
When Node B is absorbed into Node A:
1. Update Node B: `SET merged_into_id = Node_A_id`.
2. Repoint all `mentions` where `node_id = Node_B_id` to `Node_A_id`.
3. Repoint all `graph_relations` where `source_node_id = Node_B_id` or `target_node_id = Node_B_id` to `Node_A_id`.
4. **Triple Conflict & Evidence Union**:
   - If repointing produces a relation duplicate matching partial index `uq_doc_graph_relations`:
     ```sql
     -- Transfer evidence to surviving relation
     UPDATE relation_evidence 
     SET relation_id = existing_relation_id 
     WHERE relation_id = duplicate_relation_id;
     
     -- Delete redundant relation row
     DELETE FROM graph_relations WHERE id = duplicate_relation_id;
     ```
5. Record action in `entity_merge_log`.

---

### 5.5 Multi-Mode Retrieval (`vector` | `graph` | `hybrid`)

#### 1. Seed Formulation
The seed set $S_0$ combines lexical, dense, and vector-linked entities:
1. **Query Lexical Matches**: Exact matches of query n-grams against `node_aliases`.
2. **Query Dense Embedding Matches**: Query embedding $\mathbf{q}_{emb}$ compared against global concept nodes ($\text{Sim} \ge 0.75$).
   $$\text{SeedScore}_{query}(u) = \max \left( 1.0 \text{ [lexical]}, \cos(\mathbf{q}_{emb}, \mathbf{u}_{emb}) \right)$$
3. **Vector-Linked Entities**: Nodes attached via `mentions` to the top-$k$ sentence vector search hits:
   $$\text{SeedScore}_{linked}(u) = \max_{s \in \text{linked top-k}} \cos(\mathbf{q}_{emb}, \mathbf{s}_{emb})$$
4. Final Seed Score: $\text{SeedScore}(u) = \max \left( \text{SeedScore}_{query}(u), \text{SeedScore}_{linked}(u) \right)$.

#### 2. Pre-RRF Evidence Scoring
During 1-2 hop bidirectional BFS traversal, each traversed edge $e = (u, v)$ with evidence sentence $s$ receives:
$$\text{Score}_{graph}(s) = \max \left( \text{SeedScore}(u), \text{SeedScore}(v) \right) \times \text{Confidence}(e) \times (0.80)^{\text{hop}} \times \left(0.50 \text{ if } e.\text{is\_legacy else } 1.0\right)$$
Sentences are ranked descending by $\text{Score}_{graph}(s)$.

#### 3. Reciprocal Rank Fusion (Missing Items Handled)
If an item is missing from a branch, its reciprocal rank is $0$:
$$\text{RRF}(s) = \mathbb{I}(s \in \text{VectorHits}) \frac{1}{60 + \text{Rank}_{vector}(s)} + \mathbb{I}(s \in \text{GraphHits}) \frac{1}{60 + \text{Rank}_{graph}(s)}$$

#### 4. Answer Citation Verification
- Generated answers may **only** cite sentence IDs `[s*]` and relation IDs `[r*]`.
- **`[e*]` is removed as a citation type**.
- When the answer cites `[r3]`, the system expands `[r3]` to its underlying `relation_evidence` sentences, ensuring that clicking any citation in `ReaderView` highlights the exact supporting text span.

---

## 6. Bug Fixes & Subsystem Corrections

### Bug Fix A: Context-Aware Hyphenation Resolution (`clean.py`)
* **Defect**: Blindly replaced all `(\b[a-zA-Z]+)-\s*\n\s*([a-zA-Z]+\b)` with `\1\2`.
* **Correction**:
  1. Build a local document lexicon $V_{doc}$ from all unhyphenated whitespace-separated words in the document.
  2. For candidate hyphenated split `w1-\nw2`:
     - If compound `w1-w2` appears elsewhere in $V_{doc}$, keep the hyphen: `w1-w2`.
     - Else if merged `w1w2` appears in $V_{doc}$, merge: `w1w2`.
     - Else fallback to a standard English frequency dictionary; if unknown, preserve the hyphen to avoid corrupting domain-specific compounds (e.g. `"multi-hop"`).

### Bug Fix B: Normalized Frequency Header/Footer Elimination (`clean.py`)
* **Defect**: Exact string matching on `l.strip()` with fixed `count >= 2`.
* **Correction**:
  1. **Pattern Normalization**: Tokenize variable digits before counting:
     `norm_line = re.sub(r'\b\d+\b', '<NUM>', raw_line.strip())`
     Ensures `"Page 14 | ICML"` and `"Page 15 | ICML"` normalize to `"Page <NUM> | ICML"` and are correctly grouped.
  2. **Page Ratio Threshold**: Replace static count with dynamic threshold:
     $$\text{Threshold} = \max\left(2, \lceil 0.20 \times \text{total\_pages} \rceil\right)$$
     A candidate header/footer must appear on at least 20% of pages to be stripped.

### Bug Fix C: Page-Scoped & Normalized PDF Annotation Export (`routes/documents.py`)
* **Defect**: Looped across all pages, called `search_for(quote)` and broke on first match.
* **Correction**:
  1. **Page-Targeted Search**: Pass the annotation's stored `page` number directly to `pdf_doc[a.page - 1]`.
  2. **Fallback Search**: If exact string search on that page fails due to PDF whitespace/ligatures, use PyMuPDF `TextPage.search_for()` with `flags=pymupdf.TEXT_DEHYPHENATE | pymupdf.TEXT_PRESERVE_WHITESPACE`.
  3. Search neighboring pages $(\pm 1)$ only if the annotation span crosses a physical page boundary.

### Scalable Vector Search (PostgreSQL `pgvector` HNSW)
* **Defect**: Unindexed Python loop or dense NumPy matrix multiply over all DB rows.
* **Correction**:
  1. For single-document queries: retain NumPy BLAS dot-product (estimated $< 0.3\text{ ms}$).
  2. For corpus-wide cross-document search: integrate the lightweight C extension **`pgvector`** using native PostgreSQL pgvector HNSW indexing. This keeps vector search inside PostgreSQL pgvector with zero network overhead while handling $100{,}000+$ vectors in estimated $< 5\text{ ms}$.

---

## 7. Phased Implementation Roadmap

```
Phase 1: Isolated Extraction, Grounding Audit & Benchmark Dataset (No DB Schema Changes)
  ├── Sentence-mean chunker & local-ID Pydantic extractor
  ├── Exact-match grounding verifier (outputs strictly to JSONL)
  ├── 30+ hand-written multi-hop evaluation questions across 5-10 papers
  └── Manual edge-precision audit (~100 edges) -> Explicit Go/No-Go Decision Gate
        │
        ▼
Phase 2: Unified Node Schema, Conservative Resolution & SSOT Migration
  ├── Unified nodes, node_aliases, entity_merge_log, entity_merge_pending
  ├── Database migration with sentence-derived mentions.page
  ├── Exact-match auto-alias + LLM adjudication (Sim >= 0.70)
  └── Defer Entity Merge UI until empirical ambiguity rates are measured
        │
        ▼
Phase 3: NetworkX Projection & Multi-Mode Cited Retrieval
  ├── In-memory NetworkX MultiDiGraph projection service
  ├── 1-2 Hop Bidirectional BFS traversal & pre-RRF evidence ranking
  ├── Tri-mode retrieval switch (Vector | Graph | Hybrid)
  └── Text-span citation resolution & interactive ReaderView highlighting
        │
        ▼
Phase 4: Quantitative 4-Way Evaluation
  ├── Within-Doc Multi-Hop: Sentence Vector vs Current Chat vs Graph-Only vs Hybrid
  ├── Cross-Doc Multi-Hop: Graph/Hybrid vs newly built Corpus-Wide Sentence RAG
  └── Automated test runner & published comparative benchmark report
        │
        ▼
Phase 5 (Deferred): Hierarchical Community Summaries
  └── Louvain/Leiden community detection & corpus summaries (conditional on Phase 4 results)
```

### Detailed Phase Specifications

#### Phase 1: Isolated Extraction, Grounding Audit & Benchmark Spike
* **Tasks**:
  1. Implement token-based chunking in `backend/app/services/chunks.py`.
  2. Implement local-ID structured extractor (`backend/app/services/extractor.py`) using Pydantic schema validation.
  3. Implement exact-match quote verifier and concept proximity check in `backend/app/services/grounding.py`.
  4. **Strict Isolation**: Extraction and audit outputs write **exclusively to disk JSONL files** (`benchmark/phase1_extractions.jsonl`, `benchmark/phase1_grounding_audit.jsonl`). Zero database schema alterations.
  5. Fix Bug A (hyphenation) and Bug B (header/footer normalization) in `clean.py`.
  6. **Benchmark Question Curation**: Author $\ge 30$ multi-hop research questions across 5–10 papers *by hand* (not generated by the extraction model), establishing ground-truth evidence spans before prompt tuning.
  7. **Edge-Precision Spike & Go/No-Go Gate**: Extract graph from 5 papers; manually audit $\sim 100$ randomly sampled edges for factual accuracy.
     - **Go Rule**: Grounding Rate $\ge 80\%$ AND Audited Edge Precision $\ge 75\% \implies$ Proceed to Phase 2 schema migration.
     - **No-Go Rule**: Grounding Rate $< 80\%$ OR Audited Edge Precision $< 75\% \implies$ Halt; refine prompts, few-shot exemplars, and proximity constraints. Do not touch database schema.
* **Files Touched**:
  - `backend/app/services/clean.py` (bug fixes)
  - `backend/app/services/chunks.py` (new)
  - `backend/app/services/extractor.py` (new)
  - `backend/app/services/grounding.py` (new)
  - `benchmark/benchmark_questions_v1.json` (new hand-written questions)
  - `benchmark/phase1_extractions.jsonl` (spike output)
  - `benchmark/phase1_grounding_audit.jsonl` (audit results)

#### Phase 2: Unified Node Schema, Conservative Resolution & SSOT Migration
* **Tasks**:
  1. Execute schema upgrade script: create `nodes`, `node_aliases`, `entity_merge_log`, `entity_merge_pending`, `mentions`, `graph_relations`, `relation_evidence` with partial unique indexes.
  2. Migrate existing annotations to `mentions`, dynamically calculating `mentions.page` from the covering sentence row.
  3. Implement Exact-Match Auto-Aliasing (scoped by `node_type`) and Stage 2 LLM Adjudication ($\text{Sim} \ge 0.70$) with full tombstone repointing and logging to `entity_merge_log`.
  4. Log uncertain matches to `entity_merge_pending`.
* **Files Touched**:
  - `backend/app/models.py` (unified node schema with partial indexes)
  - `backend/app/migrations/001_unified_graph_schema.py` (new migration)
  - `backend/app/services/entity_resolution.py` (new)
  - `backend/app/routes/entities.py` (new CRUD & merge endpoints)

#### Phase 3: NetworkX Projection & Multi-Mode Cited Retrieval
* **Tasks**:
  1. Build `GraphProjectionService` (`backend/app/services/graph_service.py`) maintaining Postgres-backed `networkx.MultiDiGraph`.
  2. Implement multi-hop bidirectional graph expansion (`expand_graph_context`) with pre-RRF graph evidence scoring.
  3. Implement `retrieve_hybrid_context` combining vector hits and graph evidence via Reciprocal Rank Fusion.
  4. Add mode switch (`mode: 'vector' | 'graph' | 'hybrid'`) to `/documents/{id}/chat` and global `/chat`.
  5. Enhance `CitationChip.jsx` and `ReaderView.jsx` to resolve all citations (`[s*]` and `[r*]`) to underlying text spans with gold highlight pulses.
* **Files Touched**:
  - `backend/app/services/graph_service.py` (new)
  - `backend/app/services/chat_context.py` (multi-mode refactor)
  - `backend/app/routes/chat.py` (add mode parameter)
  - `frontend/src/components/ChatPanel.jsx` (mode toggle & citation upgrade)
  - `frontend/src/components/ReaderView.jsx` (span flashing)

#### Phase 4: Quantitative 4-Way Evaluation
* **Tasks**:
  1. Implement automated test runner (`benchmark/eval_runner.py`).
  2. Execute comparative evaluation across the two benchmark subdivisions:
     - **Subdivision 1 (Within-Document Multi-Hop)**: 4-way evaluation comparing:
       1. Pure Sentence Vector RAG
       2. Current DocuMesh Baseline (top-k sentences + annotations + 1-hop BFS)
       3. Graph-Only RAG
       4. Hybrid RAG
     - **Subdivision 2 (Cross-Document Multi-Hop)**: Evaluate Graph RAG and Hybrid RAG against a newly built **Corpus-Wide Sentence RAG Baseline**.
  3. Score metrics: Faithfulness (entailment), Citation Precision/Recall, and Answer Correctness.
* **Files Touched**:
  - `benchmark/eval_runner.py` (new)
  - `benchmark/corpus_vector_baseline.py` (new corpus vector baseline)
  - `docs/BENCHMARK_RESULTS.md` (output report)

#### Phase 5 (Deferred): Hierarchical Community Summaries
* **Trigger Criterion**: Implement only if corpus exceeds 50 documents and user explicitly requires corpus-wide thematic summarization.
* **Tasks**: Run Leiden clustering on global NetworkX graph; generate hierarchical cluster summaries.

---

## 8. API & Frontend Specification

### 8.1 API Endpoints

| Method | Endpoint | Description | Status |
| :--- | :--- | :--- | :--- |
| `POST` | `/documents/{id}/chat` | Enhanced with `mode: "vector" \| "graph" \| "hybrid"` | **Modified** |
| `POST` | `/chat` | Corpus-wide cross-document GraphRAG Q&A | **New** |
| `GET` | `/documents/{id}/chunks` | Retrieve chunk hierarchy with sentence indices | **New** |
| `GET` | `/nodes` | Search and filter canonical nodes (concepts & claims) | **New** |
| `GET` | `/nodes/{id}` | Inspect node details, aliases, and connected relations | **New** |
| `POST` | `/nodes/merge` | Manually merge two nodes with log entry | **New** |
| `POST` | `/nodes/revert-merge/{log_id}` | Revert a previous entity merge | **New** |
| `GET` | `/nodes/merge-pending` | List ambiguous pairs queued for review | **New** |
| `GET` | `/documents/{id}/graph/evidence` | Fetch exact text spans supporting a given relation | **New** |
| `GET` | `/documents/{id}/pdf` | Bug-fixed page-accurate highlight burn-in | **Modified** |

### 8.2 Frontend User Experience

1. **Retrieval Mode Selector**: A 3-way segmented control in `ChatPanel.jsx`:
   `[ Vector (Fast) | Graph (Relational) | Hybrid (Comprehensive) ]`.
2. **Span-Anchored Citation Pills**:
   - `[s12]`: Scrolls `ReaderView` directly to sentence 12 with a temporary gold highlight pulse.
   - `[r8]`: Highlights the relationship in `GraphView` and simultaneously pulses the underlying `relation_evidence` sentences in `ReaderView`.
   - `[e*]` citations are removed; all citations ground to concrete text spans.
3. **Deferred Entity Merge Drawer**: Merging UI is deferred until Phase 2/3 ambiguity rates are empirically quantified.

---

## 9. Official Pricing & Cost Model

### 9.1 Current Official Model Pricing (Checked November 2026)
* **OpenAI `gpt-4o-mini`**:
  - Source: OpenAI Official API Pricing (`https://openai.com/api/pricing/`, verified Nov 2026)
  - Input: $\$0.150$ per 1M tokens ($\$0.00015$ / 1k)
  - Output: $\$0.600$ per 1M tokens ($\$0.00060$ / 1k)
* **Anthropic `claude-3-5-haiku`**:
  - Source: Anthropic Official API Pricing (`https://www.anthropic.com/pricing`, verified Nov 2026)
  - Input: $\$0.800$ per 1M tokens ($\$0.00080$ / 1k)
  - Output: $\$4.000$ per 1M tokens ($\$0.00400$ / 1k)

### 9.2 Token Consumption per Academic Paper (Avg. 10 Pages, 30 Chunks)

| Operation | Calls / Paper | Input Tokens | Output Tokens | Est. Cost (`gpt-4o-mini`) | Est. Cost (`claude-3-5-haiku`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Chunk Extraction** | 30 | $30 \times 750 = 22{,}500$ | $30 \times 150 = 4{,}500$ | $\$0.0034 + \$0.0027 = \mathbf{\$0.0061}$ | $\$0.0180 + \$0.0180 = \mathbf{\$0.0360}$ |
| **Embeddings** | Local | $15{,}000$ | 0 | **$\$0.000$** (Sentence mean-pool) | **$\$0.000$** (Sentence mean-pool) |
| **Entity Adjudication** | *Calibrated in Ph. 1* | $\sim 3{,}200$ (est.) | $\sim 480$ (est.) | $\sim \mathbf{\$0.0008}$ (est.) | $\sim \mathbf{\$0.0045}$ (est.) |
| **Total Ingestion / Paper**| **~38 calls** | **$25{,}700$ tokens** | **$4{,}980$ tokens** | **~ $\$0.007$ / paper** | **~ $\$0.041$ / paper** |

*Note on Adjudication Volume*: The estimate of 8 ambiguous pairs per paper is provisional. The Phase 1 extraction spike across 5 papers will directly measure the pairwise cosine similarity distribution of extracted entity names to establish an empirically calibrated adjudication volume before Phase 2.

### 9.3 Latency Estimates & Concurrency
* **Chunk Extraction Latency**: Estimated $\sim 600 - 1200\text{ ms}$ per chunk; with concurrency semaphore ($N=5$), full 10-page paper extraction completes in an estimated $\sim 8 - 15\text{ seconds}$.
* **In-Memory Traversal Latency**: Estimated $\sim 1 - 5\text{ ms}$ for 2-hop BFS across $50{,}000$ edges in NetworkX.
* **Vector Search Latency**: Estimated $< 0.3\text{ ms}$ per document via NumPy; estimated $< 5\text{ ms}$ across $100{,}000$ chunks via `pgvector`.

---

## 10. Risk Register & Mitigations

| Risk | Impact | Probability | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **1. Extraction Hallucinations** | High | Medium | **Verbatim Grounding Rule**: Every triple requires an exact-match `evidence_quote` (post-whitespace normalization) and entity proximity within $\pm 1$ sentence (concepts), or it is discarded. |
| **2. Erroneous Entity Merging** | High | Low | **Zero Embedding Auto-Merge**: Auto-merges strictly limited to exact normalized names/aliases scoped by `node_type`. Ambiguous pairs ($\ge 0.70$) require LLM adjudication; all merges logged to `entity_merge_log` with tombstones for full reversibility. |
| **3. Super-Node Graph Distortion** | Medium | High | Broad terms (e.g. *"Method"*, *"Model"*) connect to hundreds of edges. **Mitigation**: Calculate degree centrality in NetworkX; penalize traversal across nodes with in-degree $> 50$ unless directly seeded by the query. |
| **4. PostgreSQL Concurrency** | Medium | Low | Ensure PostgreSQL is configured with connection pooling. Read-only graph traversals execute against in-memory NetworkX projection. |
| **5. LLM Prompt Drift** | Low | Medium | Strict Pydantic JSON schema validation. Malformed outputs trigger an automatic single retry with temperature 0.0. |

---

## 11. Decisive Open Questions for Stakeholders

Before proceeding to implementation, please confirm:

1. **Extraction LLM Default**: Should automated chunk extraction default to cloud APIs (`gpt-4o-mini` / `claude-3-5-haiku` at estimated $\sim \$0.007$–$\$0.041$ per 10-page paper) or would you prefer local LLM support via Ollama / vLLM (e.g., `llama-3.1-8b-instruct`)?
2. **Cross-Document Vector Index**: For corpus-wide search across thousands of chunks, do you prefer compiled **`pgvector`** using native PostgreSQL pgvector HNSW indexing?
3. **Paper Selection for Phase 1 Spike**: Which 5–10 papers in your repository should be used to author the 30+ multi-hop evaluation questions and run the $\sim 100$-edge precision spike?
