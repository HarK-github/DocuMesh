"""Tests for GraphProjectionService, multi-mode retrieval (vector, graph, hybrid), and global /chat."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import create_app
from backend.app.db import get_db, init_db
from backend.app.models import (
    Document,
    Sentence,
    Node,
    NodeAlias,
    GraphRelation,
    RelationEvidence,
    Chunk,
    Annotation,
)
from backend.app.services.graph_service import (
    GraphProjectionService,
    reciprocal_rank_fusion,
)
from backend.app.services.embedder import FakeEmbedder, set_shared_embedder
from backend.app.services.llm import FakeLLMClient, set_shared_llm_client
from backend.app.settings import get_settings


@pytest.fixture
def graphrag_setup(tmp_path, monkeypatch):
    db_file = tmp_path / "test_graphrag.db"
    db_url = f"sqlite:///{db_file}"
    eng = create_engine(db_url, connect_args={"check_same_thread": False})
    init_db(engine_override=eng)
    TestingSession = sessionmaker(bind=eng, autoflush=False, autocommit=False)

    import backend.app.db as app_db
    monkeypatch.setattr(app_db, "get_session_factory", lambda eng_arg=None: TestingSession)
    monkeypatch.setattr(app_db, "_SessionLocal", TestingSession)
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "fake")
    monkeypatch.setenv("CHAT_MIN_RELEVANCE", "-1.0")

    get_settings.cache_clear()

    fake_embedder = FakeEmbedder()
    set_shared_embedder(fake_embedder)
    fake_llm = FakeLLMClient()
    set_shared_llm_client(fake_llm)

    with TestingSession() as session:
        # Create Doc 1
        d1 = Document(
            id=1,
            filename="paper1.pdf",
            file_hash="h1",
            status="ready",
            clean_text="Simulated annealing is a local search optimization algorithm. It avoids local maxima.",
        )
        # Create Doc 2
        d2 = Document(
            id=2,
            filename="paper2.pdf",
            file_hash="h2",
            status="ready",
            clean_text="Malware detection constructs feature graphs. Graph neural networks classify basic blocks.",
        )
        session.add_all([d1, d2])
        session.commit()

        # Add sentences
        s1 = Sentence(document_id=1, idx=0, start=0, end=62, page=1, embedding=fake_embedder.embed(["Simulated annealing is a local search optimization algorithm."])[0])
        s2 = Sentence(document_id=1, idx=1, start=63, end=88, page=1, embedding=fake_embedder.embed(["It avoids local maxima."])[0])
        s3 = Sentence(document_id=2, idx=0, start=0, end=40, page=1, embedding=fake_embedder.embed(["Malware detection constructs feature graphs."])[0])
        s4 = Sentence(document_id=2, idx=1, start=41, end=97, page=1, embedding=fake_embedder.embed(["Graph neural networks classify basic blocks."])[0])
        session.add_all([s1, s2, s3, s4])

        # Add chunks
        c1 = Chunk(
            document_id=1,
            chunk_index=0,
            start=0,
            end=88,
            page=1,
            first_sentence_idx=0,
            last_sentence_idx=1,
            token_count=15,
            text="Simulated annealing is a local search optimization algorithm. It avoids local maxima.",
            embedding=fake_embedder.embed(["Simulated annealing is a local search optimization algorithm. It avoids local maxima."])[0],
        )
        c2 = Chunk(
            document_id=2,
            chunk_index=0,
            start=0,
            end=97,
            page=1,
            first_sentence_idx=0,
            last_sentence_idx=1,
            token_count=15,
            text="Malware detection constructs feature graphs. Graph neural networks classify basic blocks.",
            embedding=fake_embedder.embed(["Malware detection constructs feature graphs. Graph neural networks classify basic blocks."])[0],
        )
        # Add annotations
        a1 = Annotation(
            id=1,
            document_id=1,
            start=0,
            end=62,
            quote="Simulated annealing is a local search optimization algorithm.",
            label="Definition",
        )
        a2 = Annotation(
            id=2,
            document_id=1,
            start=63,
            end=88,
            quote="It avoids local maxima.",
            label="Claim",
        )
        session.add_all([c1, c2, a1, a2])
        session.commit()

        # Nodes
        n1 = Node(id=1, name="Simulated Annealing", normalized_name="simulated annealing", node_type="Method", is_global=True)
        n2 = Node(id=2, name="Local Maxima", normalized_name="local maxima", node_type="Problem", is_global=True)
        n3 = Node(id=3, name="Feature Graph", normalized_name="feature graph", node_type="Method", is_global=True)
        session.add_all([n1, n2, n3])
        session.commit()

        # Aliases
        session.add(NodeAlias(node_id=1, alias="Simulated Annealing", normalized_alias="simulated annealing"))
        session.add(NodeAlias(node_id=2, alias="Local Maxima", normalized_alias="local maxima"))
        session.add(NodeAlias(node_id=3, alias="Feature Graph", normalized_alias="feature graph"))
        session.commit()

        # Relations & Evidence
        rel1 = GraphRelation(id=1, document_id=1, source_node_id=1, target_node_id=2, relation_type="solves", confidence=0.95)
        session.add(rel1)
        session.commit()

        ev1 = RelationEvidence(relation_id=1, document_id=1, sentence_id=s2.id, verbatim_quote="It avoids local maxima.", start=63, end=88)
        session.add(ev1)
        session.commit()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, TestingSession

    eng.dispose()
    app_db.reset_engine()


def test_graph_projection_service(graphrag_setup):
    """Verify NetworkX graph builds nodes, edges, seeds, and traverses hops."""
    _, TestingSession = graphrag_setup
    with TestingSession() as session:
        fake_embedder = FakeEmbedder()
        service = GraphProjectionService(session, embedder=fake_embedder)

        assert service.graph.number_of_nodes() >= 3
        assert service.graph.number_of_edges() >= 1

        q_vec = fake_embedder.embed(["Simulated Annealing"])[0]
        seeds = service.find_seed_nodes("How does simulated annealing work?", q_vec)
        assert 1 in seeds
        assert seeds[1] >= 0.9

        traversed_edges, harvested_sentences = service.expand_graph_context(seeds, max_hops=2)
        assert len(traversed_edges) >= 1
        assert traversed_edges[0]["id"] == 1
        assert len(harvested_sentences) >= 1


def test_reciprocal_rank_fusion():
    """Verify RRF rank calculation and missing branch handling."""
    vec_s = [{"id": 1, "score": 0.9}, {"id": 2, "score": 0.8}]
    graph_s = [{"id": 2, "score": 0.95}, {"id": 3, "score": 0.7}]

    fused = reciprocal_rank_fusion(vec_s, graph_s, k=60, top_n=5)
    fused_ids = [item["id"] for item in fused]

    # Item 2 appears in both branches, so should have highest RRF score
    assert fused_ids[0] == 2
    assert 1 in fused_ids
    assert 3 in fused_ids


def test_multi_mode_retrieval_routes(graphrag_setup):
    """Verify document chat accepts vector, graph, and hybrid modes."""
    client, _ = graphrag_setup

    # 1. Vector mode
    resp_vec = client.post(
        "/documents/1/chat",
        json={"question": "What is simulated annealing?", "mode": "vector"},
    )
    assert resp_vec.status_code == 200
    assert resp_vec.json()["used_context"] is True

    # 2. Graph mode
    resp_graph = client.post(
        "/documents/1/chat",
        json={"question": "What does simulated annealing solve?", "mode": "graph"},
    )
    assert resp_graph.status_code == 200
    assert resp_graph.json()["used_context"] is True

    # 3. Hybrid mode
    resp_hybrid = client.post(
        "/documents/1/chat",
        json={"question": "Explain local maxima and simulated annealing.", "mode": "hybrid"},
    )
    assert resp_hybrid.status_code == 200
    assert resp_hybrid.json()["used_context"] is True


def test_global_corpus_chat(graphrag_setup):
    """Verify global /chat connects information across multiple documents."""
    client, _ = graphrag_setup

    resp = client.post(
        "/chat",
        json={"question": "How do optimization and feature graphs relate?", "mode": "hybrid"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert data["used_context"] is True
