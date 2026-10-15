"""Annotation CRUD endpoints with offset, quote, taxonomy, and version validation."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from backend.app.db import get_db
from backend.app.models import Document, Annotation, Relation, Label, Suggestion
from backend.app.schemas import AnnotationCreate, AnnotationUpdate, AnnotationResponse
from backend.app.services.clean import snap_to_word_boundaries

router = APIRouter(tags=["Annotations"])


@router.get("/documents/{document_id}/annotations", response_model=List[AnnotationResponse])
def list_annotations(document_id: int, db: Session = Depends(get_db)) -> List[AnnotationResponse]:
    """Retrieve all annotations for a document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return db.query(Annotation).filter(Annotation.document_id == document_id).all()


@router.post(
    "/documents/{document_id}/annotations",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_annotation(
    document_id: int,
    payload: AnnotationCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> AnnotationResponse:
    """Create a new text annotation validating quote match, snapping boundaries, and taxonomy."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if payload.start >= payload.end:
        raise HTTPException(status_code=422, detail="start offset must be strictly less than end offset")

    if not doc.clean_text:
        raise HTTPException(status_code=422, detail="Document clean_text is empty or not yet processed")

    if payload.end > len(doc.clean_text) or payload.start < 0:
        raise HTTPException(status_code=422, detail="Offsets exceed document clean_text boundaries")

    import re

    # 1. Snap start and end to nearest word boundaries
    snapped_start, snapped_end = snap_to_word_boundaries(doc.clean_text, payload.start, payload.end)
    expected_quote = doc.clean_text[snapped_start:snapped_end]

    raw_quote = payload.quote.strip() if payload.quote else ""

    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    quote_matches = (
        payload.quote == expected_quote
        or payload.quote == doc.clean_text[payload.start:payload.end]
        or _norm(payload.quote) == _norm(expected_quote)
        or _norm(payload.quote) == _norm(doc.clean_text[payload.start:payload.end])
    )

    if not quote_matches and raw_quote:
        # Fallback: search for quote within doc.clean_text
        found_idx = doc.clean_text.find(raw_quote)
        found_len = len(raw_quote)
        if found_idx == -1:
            words = [re.escape(w) for w in raw_quote.split() if w]
            if words:
                pat = re.compile(r"\s+".join(words), re.IGNORECASE)
                m = pat.search(doc.clean_text)
                if m:
                    found_idx = m.start()
                    found_len = m.end() - m.start()

        if found_idx != -1:
            snapped_start, snapped_end = snap_to_word_boundaries(
                doc.clean_text, found_idx, found_idx + found_len
            )
            expected_quote = doc.clean_text[snapped_start:snapped_end]
            quote_matches = True

    if not quote_matches:
        raise HTTPException(
            status_code=422,
            detail=f"Quote mismatch: expected '{expected_quote}', received '{payload.quote}'",
        )

    # 2. Check for duplicate: (document_id, start, end, label)
    existing = (
        db.query(Annotation)
        .filter(
            Annotation.document_id == document_id,
            Annotation.start == snapped_start,
            Annotation.end == snapped_end,
            Annotation.label == payload.label,
        )
        .first()
    )
    if existing:
        response.status_code = status.HTTP_200_OK
        return existing

    # Validate label against taxonomy
    label_obj = db.query(Label).filter(Label.name == payload.label).first()
    if not label_obj:
        raise HTTPException(status_code=422, detail=f"Label '{payload.label}' is not in the taxonomy")

    annotation = Annotation(
        document_id=document_id,
        start=snapped_start,
        end=snapped_end,
        quote=expected_quote,
        label=payload.label,
        note=payload.note,
        x=payload.x or 0.0,
        y=payload.y or 0.0,
        version=1,
    )
    db.add(annotation)

    # 3. Mark overlapping pending suggestions as superseded
    pending_sugs = (
        db.query(Suggestion)
        .filter(
            Suggestion.document_id == document_id,
            Suggestion.status == "pending",
        )
        .all()
    )
    for sug in pending_sugs:
        if sug.sentence:
            if max(sug.sentence.start, snapped_start) < min(sug.sentence.end, snapped_end):
                sug.status = "superseded"

    db.commit()
    db.refresh(annotation)
    return annotation


@router.patch("/annotations/{annotation_id}", response_model=AnnotationResponse)
def update_annotation(
    annotation_id: int,
    payload: AnnotationUpdate,
    db: Session = Depends(get_db),
) -> AnnotationResponse:
    """Update annotation metadata with optimistic locking version check."""
    annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    if annotation.version != payload.version:
        raise HTTPException(
            status_code=409,
            detail="Stale edit: annotation has been modified by another process",
        )

    doc = annotation.document

    # Adjust start and end boundaries if provided
    new_start = payload.start if payload.start is not None else annotation.start
    new_end = payload.end if payload.end is not None else annotation.end

    if payload.start is not None or payload.end is not None:
        if new_start >= new_end:
            raise HTTPException(status_code=422, detail="start offset must be strictly less than end offset")
        if doc and doc.clean_text:
            if new_start < 0 or new_end > len(doc.clean_text):
                raise HTTPException(status_code=422, detail="Offsets exceed document clean_text boundaries")
            snapped_start, snapped_end = snap_to_word_boundaries(doc.clean_text, new_start, new_end)
            annotation.start = snapped_start
            annotation.end = snapped_end
            annotation.quote = doc.clean_text[snapped_start:snapped_end]
        else:
            annotation.start = new_start
            annotation.end = new_end

        # Mark overlapping pending suggestions as superseded
        pending_sugs = (
            db.query(Suggestion)
            .filter(
                Suggestion.document_id == annotation.document_id,
                Suggestion.status == "pending",
            )
            .all()
        )
        for sug in pending_sugs:
            if sug.sentence:
                if max(sug.sentence.start, annotation.start) < min(sug.sentence.end, annotation.end):
                    sug.status = "superseded"

    if payload.label is not None:
        label_obj = db.query(Label).filter(Label.name == payload.label).first()
        if not label_obj:
            raise HTTPException(status_code=422, detail=f"Label '{payload.label}' is not in the taxonomy")
        annotation.label = payload.label

    if payload.note is not None:
        annotation.note = payload.note
    if payload.x is not None:
        annotation.x = payload.x
    if payload.y is not None:
        annotation.y = payload.y

    try:
        db.commit()
        db.refresh(annotation)
    except StaleDataError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Stale edit: concurrent update detected",
        )

    return annotation



@router.delete("/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_annotation(annotation_id: int, db: Session = Depends(get_db)) -> None:
    """Delete an annotation and cascade delete all its connected relations."""
    annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    # Cascade delete any relations referencing this annotation
    db.query(Relation).filter(
        (Relation.source_id == annotation_id) | (Relation.target_id == annotation_id)
    ).delete(synchronize_session=False)

    db.delete(annotation)
    db.commit()
    return None
