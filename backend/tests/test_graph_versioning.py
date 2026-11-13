"""Tests for Epistemic Knowledge Graph V2 versioning, validation, activation, and rollback."""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
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
from backend.app.services.graph_versioning import (
    validate_extraction_run,
    activate_extraction_run,
    rollback_extraction_run,
    record_legacy_edge_review,
    generate_edge_mapping_report,
)


@pytest.fixture
def graph_v2_setup(db_session):
    """Seed test document with V1 annotations and a complete V2 extraction run."""
    # 1. Create Document
    import uuid
    doc = Document(filename="turing_test.pdf", file_hash=f"hash_v2_test_{uuid.uuid4().hex[:12]}", status="ready")
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    # 2. Create V1 Highlights (Annotations)
    h1 = Annotation(document_id=doc.id, start=10, end=50, quote="Can machines think? The question is ambiguous.", label="Problem")
    h2 = Annotation(document_id=doc.id, start=60, end=150, quote="The imitation game replaces the original question.", label="Solution")
    h3 = Annotation(document_id=doc.id, start=160, end=250, quote="Digital computers can simulate any discrete state machine.", label="Claim")
    db_session.add_all([h1, h2, h3])
    db_session.commit()
    db_session.refresh(h1)
    db_session.refresh(h2)
    db_session.refresh(h3)

    # 3. Create Legacy V1 Relation
    rel1 = Relation(document_id=doc.id, source_id=h2.id, target_id=h1.id, type="solves", status="confirmed", cos_score=0.88, reason="Legacy inferred")
    rel2 = Relation(document_id=doc.id, source_id=h1.id, target_id=h3.id, type="similar_to", status="confirmed", cos_score=0.45, reason="Legacy generic proximity")
    db_session.add_all([rel1, rel2])
    db_session.commit()
    db_session.refresh(rel1)
    db_session.refresh(rel2)

    # 4. Create V2 Extraction Run (Draft / Inactive)
    run1 = ExtractionRun(
        document_id=doc.id,
        graph_version=2,
        model_name="meta-llama/Llama-3.1-8B-Instruct",
        prompt_version="v2.1",
        status="ready_for_review",
        is_active=False,
    )
    db_session.add(run1)
    db_session.commit()
    db_session.refresh(run1)

    # 5. Create V2 Propositions
    p1 = Proposition(
        document_id=doc.id,
        run_id=run1.id,
        canonical_statement="The question 'Can machines think?' is linguistically ambiguous.",
        statement_type="Problem",
        confidence=0.95,
        review_status="accepted",
    )
    p2 = Proposition(
        document_id=doc.id,
        run_id=run1.id,
        canonical_statement="The imitation game operationalizes machine intelligence via behavioral indistinguishability.",
        statement_type="Solution",
        confidence=0.98,
        review_status="accepted",
    )
    p3 = Proposition(
        document_id=doc.id,
        run_id=run1.id,
        canonical_statement="Digital computers can simulate any discrete state machine.",
        statement_type="Claim",
        confidence=0.96,
        review_status="accepted",
    )
    db_session.add_all([p1, p2, p3])
    db_session.commit()
    db_session.refresh(p1)
    db_session.refresh(p2)
    db_session.refresh(p3)

    # Link proposition provenance
    p1.highlights.append(h1)
    p2.highlights.append(h2)
    p3.highlights.append(h3)
    db_session.commit()

    # 6. Create V2 Concepts
    c1 = Concept(
        document_id=doc.id,
        run_id=run1.id,
        name="Imitation Game",
        canonical_name="imitation_game",
        category="Protocol",
        description="Behavioral test for machine intelligence.",
    )
    db_session.add(c1)
    db_session.commit()
    db_session.refresh(c1)

    # 7. Create V2 Graph Edges
    edge1 = GraphEdge(
        document_id=doc.id,
        run_id=run1.id,
        source_kind="proposition",
        source_id=p2.id,
        target_kind="proposition",
        target_id=p1.id,
        relation_type="solves",
        confidence=0.96,
        rationale="Imitation game replaces the ambiguous question.",
        review_status="accepted",
        extraction_method="llm",
    )
    edge2 = GraphEdge(
        document_id=doc.id,
        run_id=run1.id,
        source_kind="proposition",
        source_id=p2.id,
        target_kind="concept",
        target_id=c1.id,
        relation_type="defines",
        confidence=0.92,
        rationale="P2 defines the rules of the imitation game.",
        review_status="accepted",
        extraction_method="llm",
    )
    edge3_review = GraphEdge(
        document_id=doc.id,
        run_id=run1.id,
        source_kind="proposition",
        source_id=p3.id,
        target_kind="proposition",
        target_id=p2.id,
        relation_type="supports",
        confidence=0.65,
        rationale="Universal simulation provides indirect support for playing the game.",
        review_status="needs_review",
        extraction_method="llm",
    )
    db_session.add_all([edge1, edge2, edge3_review])
    db_session.commit()
    db_session.refresh(edge1)
    db_session.refresh(edge2)
    db_session.refresh(edge3_review)

    # 8. Create V2 Edge Evidence
    ev1 = EdgeEvidence(
        edge_id=edge1.id,
        highlight_id=h2.id,
        evidence_quote="The imitation game replaces the original question.",
    )
    ev2 = EdgeEvidence(
        edge_id=edge2.id,
        highlight_id=h2.id,
        evidence_quote="The imitation game replaces the original question.",
    )
    ev3 = EdgeEvidence(
        edge_id=edge3_review.id,
        highlight_id=h3.id,
        evidence_quote="Digital computers can simulate any discrete state machine.",
    )
    db_session.add_all([ev1, ev2, ev3])
    db_session.commit()

    return {
        "doc": doc,
        "run1": run1,
        "highlights": [h1, h2, h3],
        "relations": [rel1, rel2],
        "propositions": [p1, p2, p3],
        "concepts": [c1],
        "edges": [edge1, edge2, edge3_review],
    }


