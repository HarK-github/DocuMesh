"""API router for knowledge graph nodes, aliases, entity resolution, and merges."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.db import get_db
from backend.app.models import (
    Node,
    NodeAlias,
    Mention,
    GraphRelation,
    RelationEvidence,
    EntityMergePending,
    Chunk,
)
from backend.app.services.entity_resolution import EntityResolutionService

router = APIRouter(tags=["Knowledge Graph Entities"])


class MergeRequest(BaseModel):
    surviving_node_id: int = Field(..., description="ID of node that will survive and retain identity")
    absorbed_node_id: int = Field(..., description="ID of node being absorbed/tombstoned")
    reason: str = Field(..., description="Justification or evidence for the merge")


class RevertMergeResponse(BaseModel):
    status: str
    log_id: int


@router.get("/nodes", response_model=List[Dict[str, Any]])
def list_nodes(
    q: Optional[str] = Query(None, description="Search query by name or alias"),
    node_type: Optional[str] = Query(None, description="Filter by node_type"),
    is_global: Optional[bool] = Query(None, description="Filter by global concept vs local claim"),
    document_id: Optional[int] = Query(None, description="Filter by document_id"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List canonical knowledge graph nodes, excluding tombstoned/absorbed nodes."""
    query = db.query(Node).filter(Node.merged_into_id.is_(None))

    if node_type:
        query = query.filter(Node.node_type == node_type)
    if is_global is not None:
        query = query.filter(Node.is_global.is_(is_global))
    if document_id is not None:
        query = query.filter(or_(Node.document_id == document_id, Node.is_global.is_(True)))

    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        query = query.outerjoin(NodeAlias).filter(
            or_(
                Node.normalized_name.like(term),
                Node.name.ilike(term),
                NodeAlias.normalized_alias.like(term),
            )
        ).distinct()

    nodes = query.order_by(Node.id.desc()).offset(offset).limit(limit).all()

    results = []
    for n in nodes:
        alias_names = [a.alias for a in n.aliases]
        mention_count = db.query(Mention).filter(Mention.node_id == n.id).count()
        results.append({
            "id": n.id,
            "name": n.name,
            "normalized_name": n.normalized_name,
            "node_type": n.node_type,
            "description": n.description,
            "is_global": n.is_global,
            "document_id": n.document_id,
            "legacy_label": n.legacy_label,
            "aliases": alias_names,
            "mention_count": mention_count,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        })
    return results


