"""Relation CRUD and Graph view endpoints with taxonomy and cycle validation."""

from collections import deque, defaultdict
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from backend.app.db import get_db
from backend.app.models import (
    Document,
    Annotation,
    Relation,
    Suggestion,
    RejectedPair,
    ExtractionRun,
    Proposition,
    Concept,
    GraphEdge,
    EdgeEvidence,
    LegacyEdgeReview,
)
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
    PropositionResponse,
    ConceptResponse,
    GraphEdgeResponse,
    EdgeEvidenceResponse,
    ExtractionRunResponse,
    GraphValidationResponse,
    LegacyEdgeReviewRequest,
    LegacyEdgeReviewResponse,
    EdgeMappingReportResponse,
)
from backend.app.services.clean import snap_to_word_boundaries
from backend.app.services.graph_versioning import (
    validate_extraction_run,
    activate_extraction_run,
    rollback_extraction_run,
    record_legacy_edge_review,
    generate_edge_mapping_report,
)

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

    # Sync with unified graph schema (GraphRelation and RelationEvidence)
    try:
        from backend.app.models import Mention, GraphRelation, RelationEvidence, Sentence
        m_src = db.query(Mention).filter(Mention.id == payload.source_id).first()
        m_tgt = db.query(Mention).filter(Mention.id == payload.target_id).first()
        if m_src and m_tgt and m_src.node_id != m_tgt.node_id:
            existing_g = (
                db.query(GraphRelation)
                .filter(
                    GraphRelation.document_id == document_id,
                    GraphRelation.source_node_id == m_src.node_id,
                    GraphRelation.target_node_id == m_tgt.node_id,
                    GraphRelation.relation_type == payload.type,
                )
                .first()
            )
            if not existing_g:
                g_rel = GraphRelation(
                    document_id=document_id,
                    source_node_id=m_src.node_id,
                    target_node_id=m_tgt.node_id,
                    relation_type=payload.type,
                    confidence=float(relation.cos_score) if relation.cos_score is not None else 1.0,
                    status=relation.status,
                    is_legacy=payload.type in ("relates_to", "similar_to"),
                    reason=relation.reason,
                    version=relation.version,
                )
                db.add(g_rel)
                db.flush()
                sent = (
                    db.query(Sentence)
                    .filter(
                        Sentence.document_id == document_id,
                        Sentence.start <= source_ann.start,
                        Sentence.end >= source_ann.start,
                    )
                    .first()
                )
                evidence = RelationEvidence(
                    relation_id=g_rel.id,
                    document_id=document_id,
                    sentence_id=sent.id if sent else None,
                    verbatim_quote=source_ann.quote,
                    start=source_ann.start,
                    end=source_ann.end,
                )
                db.add(evidence)
                db.commit()
    except Exception:
        pass

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


def _build_legacy_graph_response(doc: Document, db: Session) -> GraphResponse:
    """Build legacy V1 graph view with annotations and relations."""
    annotations = db.query(Annotation).filter(Annotation.document_id == doc.id).all()
    relations = db.query(Relation).filter(Relation.document_id == doc.id).all()

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
            Suggestion.document_id == doc.id,
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
                document_id=doc.id,
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
                                document_id=doc.id,
                                source_id=a_id,
                                target_id=c_id,
                                type=t,
                                status="implied",
                                reason=f"Transitive inference: ({a_id}) -> ({b_id}) -> ({c_id})",
                                version=1,
                            )
                        )

    return GraphResponse(
        document_id=doc.id,
        annotations=nodes,
        relations=edges,
        graph_version=1,
        run_id=None,
        is_active=False,
    )


