"""Smart highlight suggestions endpoints based on embedding similarity."""

from typing import List
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.models import Document, Sentence, Annotation, Suggestion, Label
from backend.app.schemas import SuggestionResponse
from backend.app.services.embedder import get_embedder
from backend.app.services.ranker import rank_sentences

router = APIRouter(tags=["Suggestions"])


def _deserialize_embedding(blob: bytes) -> np.ndarray:
    """Convert stored BLOB into 1D float32 numpy array."""
    return np.frombuffer(blob, dtype=np.float32)


def _serialize_embedding(arr: np.ndarray) -> bytes:
    """Convert numpy array into raw byte string for BLOB storage."""
    return np.asarray(arr, dtype=np.float32).tobytes()


@router.get("/documents/{document_id}/suggestions", response_model=List[SuggestionResponse])
def list_suggestions(document_id: int, db: Session = Depends(get_db)) -> List[SuggestionResponse]:
    """Retrieve all highlight suggestions for a document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    suggestions = (
        db.query(Suggestion)
        .filter(Suggestion.document_id == document_id)
        .order_by(Suggestion.score.desc())
        .all()
    )

    results = []
    for sug in suggestions:
        sent = sug.sentence
        quote = doc.clean_text[sent.start:sent.end] if doc.clean_text else ""
        results.append(
            SuggestionResponse(
                id=sug.id,
                document_id=sug.document_id,
                sentence_id=sug.sentence_id,
                score=sug.score,
                status=sug.status,
                start=sent.start,
                end=sent.end,
                quote=quote,
                page=sent.page,
            )
        )
    return results


@router.post("/documents/{document_id}/suggest-highlights", response_model=List[SuggestionResponse])
def generate_highlight_suggestions(
    document_id: int,
    db: Session = Depends(get_db),
) -> List[SuggestionResponse]:
    """Rank sentences and generate pending smart highlight suggestions."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    sentences = (
        db.query(Sentence)
        .filter(Sentence.document_id == document_id)
        .order_by(Sentence.idx)
        .all()
    )
    if not sentences:
        return []

    embedder = get_embedder()

    # Ensure sentence embeddings are populated
    missing_texts = []
    missing_indices = []
    for idx, s in enumerate(sentences):
        if s.embedding is None and doc.clean_text:
            text = doc.clean_text[s.start:s.end]
            missing_texts.append(text)
            missing_indices.append(idx)

    if missing_texts:
        computed = embedder.embed(missing_texts)
        for i, emb in zip(missing_indices, computed):
            sentences[i].embedding = _serialize_embedding(emb)
        db.commit()

    # Gather positive vectors from existing annotations
    annotations = db.query(Annotation).filter(Annotation.document_id == document_id).all()
    positive_embs = []
    if annotations:
        ann_quotes = [a.quote for a in annotations]
        positive_embs = list(embedder.embed(ann_quotes))
    else:
        # Seed with first sentence if no annotations exist yet
        if sentences[0].embedding is not None:
            positive_embs = [_deserialize_embedding(sentences[0].embedding)]

    # Gather negative vectors from rejected suggestions
    rejected_sugs = (
        db.query(Suggestion)
        .filter(Suggestion.document_id == document_id, Suggestion.status == "rejected")
        .all()
    )
    negative_embs = [
        _deserialize_embedding(s.sentence.embedding)
        for s in rejected_sugs
        if s.sentence.embedding is not None
    ]

    # Prepare sentence candidate dicts for ranker
    candidates = []
    for s in sentences:
        if s.embedding is not None:
            candidates.append({
                "id": s.id,
                "start": s.start,
                "end": s.end,
                "page": s.page,
                "embedding": _deserialize_embedding(s.embedding),
            })

    existing_ann_ranges = [{"start": a.start, "end": a.end} for a in annotations]

    ranked = rank_sentences(
        sentences=candidates,
        positive_embeddings=positive_embs,
        negative_embeddings=negative_embs,
        existing_annotations=existing_ann_ranges,
    )

    # Delete existing pending suggestions to avoid duplicates
    db.query(Suggestion).filter(
        Suggestion.document_id == document_id,
        Suggestion.status == "pending",
    ).delete(synchronize_session=False)

    new_suggestions = []
    for cand, score in ranked:
        sug = Suggestion(
            document_id=document_id,
            sentence_id=cand["id"],
            score=score,
            status="pending",
        )
        db.add(sug)
        new_suggestions.append(sug)

    db.commit()

    # Format response
    results = []
    for sug in new_suggestions:
        sent = db.query(Sentence).filter(Sentence.id == sug.sentence_id).first()
        quote = doc.clean_text[sent.start:sent.end] if doc.clean_text else ""
        results.append(
            SuggestionResponse(
                id=sug.id,
                document_id=sug.document_id,
                sentence_id=sug.sentence_id,
                score=sug.score,
                status=sug.status,
                start=sent.start,
                end=sent.end,
                quote=quote,
                page=sent.page,
            )
        )
    return results


@router.post("/suggestions/{suggestion_id}/accept", response_model=SuggestionResponse)
def accept_suggestion(suggestion_id: int, db: Session = Depends(get_db)) -> SuggestionResponse:
    """Accept a suggestion: create an annotation and update suggestion status idempotently."""
    sug = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
    if not sug:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    sent = sug.sentence
    doc = sug.document

    # If already accepted, return existing result idempotently
    if sug.status != "accepted":
        # Create annotation for this sentence
        quote = doc.clean_text[sent.start:sent.end] if doc.clean_text else ""
        default_label = db.query(Label).first()
        label_name = default_label.name if default_label else "Claim"

        ann = Annotation(
            document_id=doc.id,
            start=sent.start,
            end=sent.end,
            quote=quote,
            label=label_name,
            note="Created from smart highlight suggestion",
            version=1,
        )
        db.add(ann)
        sug.status = "accepted"
        db.commit()

    quote = doc.clean_text[sent.start:sent.end] if doc.clean_text else ""
    return SuggestionResponse(
        id=sug.id,
        document_id=sug.document_id,
        sentence_id=sug.sentence_id,
        score=sug.score,
        status=sug.status,
        start=sent.start,
        end=sent.end,
        quote=quote,
        page=sent.page,
    )


@router.post("/suggestions/{suggestion_id}/reject", response_model=SuggestionResponse)
def reject_suggestion(suggestion_id: int, db: Session = Depends(get_db)) -> SuggestionResponse:
    """Reject a suggestion idempotently."""
    sug = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
    if not sug:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    sug.status = "rejected"
    db.commit()

    sent = sug.sentence
    doc = sug.document
    quote = doc.clean_text[sent.start:sent.end] if doc.clean_text else ""

    return SuggestionResponse(
        id=sug.id,
        document_id=sug.document_id,
        sentence_id=sug.sentence_id,
        score=sug.score,
        status=sug.status,
        start=sent.start,
        end=sent.end,
        quote=quote,
        page=sent.page,
    )