@router.get("/nodes/merge-pending", response_model=List[Dict[str, Any]])
def list_pending_merges(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List ambiguous candidate entity pairs awaiting review."""
    pending = (
        db.query(EntityMergePending)
        .filter(EntityMergePending.status == "pending")
        .order_by(EntityMergePending.similarity.desc())
        .limit(100)
        .all()
    )
    results = []
    for p in pending:
        node_a = db.query(Node).filter(Node.id == p.candidate_a_id).first()
        node_b = db.query(Node).filter(Node.id == p.candidate_b_id).first()
        results.append({
            "id": p.id,
            "candidate_a": {
                "id": node_a.id if node_a else p.candidate_a_id,
                "name": node_a.name if node_a else "Unknown",
                "node_type": node_a.node_type if node_a else "Unknown",
            },
            "candidate_b": {
                "id": node_b.id if node_b else p.candidate_b_id,
                "name": node_b.name if node_b else "Unknown",
                "node_type": node_b.node_type if node_b else "Unknown",
            },
            "similarity": p.similarity,
            "verdict": p.llm_adjudication_verdict,
            "reason": p.llm_reason,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return results


@router.get("/nodes/{node_id}", response_model=Dict[str, Any])
def get_node(node_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve node details, aliases, mentions, and attached relationships."""
    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    aliases = [a.alias for a in node.aliases]
    mentions = (
        db.query(Mention)
        .filter(Mention.node_id == node_id)
        .order_by(Mention.created_at.desc())
        .limit(20)
        .all()
    )

    out_relations = (
        db.query(GraphRelation)
        .filter(GraphRelation.source_node_id == node_id)
        .all()
    )
    in_relations = (
        db.query(GraphRelation)
        .filter(GraphRelation.target_node_id == node_id)
        .all()
    )

    return {
        "id": node.id,
        "name": node.name,
        "normalized_name": node.normalized_name,
        "node_type": node.node_type,
        "description": node.description,
        "is_global": node.is_global,
        "document_id": node.document_id,
        "merged_into_id": node.merged_into_id,
        "aliases": aliases,
        "mentions": [
            {
                "id": m.id,
                "document_id": m.document_id,
                "quote": m.quote,
                "start": m.start,
                "end": m.end,
                "page": m.page,
            }
            for m in mentions
        ],
        "outgoing_relations": [
            {
                "id": r.id,
                "target_node_id": r.target_node_id,
                "relation_type": r.relation_type,
                "confidence": r.confidence,
                "is_legacy": r.is_legacy,
            }
            for r in out_relations
        ],
        "incoming_relations": [
            {
                "id": r.id,
                "source_node_id": r.source_node_id,
                "relation_type": r.relation_type,
                "confidence": r.confidence,
                "is_legacy": r.is_legacy,
            }
            for r in in_relations
        ],
    }


@router.post("/nodes/merge", response_model=Dict[str, Any])
def merge_nodes(payload: MergeRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Manually merge two nodes, transferring mentions and relations into the surviving node."""
    resolver = EntityResolutionService(db)
    try:
        log = resolver.merge_nodes(
            surviving_node_id=payload.surviving_node_id,
            absorbed_node_id=payload.absorbed_node_id,
            reason=payload.reason,
            adjudicated_by="manual",
            confidence=1.0,
        )
        return {
            "status": "merged",
            "log_id": log.id,
            "surviving_node_id": log.surviving_node_id,
            "absorbed_node_id": log.absorbed_node_id,
            "absorbed_name": log.absorbed_name,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/nodes/revert-merge/{log_id}", response_model=RevertMergeResponse)
def revert_merge(log_id: int, db: Session = Depends(get_db)) -> RevertMergeResponse:
    """Revert an entity merge by its audit log ID."""
    resolver = EntityResolutionService(db)
    success = resolver.revert_merge(log_id)
    if not success:
        raise HTTPException(status_code=404, detail="Merge log not found or already reverted")
    return RevertMergeResponse(status="reverted", log_id=log_id)


@router.get("/documents/{document_id}/chunks", response_model=List[Dict[str, Any]])
def get_document_chunks(document_id: int, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Retrieve chunk hierarchy with sentence indices for a document."""
    chunks = (
        db.query(Chunk)
        .filter(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index)
        .all()
    )
    return [
        {
            "id": c.id,
            "document_id": c.document_id,
            "chunk_index": c.chunk_index,
            "start": c.start,
            "end": c.end,
            "first_sentence_idx": c.first_sentence_idx,
            "last_sentence_idx": c.last_sentence_idx,
            "token_count": c.token_count,
            "has_embedding": c.embedding is not None,
        }
        for c in chunks
    ]


@router.get("/documents/{document_id}/graph/evidence", response_model=List[Dict[str, Any]])
def get_relation_evidence(
    document_id: int,
    relation_id: int = Query(..., description="ID of graph_relation to fetch evidence for"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Fetch exact text spans and sentence references supporting a relationship."""
    evidence = (
        db.query(RelationEvidence)
        .filter(
            RelationEvidence.document_id == document_id,
            RelationEvidence.relation_id == relation_id,
        )
        .all()
    )
    return [
        {
            "id": ev.id,
            "relation_id": ev.relation_id,
            "sentence_id": ev.sentence_id,
            "verbatim_quote": ev.verbatim_quote,
            "start": ev.start,
            "end": ev.end,
        }
        for ev in evidence
    ]
