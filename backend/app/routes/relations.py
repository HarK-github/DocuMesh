"""Relation CRUD and Graph view endpoints with taxonomy and cycle validation."""

from collections import deque, defaultdict
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from backend.app.db import get_db
from backend.app.models import Document, Annotation, Relation, Suggestion, RejectedPair
from backend.app.taxonomy import is_valid_relation_type
from backend.app.schemas import (
    RelationCreate,
    RelationUpdate,
    RelationResponse,
    GraphResponse,
    AnnotationResponse,
    SuggestRelationsRequest,
    PathsResponse,
    PathItem,
    PathEdge,
)
from backend.app.services.clean import snap_to_word_boundaries

from backend.app.services.jobs import create_job, submit_job
from backend.app.services.llm import get_llm_client, LLMNotConfiguredError
from backend.app.services.relation_suggester import process_suggest_relations_job

router = APIRouter(tags=["Relations"])


@router.post("/documents/{document_id}/suggest-relations")
def suggest_relations(
    document_id: int,
    payload: Optional[SuggestRelationsRequest] = None,
    db: Session = Depends(get_db),
) -> dict:
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

    seed_annotation_id = payload.seed_annotation_id if payload else None
    job = create_job(db, job_type="suggest_relations", document_id=document_id)
    submit_job(job.id, process_suggest_relations_job, document_id, seed_annotation_id)
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
    if not is_valid_relation_type(payload.type):
        raise HTTPException(status_code=422, detail=f"Relation type '{payload.type}' is not in the taxonomy")

    relation = Relation(
        document_id=document_id,
        source_id=payload.source_id,
        target_id=payload.target_id,
        type=payload.type,
        status=payload.status or "confirmed",
        reason=payload.reason,
        cos_score=payload.cos_score if payload.cos_score is not None else payload.score,
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
        if not is_valid_relation_type(payload.type):
            raise HTTPException(status_code=422, detail=f"Relation type '{payload.type}' is not in the taxonomy")
        relation.type = payload.type

    if payload.status is not None:
        relation.status = payload.status
        if payload.status == "rejected":
            ann_min = min(relation.source_id, relation.target_id)
            ann_max = max(relation.source_id, relation.target_id)
            exists = (
                db.query(RejectedPair)
                .filter(
                    RejectedPair.document_id == relation.document_id,
                    RejectedPair.ann_id_min == ann_min,
                    RejectedPair.ann_id_max == ann_max,
                )
                .first()
            )
            if not exists:
                db.add(RejectedPair(document_id=relation.document_id, ann_id_min=ann_min, ann_id_max=ann_max))

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
    """Delete a relation and remember as rejected pair to prevent re-suggesting."""
    relation = db.query(Relation).filter(Relation.id == relation_id).first()
    if not relation:
        raise HTTPException(status_code=404, detail="Relation not found")

    # Record rejected pair so relation suggester won't re-propose it
    ann_min = min(relation.source_id, relation.target_id)
    ann_max = max(relation.source_id, relation.target_id)
    exists = (
        db.query(RejectedPair)
        .filter(
            RejectedPair.document_id == relation.document_id,
            RejectedPair.ann_id_min == ann_min,
            RejectedPair.ann_id_max == ann_max,
        )
        .first()
    )
    if not exists:
        db.add(RejectedPair(document_id=relation.document_id, ann_id_min=ann_min, ann_id_max=ann_max))

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
            score=r.cos_score,
            cos_score=r.cos_score,
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
            from backend.app.routes.suggestions import infer_dynamic_relation
            seed_ann = db.query(Annotation).filter(Annotation.id == sug.seed_annotation_id).first()
            seed_label = seed_ann.label if seed_ann else None
            _, _, dynamic_type = infer_dynamic_relation(
                seed_label, sug.label, sug.seed_annotation_id, sug.id
            )
            ghost_edge = RelationResponse(
                id=-(sug.id),
                document_id=document_id,
                source_id=sug.id,
                target_id=sug.seed_annotation_id,
                type=dynamic_type,
                status="suggested",
                reason=str(round(sug.score, 4)),
                version=1,
                score=round(sug.score, 4),
            )
            edges.append(ghost_edge)

    # Phase D: Implied relation inference for transitive types (causes, precedes)
    # ponytail: 2-hop transitive closure; BFS if multi-hop arbitrary closure needed
    transitive_types = {"causes", "precedes"}
    existing_pairs = {(r.source_id, r.target_id) for r in relations}
    existing_pairs.update({(r.target_id, r.source_id) for r in relations})

    for t in transitive_types:
        out_edges = defaultdict(list)
        for r in relations:
            if r.type == t and (r.status or "confirmed") == "confirmed":
                out_edges[r.source_id].append(r.target_id)

        for a_id, b_list in out_edges.items():
            for b_id in b_list:
                for c_id in out_edges.get(b_id, []):
                    if a_id != c_id and (a_id, c_id) not in existing_pairs:
                        existing_pairs.add((a_id, c_id))
                        edges.append(
                            RelationResponse(
                                id=-(500000 + len(edges)),
                                document_id=document_id,
                                source_id=a_id,
                                target_id=c_id,
                                type=t,
                                status="implied",
                                reason=f"Transitive inference: ({a_id}) -> ({b_id}) -> ({c_id})",
                                version=1,
                            )
                        )

    return GraphResponse(
        document_id=document_id,
        annotations=nodes,
        relations=edges,
    )


@router.get("/documents/{document_id}/paths", response_model=PathsResponse)
def get_document_paths(
    document_id: int,
    from_id: int = Query(..., alias="from", description="Source annotation ID"),
    to_id: int = Query(..., alias="to", description="Target annotation ID"),
    max_depth: int = Query(default=4, ge=1, le=10, description="Maximum path length hops"),
    db: Session = Depends(get_db),
) -> PathsResponse:
    """Find reasoning paths/chains between two annotations via BFS traversal (Phase C)."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # ponytail: stdlib collections.deque BFS for shortest and diverse paths
    relations = (
        db.query(Relation)
        .filter(Relation.document_id == document_id, Relation.status.in_(["confirmed", "suggested"]))
        .all()
    )

    adj = defaultdict(list)
    for r in relations:
        adj[r.source_id].append((r.target_id, r.type))

    paths_found: List[PathItem] = []
    queue = deque([(from_id, [from_id], [])])

    while queue and len(paths_found) < 10:
        curr, node_path, edge_path = queue.popleft()
        if curr == to_id and edge_path:
            trace_parts = [f"[{node_path[0]}]"]
            for edge in edge_path:
                trace_parts.append(f"--[{edge.type}]--> [{edge.target_id}]")
            trace_str = " ".join(trace_parts)

            paths_found.append(
                PathItem(
                    nodes=node_path,
                    edges=edge_path,
                    length=len(edge_path),
                    trace=trace_str,
                )
            )
            continue

        if len(edge_path) >= max_depth:
            continue

        for next_id, edge_type in adj.get(curr, []):
            if next_id not in node_path:
                new_edge = PathEdge(source_id=curr, target_id=next_id, type=edge_type)
                queue.append((next_id, node_path + [next_id], edge_path + [new_edge]))

    return PathsResponse(
        document_id=document_id,
        from_id=from_id,
        to_id=to_id,
        paths=paths_found,
    )
