"""Document ingestion pipeline combining extraction, cleaning, segmentation, and lexical chunking."""

from typing import Dict, Any, Optional
import numpy as np

from backend.app.db import get_session_factory
from backend.app.models import Document, Sentence
from backend.app.services.extract import extract_pages
from backend.app.services.clean import clean_extracted_pages
from backend.app.services.sentences import segment_sentences
from backend.app.services.chunks import store_chunks_for_document
from backend.app.services.jobs import update_job_status
from backend.app.services.embedder import get_embedder


def process_document(job_id: Optional[str], document_id: int, pdf_path: str) -> Dict[str, Any]:
    """Execute end-to-end ingestion pipeline: extraction -> cleaning -> sentence segmentation -> lexical chunking."""
    session_factory = get_session_factory()
    try:
        if job_id:
            update_job_status(job_id, status="running", progress=15)

        # 1. Extraction
        raw_pages = extract_pages(pdf_path)
        if job_id:
            update_job_status(job_id, progress=35)

        # 2. Cleaning
        clean_pages = clean_extracted_pages(raw_pages)
        if job_id:
            update_job_status(job_id, progress=50)

        # Validate that document has extractable text (graceful handling of scanned/empty PDFs)
        total_chars = sum(len(str(p.get("text", ""))) for p in clean_pages)
        if total_chars < 20:
            raise ValueError("Scanned or empty PDF: No extractable text found. OCR is required.")

        # 3. Sentence segmentation
        clean_text, sentences_data = segment_sentences(clean_pages)
        if job_id:
            update_job_status(job_id, progress=65)

        # 4. Sentence embedding computation
        embeddings = None
        sentence_vecs = None
        embedder = None
        try:
            embedder = get_embedder()
            sentence_texts = [str(s["text"]) for s in sentences_data]
            if sentence_texts:
                embeddings = embedder.embed(sentence_texts)
                sentence_vecs = [np.asarray(e, dtype=np.float32) for e in embeddings]
        except Exception:
            pass

        # 5. Save sentences to database
        with session_factory() as session:
            doc = session.query(Document).filter(Document.id == document_id).first()
            if not doc:
                raise ValueError(f"Document {document_id} not found")

            doc.clean_text = clean_text
            doc.status = "ready"

            # Remove existing sentences if re-processing
            session.query(Sentence).filter(Sentence.document_id == document_id).delete()

            for i, s_info in enumerate(sentences_data):
                emb_val = None
                if embeddings is not None and i < len(embeddings):
                    emb_val = np.asarray(embeddings[i], dtype=np.float32).tolist()

                sent_obj = Sentence(
                    document_id=document_id,
                    idx=int(s_info["idx"]),
                    start=int(s_info["start"]),
                    end=int(s_info["end"]),
                    page=int(s_info["page"]),
                    embedding=emb_val,
                )
                session.add(sent_obj)

            session.commit()

            # 6. Lexical Layer: Store contextual token-bounded chunks and link annotations
            created_chunks = store_chunks_for_document(
                session=session,
                document_id=document_id,
                clean_text=clean_text,
                sentences_data=sentences_data,
                embedder=embedder,
                sentence_embeddings=sentence_vecs,
            )

        if job_id:
            update_job_status(job_id, status="done", progress=100)

        return {
            "document_id": document_id,
            "sentence_count": len(sentences_data),
            "chunk_count": len(created_chunks),
        }

    except Exception as exc:
        with session_factory() as session:
            doc = session.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = "failed"
                session.commit()
        if job_id:
            update_job_status(job_id, status="failed", error=str(exc))
        raise
