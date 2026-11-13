"""Service and CLI utility to re-index lexical chunks and annotation links for documents."""

import argparse
import sys
from typing import Dict, Any
import numpy as np

from backend.app.db import get_session_factory, init_db
from backend.app.models import Document, Sentence
from backend.app.services.chunks import store_chunks_for_document
from backend.app.services.embedder import get_embedder


def reindex_document(document_id: int) -> Dict[str, Any]:
    """Re-chunk full document text, embed each chunk, and link annotations."""
    session_factory = get_session_factory()
    init_db()

    with session_factory() as session:
        doc = session.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")
        if not doc.clean_text:
            raise ValueError(f"Document {document_id} has no clean_text")

        sentence_rows = (
            session.query(Sentence)
            .filter(Sentence.document_id == document_id)
            .order_by(Sentence.idx.asc())
            .all()
        )

        sentences_data = [
            {
                "idx": s.idx,
                "start": s.start,
                "end": s.end,
                "page": s.page,
                "text": doc.clean_text[s.start:s.end],
                "embedding": s.embedding,
            }
            for s in sentence_rows
        ]

        embedder = get_embedder()
        sentence_vecs = []
        for s in sentences_data:
            if s["embedding"] is not None:
                sentence_vecs.append(np.asarray(s["embedding"], dtype=np.float32))
            else:
                sentence_vecs.append(None)

        chunks = store_chunks_for_document(
            session=session,
            document_id=document_id,
            clean_text=doc.clean_text,
            sentences_data=sentences_data,
            embedder=embedder,
            sentence_embeddings=sentence_vecs,
        )

        return {
            "document_id": document_id,
            "sentence_count": len(sentences_data),
            "chunk_count": len(chunks),
            "status": "success",
        }


def main():
    parser = argparse.ArgumentParser(description="Re-index lexical layer for a document.")
    parser.add_argument("--doc", type=int, required=True, help="Document ID to re-index")
    args = parser.parse_args()

    print(f"Re-indexing document {args.doc}...")
    res = reindex_document(args.doc)
    print(f"Re-indexing complete: {res}")


if __name__ == "__main__":
    main()
