"""Annotation CRUD endpoints with offset, quote, taxonomy, and version validation."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from backend.app.db import get_db
from backend.app.models import Document, Annotation, Relation, Label
from backend.app.schemas import AnnotationCreate, AnnotationUpdate, AnnotationResponse

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
    db: Session = Depends(get_db),
) -> AnnotationResponse:
    """Create a new text annotation validating quote match and taxonomy."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if payload.start >= payload.end:
        raise HTTPException(status_code=422, detail="start offset must be strictly less than end offset")

    if not doc.clean_text:
        raise HTTPException(status_code=422, detail="Document clean_text is empty or not yet processed")

    if payload.end > len(doc.clean_text) or payload.start < 0:
        raise HTTPException(status_code=422, detail="Offsets exceed document clean_text boundaries")

    expected_quote = doc.clean_text[payload.start:payload.end]
    if payload.quote != expected_quote:
        raise HTTPException(
            status_code=422,
            detail=f"Quote mismatch: expected '{expected_quote}', received '{payload.quote}'",
        )

    # Validate label against taxonomy
    label_obj = db.query(Label).filter(Label.name == payload.label).first()
    if not label_obj:
        raise HTTPException(status_code=422, detail=f"Label '{payload.label}' is not in the taxonomy")

    annotation = Annotation(
        document_id=document_id,
        start=payload.start,
        end=payload.end,
        quote=payload.quote,
        label=payload.label,
        note=payload.note,
        x=payload.x or 0.0,
        y=payload.y or 0.0,
        version=1,
    )
    db.add(annotation)
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
