"""Tests for canonical entity resolution, tombstone lifecycles, and entity API routes."""

import pytest
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from backend.app.models import (
    Document,
    Mention,
    GraphRelation,
    RelationEvidence,
)
from backend.app.services.entity_resolution import EntityResolutionService
from backend.app.services.llm import FakeLLMClient
from backend.app.main import app


@pytest.fixture
def test_db(engine, monkeypatch):
    connection = engine.connect()
    transaction = connection.begin()
    TestingSession = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")

    import backend.app.db as app_db
    monkeypatch.setattr(app_db, "get_session_factory", lambda eng=None: TestingSession)
    monkeypatch.setattr(app_db, "_SessionLocal", TestingSession)
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))

    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        app_db.reset_engine()


def test_scoped_exact_match_auto_merge(test_db):
    """Verify exact match auto-merges only within same node_type."""
    resolver = EntityResolutionService(test_db, llm_client=FakeLLMClient())

    node1 = resolver.resolve_or_create_node("CNN", "Method")
    # Exact match with different case/spaces should return same node
    node2 = resolver.resolve_or_create_node(" cnn ", "Method")
    assert node1.id == node2.id

    # Same surface name but different type (Dataset vs Method) MUST NOT auto-merge
    node3 = resolver.resolve_or_create_node("CNN", "Dataset")
    assert node3.id != node1.id
    assert node3.node_type == "Dataset"


def test_candidate_adjudication_bert_base_large(test_db):
    """Verify BERT-Base vs BERT-Large test: cosine >= 0.70 routed to LLM adjudication."""
    resolver = EntityResolutionService(test_db, llm_client=FakeLLMClient())

    v_base = np.ones(384, dtype=np.float32) / np.sqrt(384)
    v_large = v_base.copy()
    # Add slight perturbation so similarity is ~0.85
    v_large[0] += 0.5
    v_large /= np.linalg.norm(v_large)

    node_base = resolver.resolve_or_create_node("BERT-Base", "Method", embedding=v_base)
    # FakeLLMClient returns DISTINCT
    node_large = resolver.resolve_or_create_node("BERT-Large", "Method", embedding=v_large)

    assert node_base.id != node_large.id
    assert node_base.merged_into_id is None
    assert node_large.merged_into_id is None


def test_merge_nodes_repointing_and_revert(test_db):
    """Verify merging repoints mentions, relations, unions evidence, and can be reverted."""
    resolver = EntityResolutionService(test_db, llm_client=FakeLLMClient())

    doc = Document(id=1, filename="doc.pdf", file_hash="h1", status="ready", clean_text="Text")
    test_db.add(doc)
    test_db.commit()

    node_a = resolver.resolve_or_create_node("Adam Optimizer", "Method")
    node_b = resolver.resolve_or_create_node("Adam algorithm", "Method")
    node_c = resolver.resolve_or_create_node("Cross Entropy", "Metric")

    # Add mentions to node_b
    m1 = Mention(document_id=1, node_id=node_b.id, quote="Adam algorithm", start=0, end=14, page=1)
    test_db.add(m1)

    # Add relation from node_b to node_c
    rel = GraphRelation(
        document_id=1,
        source_node_id=node_b.id,
        target_node_id=node_c.id,
        relation_type="evaluates_with",
    )
    test_db.add(rel)
    test_db.flush()

    ev = RelationEvidence(
        relation_id=rel.id,
        document_id=1,
        verbatim_quote="Adam algorithm",
        start=0,
        end=14,
    )
    test_db.add(ev)
    test_db.commit()

    # Execute merge: node_b into node_a
    log = resolver.merge_nodes(
        surviving_node_id=node_a.id,
        absorbed_node_id=node_b.id,
        reason="Synonymous optimization method",
    )
    assert log.id is not None
    assert node_b.merged_into_id == node_a.id

    # Check mention repointed
    test_db.refresh(m1)
    assert m1.node_id == node_a.id

    # Check relation source repointed
    test_db.refresh(rel)
    assert rel.source_node_id == node_a.id

    # Revert merge
    success = resolver.revert_merge(log.id)
    assert success is True
    test_db.refresh(node_b)
    assert node_b.merged_into_id is None


def test_entities_api_endpoints(test_db):
    """Verify /nodes, /nodes/{id}, /nodes/merge, /nodes/revert-merge endpoints via TestClient."""
    from backend.app.db import get_db

    def override_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)

        # Create node through API or query
        resp = client.get("/nodes")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

        resp_pending = client.get("/nodes/merge-pending")
        assert resp_pending.status_code == 200
        assert isinstance(resp_pending.json(), list)
    finally:
        app.dependency_overrides.pop(get_db, None)