def test_validation_success_and_safety_checks(db_session, graph_v2_setup):
    """Verify validation passes on compliant V2 extraction run."""
    run1 = graph_v2_setup["run1"]
    is_valid, issues, metrics = validate_extraction_run(run1.id, db_session)
    assert is_valid is True
    assert issues == []
    assert metrics["total_propositions"] == 3
    assert metrics["total_concepts"] == 1
    assert metrics["total_edges"] == 3


def test_validation_fails_on_prohibited_relation(db_session, graph_v2_setup):
    """Verify validation blocks prohibited relations like 'precedes' or 'similar_to'."""
    run1 = graph_v2_setup["run1"]
    doc = graph_v2_setup["doc"]
    p1, p2 = graph_v2_setup["propositions"][0], graph_v2_setup["propositions"][1]
    h1 = graph_v2_setup["highlights"][0]

    bad_edge = GraphEdge(
        document_id=doc.id,
        run_id=run1.id,
        source_kind="proposition",
        source_id=p1.id,
        target_kind="proposition",
        target_id=p2.id,
        relation_type="precedes",  # Prohibited
        confidence=0.85,
        rationale="Reading order relation",
    )
    db_session.add(bad_edge)
    db_session.commit()

    ev = EdgeEvidence(edge_id=bad_edge.id, highlight_id=h1.id, evidence_quote=h1.quote)
    db_session.add(ev)
    db_session.commit()

    is_valid, issues, _ = validate_extraction_run(run1.id, db_session)
    assert is_valid is False
    assert any("prohibited relation 'precedes'" in iss for iss in issues)

    # Clean up bad edge
    db_session.delete(bad_edge)
    db_session.commit()


def test_validation_fails_on_missing_evidence(db_session, graph_v2_setup):
    """Verify validation blocks edges lacking evidence."""
    run1 = graph_v2_setup["run1"]
    doc = graph_v2_setup["doc"]
    p1, p2 = graph_v2_setup["propositions"][0], graph_v2_setup["propositions"][1]

    unbacked_edge = GraphEdge(
        document_id=doc.id,
        run_id=run1.id,
        source_kind="proposition",
        source_id=p1.id,
        target_kind="proposition",
        target_id=p2.id,
        relation_type="solves",
        confidence=0.85,
        rationale="Hypothetical unbacked link",
    )
    db_session.add(unbacked_edge)
    db_session.commit()

    is_valid, issues, _ = validate_extraction_run(run1.id, db_session)
    assert is_valid is False
    assert any("has no evidence items" in iss for iss in issues)

    db_session.delete(unbacked_edge)
    db_session.commit()


def test_transactional_activation_and_rollback(db_session, graph_v2_setup):
    """Verify activate_extraction_run and rollback_extraction_run maintain transactional consistency."""
    doc = graph_v2_setup["doc"]
    run1 = graph_v2_setup["run1"]

    assert run1.is_active is False

    # 1. Activate Run 1
    activated = activate_extraction_run(
        run_id=run1.id,
        activated_by="lead_ontologist",
        reason="Initial V2 model deployment",
        db=db_session,
    )
    assert activated.is_active is True
    assert activated.status == "active"

    # Verify audit history
    history1 = db_session.query(ExtractionRunActivationHistory).filter_by(run_id=run1.id, action="activate").first()
    assert history1 is not None
    assert history1.activated_by == "lead_ontologist"
    assert history1.previous_run_id is None

    # 2. Create Run 2 and activate it
    run2 = ExtractionRun(
        document_id=doc.id,
        graph_version=2,
        model_name="claude-3-5-sonnet",
        prompt_version="v2.2",
        status="ready_for_review",
        is_active=False,
    )
    db_session.add(run2)
    db_session.commit()

    # Add a minimal valid proposition and edge to run2
    p_run2 = Proposition(
        document_id=doc.id,
        run_id=run2.id,
        canonical_statement="Run 2 claim.",
        statement_type="Claim",
        confidence=0.99,
    )
    db_session.add(p_run2)
    db_session.commit()

    activated2 = activate_extraction_run(
        run_id=run2.id,
        activated_by="admin_user",
        reason="Upgraded model",
        db=db_session,
    )
    db_session.refresh(run1)
    assert activated2.is_active is True
    assert run1.is_active is False  # Demoted!

    # 3. Rollback Run 2 back to Run 1
    restored = rollback_extraction_run(
        document_id=doc.id,
        rolled_back_by="admin_user",
        reason="Reverting run 2 after evaluation",
        db=db_session,
    )
    assert restored is not None
    assert restored.id == run1.id
    assert restored.is_active is True

    db_session.refresh(run2)
    assert run2.is_active is False


