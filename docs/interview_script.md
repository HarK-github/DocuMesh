# DocuMesh: The Engineering Interview Spoken-Word Script & Playbook

> **How to use this playbook**: This is written in natural, first-person spoken cadence. Use the verbatim phrasing, pauses, and transition phrases to sound authoritative, practical, and deeply knowledgeable about systems architecture, numerical computing, and frontend rendering internals.

---

## ⏱️ Act 1: The 60-Second Elevator Pitch
*Use this when the interviewer opens with: **"Tell me about this project"** or **"Give me a high-level overview of DocuMesh."***

---

### 🎙️ Spoken Script:

> "Most AI document tools treat PDFs either as dumb images with sticky notes or as raw text to chunk blindly into a vector database. Both approaches lose the document’s actual epistemological structure.
>
> I built **DocuMesh** to bridge that gap. It’s an AI-assisted research workbench that transforms unstructured academic and technical PDFs into a dual-representation semantic mesh: continuous character-anchored text linked to a discrete epistemological knowledge graph—connecting claims, definitions, evidence, and results.
>
> Under the hood, I designed it with three core engineering priorities:
> 
> 1. **Robust Client-Side Reconciliation**: I built a 1D sweepline boundary-cut algorithm that slices overlapping text highlights into atomic visual segments, eliminating DOM mutation and text-layer drift in the PDF viewer.
> 2. **Ultra-Lean Embedded Vector Architecture**: Instead of pulling in a heavy external vector database like Chroma or Pinecone, I stored unit-normalized embeddings directly as binary `BLOB`s in SQLite and vectorized similarity search using NumPy BLAS level 2 matrix multiplications. This slashed container memory from **905 MB down to 35 MB** and cut cold-boot times to under two seconds.
> 3. **True Graph-RAG**: When querying the document, the system doesn’t just do flat vector retrieval; it expands context along confirmed semantic relations using multi-hop BFS and forces bracketed citation grounding—which our post-processor validates against active context IDs to eliminate hallucinated references.
>
> The result is a fast, responsive, zero-bloat platform running live on Vercel and Render."

---

## ⏱️ Act 2: The 3-Minute Architectural Deep-Dive
*Use this when the interviewer says: **"Walk me through the system architecture end-to-end"** or asks you to draw it on a whiteboard.*

---

### 🎨 Whiteboard Diagram to Sketch:

```
    [ User / Browser ] (React 18 + Vite)
            |
            | (Same-Origin /api/*)
            v
    [ Vercel Edge Reverse Proxy ]
            |
            | (HTTPS Proxy Pass)
            v
    [ FastAPI Backend ] (Render Container)
    +----------------------------------------------------------------+
    |  PyMuPDF Ingestion -> Counter Header Strip -> Canonical Text   |
    |  all-MiniLM-L6-v2 Embeddings -> SQLite WAL (Float32 BLOBs)     |
    +----------------------------------------------------------------+
            |                               |
            v                               v
    [ Recommendation Engine ]       [ Graph-RAG Chat Engine ]
    - Matrix @ Vector (BLAS)        - Top-K Seed Sentences & Nodes
    - MMR (\lambda = 0.7)           - 1-Hop BFS Relation Expansion
    - Hard Negative Mining          - Regex Citation Grounding
```

---

### 🎙️ Spoken Script:

> "Let me walk you through the lifecycle of a document from upload to interactive graph reasoning.
>
> ### 1. Ingestion & Canonical Text Normalization
> When a user uploads a PDF, PyMuPDF extracts raw text per page. But raw PDF text is messy—it has repeating headers, footers, soft-hyphens, and split words.
>
> Rather than relying on fuzzy heuristics, I built a deterministic cleaning pipeline in `clean.py`:
> * We collect the first and last non-empty lines across all pages and feed them into a Python `Counter`. Any line appearing two or more times across pages is identified as a repeated running header or footer and stripped.
> * We repair hyphenated breaks with regex—turning words like `architec-\n ture` back into `architecture`.
> * We reflow paragraphs while preserving double-newline boundaries, producing a single, canonical, immutable string: `clean_text`.
> * Every sentence is tokenized with exact `[start, end)` character offsets relative to this canonical string.
>
> ### 2. The Vector Engine (Why We Killed ChromaDB)
> Originally, the project used ChromaDB for vector search. But in production, Chroma brought massive C++ wheels, SQLite version lock conflicts, and over 200 MB of memory bloat.
>
> I realized that for a single paper, we only have between 200 and 2,000 sentences. We don't need a distributed vector index like HNSW or IVF-PQ.
>
> So I refactored the vector store into pure SQLite:
> * We encode sentences into 384-dimensional vectors using `all-MiniLM-L6-v2` and unit-normalize them.
> * We serialize the float32 array directly into bytes using Python’s buffer protocol and store it in an SQLite `LargeBinary` column.
> * To search, we load the candidate buffers directly into a continuous C-array matrix $\mathbf{M} \in \mathbb{R}^{N \times 384}$ with zero deserialization overhead and compute similarity via `matrix @ query_vector`.
> * This executes in less than **0.3 milliseconds** using CPU SIMD instructions, cutting container RAM by over **95%**.
>
> ### 3. Active Recommendation Loop (MMR + Negative Mining)
> When a user highlights a passage, they can ask the system to suggest related highlights across the paper.
>
> If you just do nearest-neighbor cosine search, it fails: you get 5 sentences from the same paragraph repeating the exact same point.
>
> To fix this, I implemented **Maximal Marginal Relevance (MMR)**:
> $$\text{MMR} = \operatorname*{argmax}_{d_i \in R \setminus S} \left[ \lambda \cdot \text{Score}(d_i) - (1 - \lambda) \cdot \max_{d_j \in S} \text{Sim}(d_i, d_j) \right]$$
> We set $\lambda = 0.7$. Furthermore, we incorporated **hard negative mining**: if a user clicks 'Reject' on a suggestion, its embedding is recorded. Future candidate scores penalize proximity to those rejected vectors by $0.5 \times \text{Sim}(c, \text{neg})$. This forces the model to actively explore unannotated conceptual areas of the paper.
>
> ### 4. Graph-RAG & Citation Grounding
> When the user queries the document, standard RAG would just embed the question and dump the top 3 chunks into the prompt.
>
> DocuMesh does **Graph-RAG**:
> * We embed the question and retrieve seed sentences and annotations.
> * Then, we perform an in-memory **1-hop BFS traversal** across confirmed semantic edges (`causes`, `supports`, `refutes`, `solves`). This pulls in critical context that vector search alone would miss because it uses different vocabulary.
> * We format the prompt with strict markdown fences and stable bracketed IDs: `[s1]`, `[a2]`, `[r3]`.
> * Finally, our post-processor regex extracts all citation tags from the LLM’s output and cross-checks them against the active context ID set. If the model hallucinates an ID that wasn't in the prompt, it’s discarded. Confirmed IDs are rendered as interactive pills that both pan the graph view and scroll the PDF viewer directly to the source text."

---

## ⏱️ Act 3: Frontend Deep-Dive (The Hard Engineering)
*Use this when the interviewer asks: **"What were the hardest frontend challenges you encountered?"***

---

### 🎙️ Spoken Script:

> "Building PDF annotation tools in the browser is notoriously tricky. There are two major pitfalls most developers fall into:
>
> ### Pitfall 1: Mutating the DOM with `<mark>` tags
> If you try to highlight text by wrapping browser text nodes in `<mark>` or `<span>` tags, you immediately corrupt the PDF.js text layer. It breaks font metrics, ruins mouse selection ranges, and crashes when highlights overlap or cross line wraps.
>
> **My Solution: 1D Sweepline Boundary Cut Algorithm**
> I kept the text completely immutable and implemented a 1D sweepline interval decomposition in `segments.js`:
> 1. We take all highlight intervals $[s_i, e_i)$ and collect their boundaries into a set of cut points: $C = \{0, L\} \cup \bigcup \{s_i, e_i\}$.
> 2. We sort $C$ chronologically: $c_0 < c_1 < \dots < c_k$.
> 3. Each slice $[c_j, c_{j+1})$ is an elementary, non-overlapping atomic span. We query which active annotations overlap that slice and render clean, styled spans without any DOM nesting errors.
> It runs in $O(M \log M)$ time and handles completely arbitrary nested or overlapping highlights deterministically.
>
> ### Pitfall 2: Text Selection vs Canonical Text Mismatch
> When a user selects text in a PDF viewer, `window.getSelection().toString()` includes weird layout artifacts—soft hyphens, split linebreaks, and variable spaces. If you search for that exact string in your cleaned backend text, it fails.
>
> **My Solution: The 3-Tier Reconciliation Cascade**
> In `offsets.js`, I built a 3-tier reconciliation engine:
> * **Tier 1**: Exact substring search starting from a hint offset.
> * **Tier 2**: Whitespace-normalized regex matching. We take the user's selected words, escape special characters, and join them with `\s+` (e.g., `/We\s+propose\s+Mesh/g`). This effortlessly bridges multi-line wraps and soft hyphens.
> * **Tier 3**: Case-insensitive fallback for scanned or OCR-noisy documents.
>
> Once resolved, we store immutable character indices $[start, end)$ which remain stable regardless of screen size, zoom level, or CSS responsive layout."

---

## ⏱️ Act 4: STAR Incident Stories (Battle-Tested Debugging)
*Use these when asked: **"Tell me about a difficult bug or production issue you solved."***

---

### 💥 Story A: The Render 512 MB OOM Crash Loop (`SIGKILL`)

| STAR Phase | What to Say |
| :--- | :--- |
| **Situation** | "When deploying the backend container to Render's free tier, the service entered an infinite crash-restart loop every 45 seconds, throwing `OOMKilled` (`exit code 137`)." |
| **Task** | "I had to diagnose why a lightweight FastAPI service was consuming more than the 512 MB memory limit allocated to the container." |
| **Action** | "I reproduced the container environment locally and profiled the memory footprint step-by-step using `tracemalloc` and Linux RSS metrics. I discovered that bare Python took 14 MB, but importing `torch` and instantiating `SentenceTransformer('all-MiniLM-L6-v2')` surged memory to **905 MB** the moment model weights loaded into CPU RAM.<br><br>Render’s Linux kernel cgroup controller was immediately terminating the process with `SIGKILL`.<br><br>Rather than paying for a larger server or letting the container crash, I implemented **automatic Linux cgroup memory inspection** in Python: reading `/sys/fs/cgroup/memory.max` (cgroup v2) or `memory.limit_in_bytes` (cgroup v1). If the container has $\le 768\text{ MB}$ or is running on Render, the system automatically falls back to an ultra-lightweight embedder." |
| **Result** | "Resident memory dropped from **905 MB to 35 MB**, the container booted in 1.8 seconds, and zero OOM kills occurred." |

---

### 💥 Story B: The uBlock Origin "CORS Null Status" Production Trap

