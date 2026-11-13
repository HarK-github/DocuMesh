"""Epistemic Knowledge Graph V2 versioning, validation, transactional cutover, and rollback service."""

from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models import (
    Document,
    Annotation,
    Relation,
    ExtractionRun,
    Proposition,
    Concept,
    GraphEdge,
    EdgeEvidence,
    ExtractionRunActivationHistory,
    LegacyEdgeReview,
)

PROHIBITED_RELATIONS = {
    "precedes",
    "follows",
    "relates_to",
    "similar_to",
    "near",
    "mentions",
    "same_page",
    "co_occurs_with",
}

PERMITTED_RELATIONS = {
    "supports",
    "contradicts",
    "defines",
    "causes",
    "enables",
    "solves",
    "elaborates",
    "part_of",
    "example_of",
    "same_as",
}

VALID_CLASSIFICATIONS = {
    "retained",
    "merged",
    "demoted_to_review",
    "rejected",
    "replaced_by_new_edge",
}


def validate_extraction_run(
    run_id: int,
    db: Session,
    max_out_degree: int = 5,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Validate safety, epistemic constraints, and grounding before activating an extraction run.

    Checks:
    1. Run exists.
    2. Every V2 edge has at least one evidence highlight.
    3. Every evidence highlight ID exists and belongs to the same document.
    4. Every evidence quote matches or is a substring of the stored highlight quote.
    5. No prohibited relation types are present.
    6. No self-loops exist.
    7. Confidence is within 0.0-1.0.
    8. No proposition exceeds the configured maximum outgoing-edge limit.
    """
    run = db.query(ExtractionRun).filter(ExtractionRun.id == run_id).first()
    if not run:
        return False, [f"Extraction run {run_id} not found"], {}

    issues: List[str] = []
    edges = db.query(GraphEdge).filter(GraphEdge.run_id == run_id).all()
    propositions = db.query(Proposition).filter(Proposition.run_id == run_id).all()
    concepts = db.query(Concept).filter(Concept.run_id == run_id).all()

    # Pre-fetch valid highlights for this document
    doc_highlights = {
        h.id: h for h in db.query(Annotation).filter(Annotation.document_id == run.document_id).all()
    }

    # Map propositions for degree checks
    prop_out_degree: Dict[int, int] = {p.id: 0 for p in propositions}
    valid_prop_ids = set(prop_out_degree.keys())
    valid_concept_ids = {c.id for c in concepts}

    for edge in edges:
        # Check 1: Relation vocabulary
        rel_type = (edge.relation_type or "").strip().lower()
        if rel_type in PROHIBITED_RELATIONS:
            issues.append(
                f"Edge {edge.id} uses prohibited relation '{edge.relation_type}'. "
                f"Prohibited relations: {', '.join(sorted(PROHIBITED_RELATIONS))}"
            )
        elif rel_type not in PERMITTED_RELATIONS:
            issues.append(
                f"Edge {edge.id} uses unknown relation '{edge.relation_type}'. "
                f"Allowed relations: {', '.join(sorted(PERMITTED_RELATIONS))}"
            )

        # Check 2: Self-loops
        if edge.source_kind == edge.target_kind and edge.source_id == edge.target_id:
            issues.append(f"Edge {edge.id} is a self-loop: {edge.source_kind}:{edge.source_id}")

        # Check 3: Valid node references
        if edge.source_kind == "proposition" and edge.source_id not in valid_prop_ids:
            issues.append(f"Edge {edge.id} references non-existent source proposition {edge.source_id}")
        elif edge.source_kind == "concept" and edge.source_id not in valid_concept_ids:
            issues.append(f"Edge {edge.id} references non-existent source concept {edge.source_id}")

        if edge.target_kind == "proposition" and edge.target_id not in valid_prop_ids:
            issues.append(f"Edge {edge.id} references non-existent target proposition {edge.target_id}")
        elif edge.target_kind == "concept" and edge.target_id not in valid_concept_ids:
            issues.append(f"Edge {edge.id} references non-existent target concept {edge.target_id}")

        # Check 4: Confidence range
        conf = float(edge.confidence) if edge.confidence is not None else -1.0
        if not (0.0 <= conf <= 1.0):
            issues.append(f"Edge {edge.id} has invalid confidence {conf}; must be between 0.0 and 1.0")

        # Check 5: Evidence requirements
        evidence_items = edge.evidence_items
        if not evidence_items:
            issues.append(f"Edge {edge.id} has no evidence items. Every V2 edge must cite source highlights.")
        else:
            for ev in evidence_items:
                if ev.highlight_id not in doc_highlights:
                    issues.append(
                        f"Edge {edge.id} evidence references highlight {ev.highlight_id} "
                        f"which does not exist in document {run.document_id}"
                    )
                else:
                    hl = doc_highlights[ev.highlight_id]
                    ev_quote = " ".join(ev.evidence_quote.strip().lower().split())
                    hl_quote = " ".join(hl.quote.strip().lower().split())
                    if not (ev_quote in hl_quote or hl_quote in ev_quote):
                        issues.append(
                            f"Edge {edge.id} evidence quote '{ev.evidence_quote[:40]}...' "
                            f"does not match highlight {hl.id} text '{hl.quote[:40]}...'"
                        )

        # Track out-degree for propositions
        if edge.source_kind == "proposition" and edge.source_id in prop_out_degree:
            prop_out_degree[edge.source_id] += 1

    # Check 6: Maximum out-degree
    for prop_id, degree in prop_out_degree.items():
        if degree > max_out_degree:
            issues.append(
                f"Proposition {prop_id} exceeds maximum outgoing edges limit: {degree} > {max_out_degree}"
            )

    metrics = {
        "run_id": run_id,
        "document_id": run.document_id,
        "total_propositions": len(propositions),
        "total_concepts": len(concepts),
        "total_edges": len(edges),
        "max_out_degree_observed": max(prop_out_degree.values()) if prop_out_degree else 0,
        "issues_count": len(issues),
    }

    return (len(issues) == 0), issues, metrics


def activate_extraction_run(
    run_id: int,
    activated_by: str = "admin",
    reason: Optional[str] = None,
    db: Optional[Session] = None,
    validate: bool = True,
) -> ExtractionRun:
    """Transactionally activate an extraction run, demoting any previously active run and logging history.

    Reversible via rollback_extraction_run.
    """
    if db is None:
        raise ValueError("Database session is required")

    run = db.query(ExtractionRun).filter(ExtractionRun.id == run_id).first()
    if not run:
        raise ValueError(f"Extraction run {run_id} not found")

    if validate:
        is_valid, issues, _ = validate_extraction_run(run_id, db)
        if not is_valid:
            error_details = "\n - ".join(issues[:10])
            if len(issues) > 10:
                error_details += f"\n ... and {len(issues) - 10} more issues."
            raise ValueError(f"Safety validation failed for run {run_id}:\n - {error_details}")

    document_id = run.document_id

    try:
        # Find currently active run ID for history recording
        prev_run = (
            db.query(ExtractionRun)
            .filter(
                ExtractionRun.document_id == document_id,
                ExtractionRun.is_active == True,
                ExtractionRun.id != run_id,
            )
            .first()
        )
        prev_run_id = prev_run.id if prev_run else None

        # 1. Explicitly demote previous active runs and flush first to satisfy uq_active_run_per_doc
        db.query(ExtractionRun).filter(
            ExtractionRun.document_id == document_id,
            ExtractionRun.is_active == True,
            ExtractionRun.id != run_id,
        ).update({"is_active": False, "status": "archived"}, synchronize_session="fetch")
        db.flush()

        # 2. Activate target run
        run.is_active = True
        run.status = "active"
        db.flush()

        # 3. Record activation in audit table
        history = ExtractionRunActivationHistory(
            document_id=document_id,
            run_id=run.id,
            previous_run_id=prev_run_id,
            action="activate",
            activated_by=activated_by,
            reason=reason or f"Activated V{run.graph_version} extraction run {run.id}",
        )
        db.add(history)
        db.commit()
        db.refresh(run)
        return run
    except Exception:
        db.rollback()
        raise


def rollback_extraction_run(
    document_id: int,
    rolled_back_by: str = "admin",
    reason: Optional[str] = None,
    db: Optional[Session] = None,
) -> Optional[ExtractionRun]:
    """Transactionally rollback an active run to the previously active run."""
    if db is None:
        raise ValueError("Database session is required")

    current_active = (
        db.query(ExtractionRun)
        .filter(ExtractionRun.document_id == document_id, ExtractionRun.is_active == True)
        .first()
    )

    # Find the most recent activation history that had a previous_run_id
    last_activation = (
        db.query(ExtractionRunActivationHistory)
        .filter(
            ExtractionRunActivationHistory.document_id == document_id,
            ExtractionRunActivationHistory.action == "activate",
        )
        .order_by(ExtractionRunActivationHistory.activated_at.desc())
        .first()
    )

    prev_run_to_restore: Optional[ExtractionRun] = None
    if last_activation and last_activation.previous_run_id:
        prev_run_to_restore = (
            db.query(ExtractionRun)
            .filter(ExtractionRun.id == last_activation.previous_run_id)
            .first()
        )

    try:
        curr_id = current_active.id if current_active else None

        # 1. Demote any currently active run and flush first
        db.query(ExtractionRun).filter(
            ExtractionRun.document_id == document_id,
            ExtractionRun.is_active == True,
        ).update({"is_active": False, "status": "archived"}, synchronize_session="fetch")
        db.flush()

        # 2. Activate restored run if found
        if prev_run_to_restore:
            prev_run_to_restore.is_active = True
            prev_run_to_restore.status = "active"
            db.flush()

        # 3. Record rollback action in audit history
        history = ExtractionRunActivationHistory(
            document_id=document_id,
            run_id=prev_run_to_restore.id if prev_run_to_restore else (curr_id or 0),
            previous_run_id=curr_id,
            action="rollback",
            activated_by=rolled_back_by,
            reason=reason or f"Rolled back from run {curr_id} to previous run {prev_run_to_restore.id if prev_run_to_restore else 'legacy'}",
        )
        db.add(history)
        db.commit()

        if prev_run_to_restore:
            db.refresh(prev_run_to_restore)
        return prev_run_to_restore
    except Exception:
        db.rollback()
        raise


def record_legacy_edge_review(
    run_id: int,
    legacy_relation_id: int,
    classification: str,
    reviewer_reason: Optional[str] = None,
    mapped_edge_id: Optional[int] = None,
    reviewed_by: str = "reviewer",
    db: Optional[Session] = None,
) -> LegacyEdgeReview:
    """Record reviewer evaluation of how a legacy relation was handled in V2.

    Enforces mandatory reason for 'rejected' or 'demoted_to_review'.
    """
    if db is None:
        raise ValueError("Database session is required")

    classification = classification.strip().lower()
    if classification not in VALID_CLASSIFICATIONS:
        raise ValueError(
            f"Invalid classification '{classification}'. Allowed: {', '.join(sorted(VALID_CLASSIFICATIONS))}"
        )

    if classification in ("rejected", "demoted_to_review") and (not reviewer_reason or not reviewer_reason.strip()):
        raise ValueError(
            f"A reviewer reason is required when classifying a legacy relation as '{classification}'"
        )

    # Check or upsert
    existing = (
        db.query(LegacyEdgeReview)
        .filter(
            LegacyEdgeReview.run_id == run_id,
            LegacyEdgeReview.legacy_relation_id == legacy_relation_id,
        )
        .first()
    )

    if existing:
        existing.classification = classification
        existing.reviewer_reason = reviewer_reason
        existing.mapped_edge_id = mapped_edge_id
        existing.reviewed_by = reviewed_by
        record = existing
    else:
        record = LegacyEdgeReview(
            run_id=run_id,
            legacy_relation_id=legacy_relation_id,
            classification=classification,
            reviewer_reason=reviewer_reason,
            mapped_edge_id=mapped_edge_id,
            reviewed_by=reviewed_by,
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return record


def generate_edge_mapping_report(
    document_id: int,
    run_id: int,
    db: Session,
) -> Dict[str, Any]:
    """Generate complete edge mapping comparison report between legacy V1 and V2."""
    legacy_relations = db.query(Relation).filter(Relation.document_id == document_id).all()
    reviews = db.query(LegacyEdgeReview).filter(LegacyEdgeReview.run_id == run_id).all()
    review_by_legacy_id = {r.legacy_relation_id: r for r in reviews}

    classification_counts: Dict[str, int] = {c: 0 for c in VALID_CLASSIFICATIONS}
    items = []

    for rel in legacy_relations:
        rev = review_by_legacy_id.get(rel.id)
        cls = rev.classification if rev else "unreviewed"
        if cls in classification_counts:
            classification_counts[cls] += 1

        items.append({
            "legacy_relation_id": rel.id,
            "source_id": rel.source_id,
            "target_id": rel.target_id,
            "legacy_type": rel.type,
            "legacy_reason": rel.reason,
            "classification": cls,
            "reviewer_reason": rev.reviewer_reason if rev else None,
            "mapped_edge_id": rev.mapped_edge_id if rev else None,
            "reviewed_by": rev.reviewed_by if rev else None,
        })

    total_legacy = len(legacy_relations)
    reviewed_count = len(reviews)
    unreviewed_count = total_legacy - reviewed_count

    return {
        "document_id": document_id,
        "run_id": run_id,
        "total_legacy_edges": total_legacy,
        "reviewed_edges_count": reviewed_count,
        "unreviewed_edges_count": unreviewed_count,
        "review_coverage_pct": round((reviewed_count / total_legacy * 100.0), 1) if total_legacy > 0 else 100.0,
        "classification_breakdown": classification_counts,
        "items": items,
    }
