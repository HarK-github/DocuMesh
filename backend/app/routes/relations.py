"""Relation CRUD and Graph view endpoints with taxonomy and cycle validation."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from backend.app.db import get_db
from backend.app.models import Document, Annotation, Relation, RelationType, Suggestion
from backend.app.schemas import (
    RelationCreate,
    RelationUpdate,
    RelationResponse,
    GraphResponse,
    AnnotationResponse,
)
from backend.app.services.clean import snap_to_word_boundaries

from backend.app.services.jobs import create_job, submit_job
from backend.app.services.llm import get_llm_client, LLMNotConfiguredError
from backend.app.services.relation_suggester import process_suggest_relations_job

router = APIRouter(tags=["Relations"])


@router.post("/documents/{document_id}/suggest-relations")
def suggest_relations(document_id: int, db: Session = Depends(get_db)) -> dict:
    """Trigger background LLM relationship discovery across annotation pairs."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        get_llm_client()
    except LLMNotConfiguredError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"LLM service is not configured: {str(exc)}",
        )

    job = create_job(db, job_type="suggest_relations", document_id=document_id)
    submit_job(job.id, process_suggest_relations_job, document_id)
    return {"job_id": job.id}


@router.get("/documents/{document_id}/relations", response_model=List[RelationResponse])
def list_relations(document_id: int, db: Session = Depends(get_db)) -> List[RelationResponse]:
    """Retrieve all relations for a document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return db.query(Relation).filter(Relation.document_id == document_id).all()


@router.post(
    "/documents/{document_id}/relations",
    response_model=RelationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_relation(
    document_id: int,
    payload: RelationCreate,
    db: Session = Depends(get_db),
) -> RelationResponse:
    """Create a typed relationship between two distinct annotations."""
    if payload.source_id == payload.target_id:
        raise HTTPException(
            status_code=422,
            detail="A relation cannot link an annotation to itself (self-link forbidden)",
        )

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    source_ann = (
        db.query(Annotation)
        .filter(Annotation.id == payload.source_id, Annotation.document_id == document_id)
        .first()
    )
    if not source_ann:
        raise HTTPException(status_code=404, detail="Source annotation not found in this document")

    target_ann = (
        db.query(Annotation)
        .filter(Annotation.id == payload.target_id, Annotation.document_id == document_id)
        .first()
    )
    if not target_ann:
        raise HTTPException(status_code=404, detail="Target annotation not found in this document")

    # Validate relation type against taxonomy
    rel_type_obj = db.query(RelationType).filter(RelationType.name == payload.type).first()
    if not rel_type_obj:
        raise HTTPException(status_code=422, detail=f"Relation type '{payload.type}' is not in the taxonomy")

    relation = Relation(
        document_id=document_id,
        source_id=payload.source_id,
        target_id=payload.target_id,
        type=payload.type,
        status=payload.status or "confirmed",
        reason=payload.reason,
        version=1,
    )
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return relation


@router.patch("/relations/{relation_id}", response_model=RelationResponse)
def update_relation(
    relation_id: int,
    payload: RelationUpdate,
    db: Session = Depends(get_db),
) -> RelationResponse:
    """Update a relation with optimistic locking version check."""
    relation = db.query(Relation).filter(Relation.id == relation_id).first()
    if not relation:
        raise HTTPException(status_code=404, detail="Relation not found")

    if relation.version != payload.version:
        raise HTTPException(
            status_code=409,
            detail="Stale edit: relation has been modified by another process",
        )

    if payload.type is not None:
        rel_type_obj = db.query(RelationType).filter(RelationType.name == payload.type).first()
        if not rel_type_obj:
            raise HTTPException(status_code=422, detail=f"Relation type '{payload.type}' is not in the taxonomy")
        relation.type = payload.type

    if payload.status is not None:
        relation.status = payload.status
    if payload.reason is not None:
        relation.reason = payload.reason

    try:
        db.commit()
        db.refresh(relation)
    except StaleDataError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Stale edit: concurrent update detected",
        )

    return relation


@router.delete("/relations/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relation(relation_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a relation."""
    relation = db.query(Relation).filter(Relation.id == relation_id).first()
    if not relation:
        raise HTTPException(status_code=404, detail="Relation not found")
    db.delete(relation)
    db.commit()
    return None


@router.get("/documents/{document_id}/graph", response_model=GraphResponse)
def get_document_graph(document_id: int, db: Session = Depends(get_db)) -> GraphResponse:
    """Retrieve full graph view: annotations (nodes), relations (edges), and pending suggestions as ghost nodes."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    annotations = db.query(Annotation).filter(Annotation.document_id == document_id).all()
    relations = db.query(Relation).filter(Relation.document_id == document_id).all()

    nodes: List[AnnotationResponse] = [
        AnnotationResponse(
            id=a.id,
            document_id=a.document_id,
            start=a.start,
            end=a.end,
            quote=a.quote,
            label=a.label,
            note=a.note,
            x=a.x,
            y=a.y,
            version=a.version,
            created_at=a.created_at,
            status="confirmed",
        )
        for a in annotations
    ]

    edges: List[RelationResponse] = [
        RelationResponse(
            id=r.id,
            document_id=r.document_id,
            source_id=r.source_id,
            target_id=r.target_id,
            type=r.type,
            status=r.status or "confirmed",
            reason=r.reason,
            version=r.version,
        )
        for r in relations
    ]

    # Query pending suggestions and append as ghost nodes and similar_to edges
    pending_sugs = (
        db.query(Suggestion)
        .filter(
            Suggestion.document_id == document_id,
            Suggestion.status == "pending",
        )
        .all()
    )

    for sug in pending_sugs:
        sent = sug.sentence
        if sent and doc.clean_text:
            s_start, s_end = snap_to_word_boundaries(doc.clean_text, sent.start, sent.end)
            quote = doc.clean_text[s_start:s_end]
        else:
            s_start, s_end = (sent.start, sent.end) if sent else (0, 0)
            quote = ""

        ghost_node = AnnotationResponse(
            id=sug.id,
            document_id=sug.document_id,
            start=s_start,
            end=s_end,
            quote=quote,
            label=sug.label or "Claim",
            note=f"Suggested highlight ({int(sug.score * 100)}% match)",
            x=0.0,
            y=0.0,
            version=1,
            created_at=None,
            status="suggested",
            score=round(sug.score, 4),
            sentence_id=sug.sentence_id,
            seed_annotation_id=sug.seed_annotation_id,
        )
        nodes.append(ghost_node)

        if sug.seed_annotation_id:
            ghost_edge = RelationResponse(
                id=-(sug.id),
                document_id=document_id,
                source_id=sug.id,
                target_id=sug.seed_annotation_id,
                type="similar_to",
                status="suggested",
                reason=str(round(sug.score, 4)),
                version=1,
                score=round(sug.score, 4),
            )
            edges.append(ghost_edge)

    return GraphResponse(
        document_id=document_id,
        annotations=nodes,
        relations=edges,
    )