| STAR Phase | What to Say |
| :--- | :--- |
| **Situation** | "After deploying our frontend to Vercel and backend to Render, users with ad blockers like uBlock Origin reported that the app said 'Server Offline'. In the browser console, the error appeared as: `Cross-Origin Request Blocked: (Reason: CORS request did not succeed). Status code: (null)`." |
| **Task** | "I needed to understand why CORS was supposedly failing when our FastAPI backend had `CORSMiddleware` configured to allow all Vercel origins." |
| **Action** | "I inspected the browser network tab and realized the HTTP request wasn't actually returning a 403 or 500—it had status code `(null)` and duration `0ms`. The request never even generated a TCP packet.<br><br>The root cause was uBlock Origin's EasyPrivacy list, which blocks third-party cross-origin requests to paths ending in `/health` or periodic polling beacons. The browser logs extension-canceled requests as generic CORS failures.<br><br>Instead of asking users to disable ad blockers, I re-architected our network flow: I configured a **Vercel Edge Reverse Proxy** in `vercel.json` routing `/api/*` directly to Render backend endpoints, and set frontend requests to use the same-origin relative path `/api`." |
| **Result** | "Because requests are now first-party and same-origin to the frontend domain, browser ad blockers treat them as legitimate application traffic. This eliminated both the blocking issue and the 150ms CORS preflight round-trip latency." |

---

## ⏱️ Act 5: Curveball Defense (Mastering the Toughest Questions)

---

### ❓ Q1: "Why did you build your own Graph-RAG instead of using LangChain or LlamaIndex?"
> **Your Answer**:
> "LangChain and LlamaIndex are great for rapid prototyping, but they introduce heavy speculative abstractions that make low-level debugging and latency optimization difficult.
>
> In our case, document epistemological graphs require exact character-offset anchoring, dynamic 1-hop BFS expansion across typed edges, and strict token-budgeted prompt construction with regex validation.
>
> By writing the retrieval pipeline in 150 lines of clean Python in `chat_context.py`, we eliminated hundreds of transitive dependencies, cut execution overhead, and gained full control over prompt construction and citation verification."

---

### ❓ Q2: "What happens if a user uploads a scanned PDF with no text layer?"
> **Your Answer**:
> "PyMuPDF extracts empty strings from scanned image pages. In our current architecture, the cleaning pipeline detects when `clean_text` has fewer than 15 characters and raises a validation error.
>
> As part of our roadmap, the natural extension is an asynchronous OCR worker using Tesseract or PaddleOCR that generates a synthetic text layer with bounding boxes, which our pipeline can ingest through the exact same character-offset normalization interface."

---

### ❓ Q3: "Doesn't computing cosine similarity with NumPy on CPU fail if you scale to millions of vectors?"
> **Your Answer**:
> "If we were searching across a global corpus of 10 million academic papers, yes—NumPy brute-force would be $O(N \cdot d)$ and we would need an approximate nearest neighbor (ANN) index like Milvus or Qdrant with HNSW graphs.
>
> But DocuMesh's core design constraint is **document-scoped mesh synthesis**. A single paper has between 200 and 2,000 sentences. Across 2,000 vectors of 384 dimensions, a NumPy BLAS dot-product takes less than **0.3 milliseconds**—which is faster than the network round-trip to an external vector database. Choosing NumPy over an external vector DB is an example of choosing the simplest tool that is mathematically optimal for the operational scale."

---

### ❓ Q4: "How do you handle race conditions when multiple users update annotations simultaneously?"
> **Your Answer**:
> "In the backend, SQLite is configured in **WAL mode (Write-Ahead Logging)**, which allows concurrent readers while a write occurs. For write contention on annotations and relations, we use SQLAlchemy transactions with optimistic versioning.
>
> On the frontend, TanStack React Query handles optimistic updates for UI responsiveness and uses deterministic query key invalidations to reconcile server state immediately after mutations complete."

---

## ⏱️ Act 6: The Closing Statement
*Use this when the interviewer asks: **"Do you have any final thoughts or questions for us?"***

---

### 🎙️ Spoken Script:

> "To wrap up: what I enjoyed most about building DocuMesh was the intersection of rigorous mathematical algorithms—like Maximal Marginal Relevance and Sweepline Interval Slicing—with real-world systems engineering—like memory profiling under Linux cgroups and edge reverse proxies.
>
> It’s easy to assemble AI apps by gluing together third-party APIs. But making them fast, reliable, lightweight, and deeply grounded in primary source documents requires caring about the bytes, the DOM, and the math. That’s the engineering mindset I bring to your team."
