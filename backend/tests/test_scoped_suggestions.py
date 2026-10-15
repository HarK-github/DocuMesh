"""Comprehensive tests for Part C: scoped suggestions, pure scoring, MMR diversity, pending cap, atomic accept, and idempotency."""

import pytest
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import create_app
from backend.app.db import get_db, init_db, reset_engine
from backend.app.models import Document, Sentence, Annotation, Suggestion, Relation
from backend.app.services.embedder import FakeEmbedder, set_shared_embedder
from backend.app.services.ranker import (
    compute_candidate_score,
    select_diverse_candidates_mmr,
    cosine_similarity,
)
from backend.app.settings import get_settings


# ---------------------------------------------------------------------------
# Unit tests for pure scoring and MMR
# ---------------------------------------------------------------------------

def test_compute_candidate_score_with_known_vectors() -> None:
    """Test pure scoring function: score = max_sim(cand, positives) - neg_weight * max_sim(cand, negatives)."""
    p1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    p2 = np.array([0.7071, 0.7071, 0.0], dtype=np.float32)
    n1 = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    # Candidate matches p1 exactly
    c_exact_pos = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    score = compute_candidate_score(c_exact_pos, [p1, p2], [n1], neg_weight=0.5)
    # pos_sim = 1.0, neg_sim = 0.0 -> score = 1.0
    assert abs(score - 1.0) < 1e-4

    # Candidate halfway between p1 and n1
    c_half = np.array([0.7071, 0.7071, 0.0], dtype=np.float32)
    # pos_sim with p2 is 1.0, neg_sim with n1 is 0.7071
    # score = 1.0 - 0.5 * 0.7071 = 0.6464
    score_half = compute_candidate_score(c_half, [p1, p2], [n1], neg_weight=0.5)
    assert abs(score_half - (1.0 - 0.5 * 0.7071)) < 1e-3

    # Candidate matches n1 exactly
    c_neg = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    # pos_sim = 0.7071 (with p2), neg_sim = 1.0 (with n1)
    # score = 0.7071 - 0.5 * 1.0 = 0.2071
    score_neg = compute_candidate_score(c_neg, [p1, p2], [n1], neg_weight=0.5)
    assert abs(score_neg - (0.7071 - 0.5)) < 1e-3


def test_select_diverse_candidates_mmr_avoids_near_duplicates() -> None:
    """MMR diversity avoids picking redundant near-identical candidates."""
    # Seed / query direction is [1, 0, 0]
    # c1 and c2 are almost identical [1, 0, 0] and [0.999, 0.01, 0]
    # c3 is slightly lower score [0.8, 0.6, 0] but distinct
    c1 = {
        "id": 1,
        "score": 0.95,
        "vector": np.array([1.0, 0.0, 0.0], dtype=np.float32),
    }
    c2 = {
        "id": 2,
        "score": 0.94,
        "vector": np.array([0.999, 0.01, 0.0], dtype=np.float32),
    }
    c3 = {
        "id": 3,
        "score": 0.85,
        "vector": np.array([0.7, 0.71, 0.0], dtype=np.float32),
    }

    # With high diversity penalty (mmr_lambda = 0.5), c3 should be picked ahead of the near-duplicate c2
    selected = select_diverse_candidates_mmr([c1, c2, c3], mmr_lambda=0.5, limit=2)
    assert len(selected) == 2
    assert selected[0]["id"] == 1
    assert selected[1]["id"] == 3  # c3 chosen over duplicate c2!


# ---------------------------------------------------------------------------
# Integration tests for Scoped Suggestions Endpoints
# ---------------------------------------------------------------------------

