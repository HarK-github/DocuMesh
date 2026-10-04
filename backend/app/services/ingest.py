"""Document ingestion pipeline combining extraction, cleaning, and segmentation."""

from typing import Dict, Any, Optional
from backend.app.db import get_session_factory
from backend.app.models import Document, Sentence
from backend.app.services.extract import extract_pages
from backend.app.services.clean import clean_extracted_pages
from backend.app.services.sentences import segment_sentences
from backend.app.services.jobs import update_job_status


def process_document(job_id: Optional[str], document_id: int, pdf_path: str) -> Dict[str, Any]:
    """Execute end-to-end ingestion pipeline for a document."""
    session_factory = get_session_factory()
    try:
        if job_id:
            update_job_status(job_id, status="running", progress=20)

        # 1. Extraction
        raw_pages = extract_pages(pdf_path)
        if job_id:
            update_job_status(job_id, progress=40)

        # 2. Cleaning
        clean_pages = clean_extracted_pages(raw_pages)
        if job_id:
            update_job_status(job_id, progress=60)

        # 3. Sentence segmentation
        clean_text, sentences_data = segment_sentences(clean_pages)
        if job_id:
            update_job_status(job_id, progress=80)

        # 4. Optional embedding computation (Phase 5)
        embeddings = None
        try:
            from backend.app.services.embedder import get_embedder
            embedder = get_embedder()
            sentence_texts = [str(s["text"]) for s in sentences_data]
            if sentence_texts:
                embeddings = embedder.embed(sentence_texts)
        except Exception:
            pass

        # 5. Save to database
        with session_factory() as session:
            doc = session.query(Document).filter(Document.id == document_id).first()
            if not doc:
                raise ValueError(f"Document {document_id} not found")

            doc.clean_text = clean_text
            doc.status = "ready"

            # Remove existing sentences if re-processing
            session.query(Sentence).filter(Sentence.document_id == document_id).delete()

            for i, s_info in enumerate(sentences_data):
                emb_bytes = None
                if embeddings is not None and i < len(embeddings):
                    import numpy as np
                    emb_bytes = np.asarray(embeddings[i], dtype=np.float32).tobytes()

                sent_obj = Sentence(
                    document_id=document_id,
                    idx=int(s_info["idx"]),
                    start=int(s_info["start"]),
                    end=int(s_info["end"]),
                    page=int(s_info["page"]),
                    embedding=emb_bytes,
                )
                session.add(sent_obj)

            session.commit()

            # Index sentence vectors into vector store
            try:
                from backend.app.services.vector_store import get_vector_store
                import numpy as np

                store = get_vector_store()
                store_items = []
                saved_sentences = (
                    session.query(Sentence)
                    .filter(Sentence.document_id == document_id, Sentence.embedding.isnot(None))
                    .all()
                )
                for s in saved_sentences:
                    store_items.append({
                        "id": f"doc_{document_id}_sent_{s.id}",
                        "vector": np.frombuffer(s.embedding, dtype=np.float32),
                        "metadata": {
                            "document_id": document_id,
                            "sentence_id": s.id,
                            "start": s.start,
                            "end": s.end,
                            "page": s.page,
                        },
                    })
                if store_items:
                    store.add(store_items)
            except Exception:
                pass

        if job_id:
            update_job_status(job_id, status="done", progress=100)

        return {"document_id": document_id, "sentence_count": len(sentences_data)}

    except Exception as exc:
        with session_factory() as session:
            doc = session.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = "failed"
                session.commit()
        if job_id:
            update_job_status(job_id, status="failed", error=str(exc))
        raise
