"""Pure sentence vector RAG baseline (within-document and corpus-wide)."""

from typing import List, Dict, Any, Optional
import numpy as np
from sqlalchemy.orm import Session

from backend.app.models import Sentence, Document
from backend.app.services.embedder import BaseEmbedder, get_embedder
from backend.app.services.ranker import cosine_similarity
from backend.app.services.llm import BaseLLMClient, get_llm_client
from backend.app.services.chat_context import CHAT_SYSTEM_PROMPT, validate_citations
from backend.app.settings import get_settings


def retrieve_pure_vector_sentences(
    db: Session,
    question: str,
    document_id: Optional[int] = None,
    top_k: int = 5,
    embedder: Optional[BaseEmbedder] = None,
) -> List[Dict[str, Any]]:
    """Retrieve top-k sentences purely by cosine similarity without graph or annotations."""
    embedder = embedder or get_embedder()
    q_emb = embedder.embed([question])[0]

    q = db.query(Sentence).join(Document, Document.id == Sentence.document_id)
    if document_id is not None:
        q = q.filter(Sentence.document_id == document_id)

    scored = []
    for s in q.all():
        if s.embedding is None:
            continue
        s_emb = np.frombuffer(s.embedding, dtype=np.float32)
        sim = cosine_similarity(q_emb, s_emb)
        clean_text = s.document.clean_text if s.document else ""
        text = clean_text[s.start : s.end] if clean_text else ""
        scored.append({
            "id": s.id,
            "document_id": s.document_id,
            "start": s.start,
            "end": s.end,
            "page": s.page,
            "text": text,
            "score": float(sim),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def answer_pure_vector_rag(
    db: Session,
    question: str,
    document_id: Optional[int] = None,
    top_k: int = 5,
    embedder: Optional[BaseEmbedder] = None,
    llm: Optional[BaseLLMClient] = None,
) -> Dict[str, Any]:
    """Execute pure sentence vector RAG and return answer and citations."""
    settings = get_settings()
    llm = llm or get_llm_client()
    sentences = retrieve_pure_vector_sentences(
        db, question, document_id=document_id, top_k=top_k, embedder=embedder
    )

    if not sentences:
        return {"answer": "I couldn't find this in the document.", "citations": [], "context": []}

    lines = []
    items_by_id = {}
    active_ids = set()
    for s in sentences:
        cid = f"s{s['id']}"
        active_ids.add(cid)
        items_by_id[cid] = {
            "type": "sentence",
            "id": s["id"],
            "start": s.get("start"),
            "end": s.get("end"),
            "page": s.get("page"),
            "text": s.get("text"),
        }
        lines.append(f"[{cid}] {s['text'].strip()}")

    context_str = "Document Sentences:\n" + "\n".join(lines)
    system_prompt = f"{CHAT_SYSTEM_PROMPT}\n\n=== Context (Pure Vector) ===\n{context_str}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    answer = llm.complete(messages)
    citations = validate_citations(answer, active_ids, items_by_id)

    return {
        "answer": answer,
        "citations": citations,
        "context": sentences,
    }
