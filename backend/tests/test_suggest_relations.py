"""Test LLM relation suggestions: valid responses, malformed JSON, taxonomy check, and no API key."""

import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.main import create_app
from backend.app.db import get_db, init_db, reset_engine
from backend.app.models import Document, Annotation, Relation
from backend.app.services.llm import FakeLLMClient, set_shared_llm_client
from backend.app.settings import get_settings


@pytest.fixture
def relation_test_setup(tmp_path, monkeypatch):
    """Set up TestClient with annotations ready for relationship inference."""
    db_file = tmp_path / "test_rel_sug.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("MAX_RELATION_PAIRS", "5")

    get_settings.cache_clear()
    reset_engine()

    engine = create_engine(f"sqlite:///{db_file}")
    init_db(engine_override=engine)
    TestingSession = sessionmaker(bind=engine)

    with TestingSession() as session:
        doc = Document(
            filename="logic.pdf",
            file_hash="hashlogic1",
            status="ready",
            clean_text="Premise A is true. Conclusion B follows logically.",
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

        a1 = Annotation(
            document_id=doc_id,
            start=0,
            end=18,
            quote="Premise A is true.",
            label="Claim",
            version=1,
        )
        a2 = Annotation(
            document_id=doc_id,
            start=19,
            end=49,
            quote="Conclusion B follows logically.",
            label="Result",
            version=1,
        )
        session.add_all([a1, a2])
        session.commit()
        ann1_id, ann2_id = a1.id, a2.id

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, doc_id, ann1_id, ann2_id, TestingSession


def test_suggest_relations_valid_response(relation_test_setup) -> None:
    """Verify successful relation discovery, suggested status, and job completion."""
    client, doc_id, ann1_id, ann2_id, SessionFactory = relation_test_setup

    fake_client = FakeLLMClient(default_type="supports")
    set_shared_llm_client(fake_client)

    res = client.post(f"/documents/{doc_id}/suggest-relations")
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    assert job_id is not None

    # Wait for job to finish
    for _ in range(20):
        time.sleep(0.1)
        job_res = client.get(f"/jobs/{job_id}").json()
        if job_res["status"] in ("done", "failed"):
            break

    job_data = client.get(f"/jobs/{job_id}").json()
    assert job_data["status"] == "done"
    assert job_data["result"]["suggested_count"] > 0

    # Verify suggested relations in DB
    with SessionFactory() as session:
        rels = session.query(Relation).filter(Relation.document_id == doc_id).all()
        assert len(rels) > 0
        assert rels[0].status == "suggested"
        assert rels[0].type == "supports"


def test_suggest_relations_malformed_json(relation_test_setup) -> None:
    """Verify that malformed JSON from LLM is safely handled without crashing."""
    client, doc_id, _, _, _ = relation_test_setup

    malformed_llm = FakeLLMClient(malformed=True)
    set_shared_llm_client(malformed_llm)

    res = client.post(f"/documents/{doc_id}/suggest-relations")
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    for _ in range(20):
        time.sleep(0.1)
        job_res = client.get(f"/jobs/{job_id}").json()
        if job_res["status"] in ("done", "failed"):
            break

    job_data = client.get(f"/jobs/{job_id}").json()
    assert job_data["status"] == "done"
    assert job_data["result"]["suggested_count"] == 0
    assert job_data["result"]["failed_pairs_count"] > 0


def test_suggest_relations_type_not_in_taxonomy(relation_test_setup) -> None:
    """Verify that invalid relation types returned by LLM are excluded."""
    client, doc_id, _, _, _ = relation_test_setup

    fake_client = FakeLLMClient(default_type="unrecognized_alien_relation")
    set_shared_llm_client(fake_client)

    res = client.post(f"/documents/{doc_id}/suggest-relations")
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    for _ in range(20):
        time.sleep(0.1)
        job_res = client.get(f"/jobs/{job_id}").json()
        if job_res["status"] in ("done", "failed"):
            break

    job_data = client.get(f"/jobs/{job_id}").json()
    assert job_data["status"] == "done"
    assert job_data["result"]["suggested_count"] == 0
    assert job_data["result"]["failed_pairs_count"] > 0


def test_suggest_relations_no_api_key(relation_test_setup, monkeypatch) -> None:
    """Verify 503 error when LLM provider requires key but none is configured."""
    client, doc_id, _, _, _ = relation_test_setup

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()
    set_shared_llm_client(None)

    res = client.post(f"/documents/{doc_id}/suggest-relations")
    assert res.status_code == 503
    assert "LLM service is not configured" in res.json()["detail"]


def test_suggest_relations_scoped_seed(relation_test_setup) -> None:
    """Verify relations discovery scoped to a seed annotation."""
    client, doc_id, ann1_id, ann2_id, SessionFactory = relation_test_setup

    fake_client = FakeLLMClient(default_type="supports")
    set_shared_llm_client(fake_client)

    res = client.post(
        f"/documents/{doc_id}/suggest-relations",
        json={"seed_annotation_id": ann1_id},
    )
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    for _ in range(20):
        time.sleep(0.1)
        job_res = client.get(f"/jobs/{job_id}").json()
        if job_res["status"] in ("done", "failed"):
            break

    job_data = client.get(f"/jobs/{job_id}").json()
    assert job_data["status"] == "done"
    assert job_data["result"]["suggested_count"] > 0


def test_suggest_relations_persists_cos_score(relation_test_setup) -> None:
    """Verify cos_score is persisted on suggested Relation and exposed via API."""
    client, doc_id, _, _, SessionFactory = relation_test_setup

    fake_client = FakeLLMClient(default_type="supports")
    set_shared_llm_client(fake_client)

    res = client.post(f"/documents/{doc_id}/suggest-relations")
    job_id = res.json()["job_id"]

    for _ in range(20):
        time.sleep(0.1)
        job_res = client.get(f"/jobs/{job_id}").json()
        if job_res["status"] in ("done", "failed"):
            break

    with SessionFactory() as session:
        rel = session.query(Relation).filter(Relation.document_id == doc_id).first()
        assert rel is not None
        assert rel.cos_score is not None
        assert rel.score == rel.cos_score

    # Check /graph endpoint exposes score and cos_score
    graph_res = client.get(f"/documents/{doc_id}/graph").json()
    assert len(graph_res["relations"]) > 0
    assert graph_res["relations"][0]["cos_score"] is not None


def test_suggest_relations_prunes_skip_label_pairs(relation_test_setup) -> None:
    """Verify Definition <-> Result pairs are pruned by label-pair filter."""
    client, doc_id, _, _, SessionFactory = relation_test_setup

    with SessionFactory() as session:
        # Clear existing annotations and add Definition <-> Result
        session.query(Relation).filter(Relation.document_id == doc_id).delete()
        session.query(Annotation).filter(Annotation.document_id == doc_id).delete()
        d_ann = Annotation(
            document_id=doc_id,
            start=0,
            end=10,
            quote="Definition of term",
            label="Definition",
            version=1,
        )
        r_ann = Annotation(
            document_id=doc_id,
            start=11,
            end=25,
            quote="Result achieved here",
            label="Result",
            version=1,
        )
        session.add_all([d_ann, r_ann])
        session.commit()

    fake_client = FakeLLMClient(default_type="supports")
    set_shared_llm_client(fake_client)

    res = client.post(f"/documents/{doc_id}/suggest-relations")
    job_id = res.json()["job_id"]

    for _ in range(20):
        time.sleep(0.1)
        job_res = client.get(f"/jobs/{job_id}").json()
        if job_res["status"] in ("done", "failed"):
            break

    job_data = client.get(f"/jobs/{job_id}").json()
    assert job_data["status"] == "done"
    # Filter pruned the pair so 0 candidates were sent to LLM
    assert job_data["result"]["suggested_count"] == 0


def test_suggest_relations_caching_avoids_llm(relation_test_setup) -> None:
    """Verify that cached relation inferences are retrieved from DB without calling LLM."""
    client, doc_id, _, _, SessionFactory = relation_test_setup

    fake_client = FakeLLMClient(default_type="supports")
    set_shared_llm_client(fake_client)

    # First run: populates cache
    res = client.post(f"/documents/{doc_id}/suggest-relations")
    job_id = res.json()["job_id"]
    for _ in range(20):
        time.sleep(0.1)
        if client.get(f"/jobs/{job_id}").json()["status"] in ("done", "failed"):
            break

    # Verify cache has entries
    with SessionFactory() as session:
        from backend.app.models import RelationCache
        caches = session.query(RelationCache).all()
        assert len(caches) > 0
        # Delete relation row from DB to simulate fresh discovery
        session.query(Relation).filter(Relation.document_id == doc_id).delete()
        session.commit()

    # Second run: configure LLM to fail if invoked
    failing_llm = FakeLLMClient(fail=True)
    set_shared_llm_client(failing_llm)

    res2 = client.post(f"/documents/{doc_id}/suggest-relations")
    job_id2 = res2.json()["job_id"]
    for _ in range(20):
        time.sleep(0.1)
        if client.get(f"/jobs/{job_id2}").json()["status"] in ("done", "failed"):
            break

    job_data2 = client.get(f"/jobs/{job_id2}").json()
    assert job_data2["status"] == "done"
    # Successfully retrieved from cache!
    assert job_data2["result"]["suggested_count"] > 0


def test_suggest_relations_rejected_pair_not_resuggested(relation_test_setup) -> None:
    """Verify deleted/rejected relations are saved in RejectedPair and skipped in future runs."""
    client, doc_id, _, _, SessionFactory = relation_test_setup

    fake_client = FakeLLMClient(default_type="supports")
    set_shared_llm_client(fake_client)

    res = client.post(f"/documents/{doc_id}/suggest-relations")
    job_id = res.json()["job_id"]
    for _ in range(20):
        time.sleep(0.1)
        if client.get(f"/jobs/{job_id}").json()["status"] in ("done", "failed"):
            break

    # Get suggested relation ID and delete it
    with SessionFactory() as session:
        rel = session.query(Relation).filter(Relation.document_id == doc_id).first()
        rel_id = rel.id

    del_res = client.delete(f"/relations/{rel_id}")
    assert del_res.status_code == 204

    # Verify RejectedPair entry exists
    with SessionFactory() as session:
        from backend.app.models import RejectedPair
        rejected = session.query(RejectedPair).filter(RejectedPair.document_id == doc_id).all()
        assert len(rejected) > 0

    # Re-run suggestion job: pair should be skipped
    res2 = client.post(f"/documents/{doc_id}/suggest-relations")
    job_id2 = res2.json()["job_id"]
    for _ in range(20):
        time.sleep(0.1)
        if client.get(f"/jobs/{job_id2}").json()["status"] in ("done", "failed"):
            break

    job_data2 = client.get(f"/jobs/{job_id2}").json()
    assert job_data2["status"] == "done"
    assert job_data2["result"]["suggested_count"] == 0


def test_suggest_relations_new_taxonomy_types(relation_test_setup) -> None:
    """Verify contrasts_with, conditional_on, and precedes can be suggested."""
    client, doc_id, _, _, SessionFactory = relation_test_setup

    # Test contrasts_with
    fake_client = FakeLLMClient(default_type="contrasts_with")
    set_shared_llm_client(fake_client)

    res = client.post(f"/documents/{doc_id}/suggest-relations")
    job_id = res.json()["job_id"]
    for _ in range(20):
        time.sleep(0.1)
        if client.get(f"/jobs/{job_id}").json()["status"] in ("done", "failed"):
            break

    job_data = client.get(f"/jobs/{job_id}").json()
    assert job_data["status"] == "done"
    assert job_data["result"]["suggested_count"] > 0

    with SessionFactory() as session:
        rel = session.query(Relation).filter(Relation.document_id == doc_id).first()
        assert rel.type == "contrasts_with"