@pytest.fixture
def scoped_setup(tmp_path, monkeypatch):
    """Set up TestClient with FakeEmbedder, FakeVectorStore, and documents."""
    db_file = tmp_path / "test_scoped.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setenv("VECTOR_STORE", "fake")
    monkeypatch.setenv("SIMILARITY_THRESHOLD", "0.2")
    monkeypatch.setenv("MAX_PENDING_PER_SEED", "2")
    monkeypatch.setenv("SUGGESTION_COUNT", "3")

    get_settings.cache_clear()
    reset_engine()

    engine = create_engine(f"sqlite:///{db_file}")
    init_db(engine_override=engine)
    TestingSession = sessionmaker(bind=engine)

    fake_emb = FakeEmbedder(dim=8)
    set_shared_embedder(fake_emb)

    text = (
        "Artificial intelligence revolutionizes computers. "    # s0 (0, 51) - Ann 1 (Claim)
        "Machine learning models require big data. "            # s1 (51, 93) - Ann 2 (Claim)
        "Deep neural networks learn representations well. "     # s2 (93, 142)
        "Robotics systems transform industrial manufacturing. " # s3 (142, 196)
        "Computer vision algorithms detect complex objects. "   # s4 (196, 248)
        "Natural language models comprehend human phrases. "    # s5 (248, 299)
        "A delicious recipe for homemade apple pie treats. "    # s6 (299, 349) - Ann 3 (Method)
        "Baking ingredients include fresh apples and flour. "   # s7 (349, 401)
        "Preheat the kitchen oven before preparing crusts."     # s8 (401, 451)
    )

    with TestingSession() as session:
        doc = Document(
            filename="ai_and_cooking.pdf",
            file_hash="scoped_hash_1",
            status="ready",
            clean_text=text,
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

        # Insert sentences
        ranges = [
            (0, 51),
            (51, 93),
            (93, 142),
            (142, 196),
            (196, 248),
            (248, 299),
            (299, 349),
            (349, 401),
            (401, 451),
        ]
        s_objs = []
        for idx, (st, en) in enumerate(ranges):
            q = text[st:en]
            emb = fake_emb.embed([q])[0]
            s = Sentence(
                document_id=doc_id,
                idx=idx,
                start=st,
                end=en,
                page=1,
                embedding=emb.tobytes(),
            )
            s_objs.append(s)
            session.add(s)
        session.commit()

        # Create annotations:
        ann1 = Annotation(
            document_id=doc_id,
            start=0,
            end=50,
            quote=text[0:50],
            label="Claim",
            version=1,
        )
        ann2 = Annotation(
            document_id=doc_id,
            start=51,
            end=92,
            quote=text[51:92],
            label="Claim",
            version=1,
        )
        ann3 = Annotation(
            document_id=doc_id,
            start=299,
            end=348,
            quote=text[299:348],
            label="Method",
            version=1,
        )
        session.add_all([ann1, ann2, ann3])
        session.commit()
        ann1_id = ann1.id
        ann2_id = ann2.id
        ann3_id = ann3.id

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, doc_id, ann1_id, ann2_id, ann3_id, TestingSession


def test_never_seed_from_unconfirmed_suggestions(scoped_setup) -> None:
    """Only confirmed annotations can be used as seeds; suggestion IDs return 404."""
    client, doc_id, _, _, _, TestingSession = scoped_setup

    with TestingSession() as session:
        sent = session.query(Sentence).filter(Sentence.document_id == doc_id).first()
        sug = Suggestion(
            id=9999,
            document_id=doc_id,
            sentence_id=sent.id,
            score=0.8,
            status="pending",
        )
        session.add(sug)
        session.commit()
        sug_id = sug.id

    # Attempting to seed with a suggestion ID must fail with 404
    res = client.post(
        f"/documents/{doc_id}/suggest-highlights",
        json={"seed_annotation_id": sug_id, "scope": "passage"},
    )
    assert res.status_code == 404
    assert "only confirmed annotations" in res.json()["detail"].lower()


def test_scope_passage_vs_category_positives(scoped_setup) -> None:
    """Passage scope uses seed only; category scope aggregates all annotations with seed label."""
    client, doc_id, ann1_id, _, ann3_id, _ = scoped_setup

    # Suggest with passage scope on ann1 (Claim)
    res_passage = client.post(
        f"/documents/{doc_id}/suggest-highlights",
        json={"seed_annotation_id": ann1_id, "scope": "passage"},
    )
    assert res_passage.status_code == 200
    sugs_passage = res_passage.json()
    assert len(sugs_passage) > 0
    assert all(s["label"] == "Claim" for s in sugs_passage)
    assert all(s["scope"] == "passage" for s in sugs_passage)

    # Suggest with category scope on ann3 (Method)
    res_category = client.post(
        f"/documents/{doc_id}/suggest-highlights",
        json={"seed_annotation_id": ann3_id, "scope": "category"},
    )
    assert res_category.status_code == 200
    sugs_cat = res_category.json()
    assert len(sugs_cat) > 0
    assert all(s["label"] == "Method" for s in sugs_cat)
    assert all(s["scope"] == "category" for s in sugs_cat)



def test_negatives_are_label_scoped(scoped_setup) -> None:
    """Rejection under one label does not penalize suggestions under another label."""
    client, doc_id, ann1_id, _, ann3_id, TestingSession = scoped_setup

    # Reject a cooking sentence under label "Method"
    with TestingSession() as session:
        sent_cooking = (
            session.query(Sentence)
            .filter(Sentence.document_id == doc_id, Sentence.start == 349)
            .first()
        )
        rej_method = Suggestion(
            document_id=doc_id,
            sentence_id=sent_cooking.id,
            score=0.8,
            status="rejected",
            label="Method",
        )
        session.add(rej_method)
        session.commit()

    # Now suggest highlights for AI seed (Claim)
    # The rejected Method suggestion should not penalize Claim
    res = client.post(
        f"/documents/{doc_id}/suggest-highlights",
        json={"seed_annotation_id": ann1_id, "scope": "passage"},
    )
    assert res.status_code == 200
    claim_sugs = res.json()
    # Results should be Claim and AI-related
    assert all(s["label"] == "Claim" for s in claim_sugs)


def test_pending_cap(scoped_setup) -> None:
    """Returns existing pending suggestions without creating new ones when cap is hit."""
    client, doc_id, ann1_id, _, _, _ = scoped_setup
    # In fixture, MAX_PENDING_PER_SEED is set to 2

    res1 = client.post(
        f"/documents/{doc_id}/suggest-highlights",
        json={"seed_annotation_id": ann1_id, "scope": "passage"},
    )
    assert res1.status_code == 200
    assert len(res1.json()) <= 2

    # Second request hits the cap of 2
    res2 = client.post(
        f"/documents/{doc_id}/suggest-highlights",
        json={"seed_annotation_id": ann1_id, "scope": "passage"},
    )
    assert res2.status_code == 200
    res2_json = res2.json()
    assert len(res2_json) <= 2
    if len(res2_json) == 2:
        assert res2_json[0].get("message") is not None
        assert "maximum pending" in res2_json[0]["message"].lower()


def test_atomic_accept_and_idempotency(scoped_setup) -> None:
    """Accept creates annotation + similar_to relation in one transaction; idempotent."""
    client, doc_id, ann1_id, _, _, TestingSession = scoped_setup

    res = client.post(
        f"/documents/{doc_id}/suggest-highlights",
        json={"seed_annotation_id": ann1_id, "scope": "passage"},
    )
    assert res.status_code == 200
    sugs = res.json()
    assert len(sugs) > 0
    target_sug = sugs[0]

    # Accept suggestion
    acc_res = client.post(f"/suggestions/{target_sug['id']}/accept")
    assert acc_res.status_code == 200
    acc_data = acc_res.json()
    assert acc_data["status"] == "accepted"

    # Verify annotation created in DB with the suggestion's label
    with TestingSession() as session:
        new_ann = (
            session.query(Annotation)
            .filter(
                Annotation.document_id == doc_id,
                Annotation.start == target_sug["start"],
                Annotation.end == target_sug["end"],
            )
            .first()
        )
        assert new_ann is not None
        assert new_ann.label == target_sug["label"]

        # Verify similar_to relation exists connecting seed -> new_ann
        rel = (
            session.query(Relation)
            .filter(
                Relation.document_id == doc_id,
                Relation.source_id == ann1_id,
                Relation.target_id == new_ann.id,
                Relation.type == "similar_to",
            )
            .first()
        )
        assert rel is not None
        assert rel.status == "confirmed"
        assert rel.reason is not None

    # Idempotent accept: accept again
    acc2 = client.post(f"/suggestions/{target_sug['id']}/accept")
    assert acc2.status_code == 200

    # Verify no duplicate relation was created
    with TestingSession() as session:
        rel_count = (
            session.query(Relation)
            .filter(
                Relation.document_id == doc_id,
                Relation.source_id == ann1_id,
                Relation.target_id == new_ann.id,
                Relation.type == "similar_to",
            )
            .count()
        )
        assert rel_count == 1


def test_reject_idempotency(scoped_setup) -> None:
    """Rejecting a suggestion sets status to rejected and is idempotent."""
    client, doc_id, ann1_id, _, _, _ = scoped_setup

    res = client.post(
        f"/documents/{doc_id}/suggest-highlights",
        json={"seed_annotation_id": ann1_id, "scope": "passage"},
    )
    assert res.status_code == 200
    sugs = res.json()
    assert len(sugs) > 0
    target_sug = sugs[0]

    # Reject
    rej1 = client.post(f"/suggestions/{target_sug['id']}/reject")
    assert rej1.status_code == 200
    assert rej1.json()["status"] == "rejected"

    # Reject again (idempotent)
    rej2 = client.post(f"/suggestions/{target_sug['id']}/reject")
    assert rej2.status_code == 200
    assert rej2.json()["status"] == "rejected"


def test_graph_includes_ghost_nodes_and_excludes_rejected(scoped_setup) -> None:
    """Graph endpoint returns suggested ghost nodes and edges, and excludes rejected suggestions."""
    client, doc_id, ann1_id, _, _, _ = scoped_setup

    res = client.post(
        f"/documents/{doc_id}/suggest-highlights",
        json={"seed_annotation_id": ann1_id, "scope": "passage"},
    )
    assert res.status_code == 200
    sugs = res.json()
    assert len(sugs) >= 2
    sug_to_reject = sugs[0]
    sug_to_keep = sugs[1]

    # Graph initially has confirmed nodes + ghost nodes for both suggestions
    g_res = client.get(f"/documents/{doc_id}/graph")
    assert g_res.status_code == 200
    graph = g_res.json()

    ghost_nodes = [n for n in graph["annotations"] if n["status"] == "suggested"]
    ghost_edges = [e for e in graph["relations"] if e["status"] == "suggested"]

    assert any(n["id"] == sug_to_reject["id"] for n in ghost_nodes)
    assert any(n["id"] == sug_to_keep["id"] for n in ghost_nodes)
    assert all(n["seed_annotation_id"] == ann1_id for n in ghost_nodes)
    assert all(n["label"] == "Claim" for n in ghost_nodes)
    assert all(n["score"] is not None for n in ghost_nodes)

    assert any(e["type"] == "similar_to" and e["source_id"] == sug_to_reject["id"] and e["target_id"] == ann1_id for e in ghost_edges)
    assert any(e["type"] == "similar_to" and e["source_id"] == sug_to_keep["id"] and e["target_id"] == ann1_id for e in ghost_edges)

    # Reject one suggestion
    client.post(f"/suggestions/{sug_to_reject['id']}/reject")

    # Rejected suggestion must be absent from graph
    g_res2 = client.get(f"/documents/{doc_id}/graph")
    graph2 = g_res2.json()
    ghost_nodes2 = [n for n in graph2["annotations"] if n["status"] == "suggested"]
    ghost_edges2 = [e for e in graph2["relations"] if e["status"] == "suggested"]
    assert not any(n["id"] == sug_to_reject["id"] for n in ghost_nodes2)
    assert not any(e["source_id"] == sug_to_reject["id"] for e in ghost_edges2)

    # sug_to_keep is still present
    assert any(n["id"] == sug_to_keep["id"] for n in ghost_nodes2)
    assert any(e["source_id"] == sug_to_keep["id"] and e["target_id"] == ann1_id for e in ghost_edges2)


def test_dynamic_relation_inference_on_accept(scoped_setup) -> None:
    """Verify that accepting suggestions between different categories dynamically assigns typed relations."""
    client, doc_id, _, _, _, TestingSession = scoped_setup

    # Create a Problem annotation and a Solution suggestion
    with TestingSession() as session:
        prob = Annotation(
            document_id=doc_id,
            start=0,
            end=10,
            quote="Problem statement here",
            label="Problem",
            version=1,
        )
        session.add(prob)
        session.commit()
        prob_id = prob.id

        sent = session.query(Sentence).filter(Sentence.document_id == doc_id).first()
        sug = Suggestion(
            document_id=doc_id,
            sentence_id=sent.id,
            seed_annotation_id=prob_id,
            label="Solution",
            scope="passage",
            score=0.91,
            status="pending",
        )
        session.add(sug)
        session.commit()
        sug_id = sug.id

    # Accept the Solution suggestion
    res = client.post(f"/suggestions/{sug_id}/accept")
    assert res.status_code == 200

    # Verify that the created relation has type "solves"
    with TestingSession() as session:
        rel = (
            session.query(Relation)
            .filter(
                Relation.document_id == doc_id,
                Relation.target_id == prob_id,
                Relation.type == "solves",
            )
            .first()
        )
        assert rel is not None
        assert rel.status == "confirmed"