def test_legacy_edge_review_protocol(db_session, graph_v2_setup):
    """Verify recording legacy edge review classifications with reason validation."""
    run1 = graph_v2_setup["run1"]
    rel1 = graph_v2_setup["relations"][0]
    rel2 = graph_v2_setup["relations"][1]

    # Valid retained review
    rev1 = record_legacy_edge_review(
        run_id=run1.id,
        legacy_relation_id=rel1.id,
        classification="retained",
        reviewer_reason="V2 edge E1 retains this solves link with verified quote.",
        reviewed_by="evaluator_alice",
        db=db_session,
    )
    assert rev1.classification == "retained"

    # Rejected review without reason should fail
    with pytest.raises(ValueError, match="reviewer reason is required"):
        record_legacy_edge_review(
            run_id=run1.id,
            legacy_relation_id=rel2.id,
            classification="rejected",
            reviewer_reason="",  # Empty reason forbidden
            db=db_session,
        )

    # Rejected review with valid reason
    rev2 = record_legacy_edge_review(
        run_id=run1.id,
        legacy_relation_id=rel2.id,
        classification="rejected",
        reviewer_reason="Generic proximity similar_to edge discarded under V2 strict semantic ontology.",
        reviewed_by="evaluator_alice",
        db=db_session,
    )
    assert rev2.classification == "rejected"

    # Generate mapping report
    report = generate_edge_mapping_report(document_id=graph_v2_setup["doc"].id, run_id=run1.id, db=db_session)
    assert report["total_legacy_edges"] == 2
    assert report["reviewed_edges_count"] == 2
    assert report["review_coverage_pct"] == 100.0
    assert report["classification_breakdown"]["retained"] == 1
    assert report["classification_breakdown"]["rejected"] == 1


def test_graph_api_version_compatibility(db_session, graph_v2_setup):
    """Verify /documents/{id}/graph respects version parameters and cutover boundary."""
    client = TestClient(app)
    doc_id = graph_v2_setup["doc"].id
    run1 = graph_v2_setup["run1"]

    # 1. Before cutover (run1.is_active is False)
    # Default query should return legacy V1 graph
    res_default = client.get(f"/documents/{doc_id}/graph")
    assert res_default.status_code == 200
    data_v1 = res_default.json()
    assert data_v1["graph_version"] == 1
    assert len(data_v1["annotations"]) == 3
    assert len(data_v1["relations"]) >= 2  # rel1, rel2

    # 2. Explicit graph_version=1 must return legacy V1 graph
    res_v1_explicit = client.get(f"/documents/{doc_id}/graph?graph_version=1")
    assert res_v1_explicit.status_code == 200
    assert res_v1_explicit.json()["graph_version"] == 1

    # 3. Explicit run_id query returns V2 data even before cutover
    res_run = client.get(f"/documents/{doc_id}/graph?run_id={run1.id}")
    assert res_run.status_code == 200
    data_v2 = res_run.json()
    assert data_v2["graph_version"] == 2
    assert data_v2["run_id"] == run1.id
    assert len(data_v2["propositions"]) == 3
    assert len(data_v2["concepts"]) == 1
    # By default, include_review=False so 2 accepted edges are returned (excluding needs_review)
    assert len(data_v2["edges"]) == 2

    # Query with include_review=true
    res_run_all = client.get(f"/documents/{doc_id}/graph?run_id={run1.id}&include_review=true")
    assert len(res_run_all.json()["edges"]) == 3

    # Query with confidence filter
    res_conf = client.get(f"/documents/{doc_id}/graph?run_id={run1.id}&min_confidence=0.95")
    assert len(res_conf.json()["edges"]) == 1
    assert res_conf.json()["edges"][0]["relation_type"] == "solves"

    # 4. Activate run1 via API endpoint
    res_act = client.post(f"/documents/{doc_id}/graph/runs/{run1.id}/activate?activated_by=api_tester")
    assert res_act.status_code == 200
    assert res_act.json()["is_active"] is True

    # 5. After cutover: default query returns active V2 graph!
    res_after_cutover = client.get(f"/documents/{doc_id}/graph")
    assert res_after_cutover.status_code == 200
    data_after = res_after_cutover.json()
    assert data_after["graph_version"] == 2
    assert data_after["run_id"] == run1.id
    assert data_after["is_active"] is True

    # 6. Legacy V1 remains fully accessible via explicit graph_version=1
    res_v1_post_cutover = client.get(f"/documents/{doc_id}/graph?graph_version=1")
    assert res_v1_post_cutover.status_code == 200
    assert res_v1_post_cutover.json()["graph_version"] == 1
    assert len(res_v1_post_cutover.json()["annotations"]) == 3