def _build_v2_graph_response(
    doc: Document,
    run: ExtractionRun,
    db: Session,
    min_confidence: Optional[float] = None,
    relation_type: Optional[str] = None,
    include_review: bool = False,
) -> GraphResponse:
    """Build Epistemic Knowledge Graph V2 response."""
    props = db.query(Proposition).filter(Proposition.run_id == run.id).all()
    concepts = db.query(Concept).filter(Concept.run_id == run.id).all()

    edges_query = db.query(GraphEdge).filter(GraphEdge.run_id == run.id)
    if min_confidence is not None:
        edges_query = edges_query.filter(GraphEdge.confidence >= min_confidence)
    if relation_type:
        edges_query = edges_query.filter(GraphEdge.relation_type == relation_type)
    if not include_review:
        edges_query = edges_query.filter(GraphEdge.review_status.in_(["accepted", "auto_candidate"]))

    raw_edges = edges_query.all()

    prop_responses: List[PropositionResponse] = [
        PropositionResponse(
            id=p.id,
            document_id=p.document_id,
            run_id=p.run_id,
            canonical_statement=p.canonical_statement,
            statement_type=p.statement_type,
            summary=p.summary,
            confidence=float(p.confidence),
            review_status=p.review_status,
            provenance_highlight_ids=[h.id for h in p.highlights],
        )
        for p in props
    ]

    concept_responses: List[ConceptResponse] = [
        ConceptResponse(
            id=c.id,
            document_id=c.document_id,
            run_id=c.run_id,
            name=c.name,
            canonical_name=c.canonical_name,
            category=c.category,
            description=c.description,
        )
        for c in concepts
    ]

    edge_responses: List[GraphEdgeResponse] = [
        GraphEdgeResponse(
            id=e.id,
            run_id=e.run_id,
            source_kind=e.source_kind,
            source_id=e.source_id,
            target_kind=e.target_kind,
            target_id=e.target_id,
            relation_type=e.relation_type,
            direction=e.direction,
            confidence=float(e.confidence),
            rationale=e.rationale,
            review_status=e.review_status,
            extraction_method=e.extraction_method,
            evidence=[
                EdgeEvidenceResponse(
                    id=ev.id,
                    edge_id=ev.edge_id,
                    highlight_id=ev.highlight_id,
                    evidence_quote=ev.evidence_quote,
                )
                for ev in e.evidence_items
            ],
        )
        for e in raw_edges
    ]

    # Map propositions to AnnotationResponse for backwards compatibility
    compat_annotations: List[AnnotationResponse] = [
        AnnotationResponse(
            id=p.id,
            document_id=doc.id,
            start=0,
            end=len(p.canonical_statement),
            quote=p.canonical_statement,
            label=p.statement_type,
            note=p.summary or f"Proposition P{p.id}",
            x=0.0,
            y=0.0,
            version=1,
            created_at=p.created_at,
            status="confirmed",
        )
        for p in props
    ]

    compat_relations: List[RelationResponse] = [
        RelationResponse(
            id=e.id,
            document_id=doc.id,
            source_id=e.source_id,
            target_id=e.target_id,
            type=e.relation_type,
            status=e.review_status,
            reason=e.rationale,
            version=1,
            score=float(e.confidence),
            cos_score=float(e.confidence),
        )
        for e in raw_edges
    ]

    return GraphResponse(
        document_id=doc.id,
        annotations=compat_annotations,
        relations=compat_relations,
        graph_version=2,
        run_id=run.id,
        is_active=run.is_active,
        propositions=prop_responses,
        concepts=concept_responses,
        edges=edge_responses,
    )


