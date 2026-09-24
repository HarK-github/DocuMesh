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