@router.get("/documents/{document_id}/graph", response_model=GraphResponse)
def get_document_graph(
    document_id: int,
    graph_version: Optional[int] = Query(None, description="Graph version: 1 for legacy, 2 for epistemic V2"),
    run_id: Optional[int] = Query(None, description="Specific extraction run ID to query"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum edge confidence filter"),
    relation_type: Optional[str] = Query(None, description="Filter edges by relation type"),
    include_review: bool = Query(False, description="Whether to include needs_review edges in V2"),
    db: Session = Depends(get_db),
) -> GraphResponse:
    """Retrieve graph view supporting both legacy V1 and epistemic V2 with safe version resolution."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 1. Explicit V1 request
    if graph_version == 1:
        return _build_legacy_graph_response(doc, db)

    # 2. Specific extraction run request
    if run_id is not None:
        run = (
            db.query(ExtractionRun)
            .filter(ExtractionRun.id == run_id, ExtractionRun.document_id == document_id)
            .first()
        )
        if not run:
            raise HTTPException(status_code=404, detail=f"Extraction run {run_id} not found for document {document_id}")
        return _build_v2_graph_response(doc, run, db, min_confidence, relation_type, include_review)

    # 3. Resolve active run
    active_run = (
        db.query(ExtractionRun)
        .filter(ExtractionRun.document_id == document_id, ExtractionRun.is_active == True)
        .first()
    )
    if active_run:
        return _build_v2_graph_response(doc, active_run, db, min_confidence, relation_type, include_review)

    # 4. If no active run: if V2 explicitly asked, check for any latest run
    if graph_version == 2:
        latest_run = (
            db.query(ExtractionRun)
            .filter(ExtractionRun.document_id == document_id)
            .order_by(ExtractionRun.created_at.desc())
            .first()
        )
        if latest_run:
            return _build_v2_graph_response(doc, latest_run, db, min_confidence, relation_type, include_review)
        return GraphResponse(
            document_id=doc.id,
            annotations=[],
            relations=[],
            graph_version=2,
            run_id=None,
            is_active=False,
            propositions=[],
            concepts=[],
            edges=[],
        )

    # 5. Default before cutover: return legacy V1 graph
    return _build_legacy_graph_response(doc, db)


# --- Epistemic Knowledge Graph V2 Admin Endpoints ---


@router.get("/documents/{document_id}/graph/runs", response_model=List[ExtractionRunResponse])
def list_extraction_runs(
    document_id: int,
    db: Session = Depends(get_db),
) -> List[ExtractionRunResponse]:
    """List all extraction runs for a document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    runs = (
        db.query(ExtractionRun)
        .filter(ExtractionRun.document_id == document_id)
        .order_by(ExtractionRun.created_at.desc())
        .all()
    )
    return [
        ExtractionRunResponse(
            id=r.id,
            document_id=r.document_id,
            graph_version=r.graph_version,
            model_name=r.model_name,
            prompt_version=r.prompt_version,
            status=r.status,
            is_active=r.is_active,
            created_at=r.created_at,
        )
        for r in runs
    ]


@router.get("/documents/{document_id}/graph/runs/{run_id}/validate", response_model=GraphValidationResponse)
def validate_run_endpoint(
    document_id: int,
    run_id: int,
    max_out_degree: int = Query(5, ge=1, le=20, description="Maximum permitted outgoing edges per proposition"),
    db: Session = Depends(get_db),
) -> GraphValidationResponse:
    """Run automated safety, evidence, and epistemic constraint checks on an extraction run."""
    run = (
        db.query(ExtractionRun)
        .filter(ExtractionRun.id == run_id, ExtractionRun.document_id == document_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail=f"Extraction run {run_id} not found for document {document_id}")
    is_valid, issues, metrics = validate_extraction_run(run_id, db, max_out_degree=max_out_degree)
    return GraphValidationResponse(is_valid=is_valid, issues=issues, metrics=metrics)


@router.post("/documents/{document_id}/graph/runs/{run_id}/activate", response_model=ExtractionRunResponse)
def activate_run_endpoint(
    document_id: int,
    run_id: int,
    activated_by: str = Query("admin", description="Identity activating the run"),
    reason: Optional[str] = Query(None, description="Reason for activation"),
    force: bool = Query(False, description="Bypass safety validation"),
    db: Session = Depends(get_db),
) -> ExtractionRunResponse:
    """Transactionally activate an extraction run for production serving."""
    run = (
        db.query(ExtractionRun)
        .filter(ExtractionRun.id == run_id, ExtractionRun.document_id == document_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail=f"Extraction run {run_id} not found for document {document_id}")
    try:
        activated = activate_extraction_run(
            run_id=run_id,
            activated_by=activated_by,
            reason=reason,
            db=db,
            validate=(not force),
        )
        return ExtractionRunResponse(
            id=activated.id,
            document_id=activated.document_id,
            graph_version=activated.graph_version,
            model_name=activated.model_name,
            prompt_version=activated.prompt_version,
            status=activated.status,
            is_active=activated.is_active,
            created_at=activated.created_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/documents/{document_id}/graph/rollback", response_model=Optional[ExtractionRunResponse])
def rollback_run_endpoint(
    document_id: int,
    rolled_back_by: str = Query("admin", description="Identity triggering rollback"),
    reason: Optional[str] = Query(None, description="Reason for rollback"),
    db: Session = Depends(get_db),
) -> Optional[ExtractionRunResponse]:
    """Transactionally rollback an active run to the previously active run."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    restored = rollback_extraction_run(
        document_id=document_id,
        rolled_back_by=rolled_back_by,
        reason=reason,
        db=db,
    )
    if restored:
        return ExtractionRunResponse(
            id=restored.id,
            document_id=restored.document_id,
            graph_version=restored.graph_version,
            model_name=restored.model_name,
            prompt_version=restored.prompt_version,
            status=restored.status,
            is_active=restored.is_active,
            created_at=restored.created_at,
        )
    return None


@router.get("/documents/{document_id}/graph/comparison", response_model=EdgeMappingReportResponse)
def get_graph_comparison(
    document_id: int,
    run_id: int = Query(..., description="V2 Extraction run ID to compare against legacy V1"),
    db: Session = Depends(get_db),
) -> EdgeMappingReportResponse:
    """Generate side-by-side comparison report between legacy V1 relations and V2 extraction."""
    run = (
        db.query(ExtractionRun)
        .filter(ExtractionRun.id == run_id, ExtractionRun.document_id == document_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail=f"Extraction run {run_id} not found for document {document_id}")
    report = generate_edge_mapping_report(document_id=document_id, run_id=run_id, db=db)
    return EdgeMappingReportResponse(**report)


@router.post("/documents/{document_id}/graph/legacy-review", response_model=LegacyEdgeReviewResponse)
def review_legacy_edge_endpoint(
    document_id: int,
    payload: LegacyEdgeReviewRequest,
    db: Session = Depends(get_db),
) -> LegacyEdgeReviewResponse:
    """Submit a reviewer evaluation for a legacy V1 relation."""
    run = (
        db.query(ExtractionRun)
        .filter(ExtractionRun.id == payload.run_id, ExtractionRun.document_id == document_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail=f"Extraction run {payload.run_id} not found for document {document_id}")
    rel = (
        db.query(Relation)
        .filter(Relation.id == payload.legacy_relation_id, Relation.document_id == document_id)
        .first()
    )
    if not rel:
        raise HTTPException(status_code=404, detail=f"Legacy relation {payload.legacy_relation_id} not found in document")
    try:
        record = record_legacy_edge_review(
            run_id=payload.run_id,
            legacy_relation_id=payload.legacy_relation_id,
            classification=payload.classification,
            reviewer_reason=payload.reviewer_reason,
            mapped_edge_id=payload.mapped_edge_id,
            reviewed_by=payload.reviewed_by or "reviewer",
            db=db,
        )
        return LegacyEdgeReviewResponse(
            id=record.id,
            run_id=record.run_id,
            legacy_relation_id=record.legacy_relation_id,
            classification=record.classification,
            reviewer_reason=record.reviewer_reason,
            mapped_edge_id=record.mapped_edge_id,
            reviewed_by=record.reviewed_by,
            reviewed_at=record.reviewed_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


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
