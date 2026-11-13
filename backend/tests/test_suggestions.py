"""Test smart highlight suggestions, acceptance into annotations, and rejection."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from backend.app.main import create_app
from backend.app.db import get_db
from backend.app.models import Document, Sentence
from backend.app.services.embedder import FakeEmbedder, set_shared_embedder
from backend.app.settings import get_settings


@pytest.fixture
def suggestions_setup(engine, monkeypatch):
    """Set up TestClient with FakeEmbedder and a sample segmented document."""
    connection = engine.connect()
    transaction = connection.begin()
    TestingSession = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")

    import backend.app.db as app_db
    monkeypatch.setattr(app_db, "get_session_factory", lambda engine=None: TestingSession)
    monkeypatch.setattr(app_db, "_SessionLocal", TestingSession)
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv("SIMILARITY_THRESHOLD", "-1.0")  # Accept all for test predictability
    monkeypatch.setenv("SUGGESTION_COUNT", "5")
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "fake")

    get_settings.cache_clear()

    # Use FakeEmbedder for fast isolated testing
    fake_emb = FakeEmbedder()
    set_shared_embedder(fake_emb)

    text = "Can machines think? Digital computers are universal. The imitation game is played with three people."
    # sentences:
    # 0: "Can machines think?" (0, 19)
    # 1: "Digital computers are universal." (20, 52)
    # 2: "The imitation game is played with three people." (53, 99)

    with TestingSession() as session:
        doc = Document(
            filename="test.pdf",
            file_hash="fakehash777",
            status="ready",
            clean_text=text,
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

        s1 = Sentence(document_id=doc_id, idx=0, start=0, end=19, page=1)
        s2 = Sentence(document_id=doc_id, idx=1, start=20, end=52, page=1)
        s3 = Sentence(document_id=doc_id, idx=2, start=53, end=99, page=1)
        session.add_all([s1, s2, s3])
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
        yield client, doc_id, text

    transaction.rollback()
    connection.close()
    app_db.reset_engine()


def test_suggest_highlights_flow(suggestions_setup) -> None:
    """Verify generating suggestions, accepting a suggestion into an annotation, and rejecting."""
    client, doc_id, text = suggestions_setup

    # 1. Generate suggestions
    res = client.post(f"/documents/{doc_id}/suggest-highlights")
    assert res.status_code == 200
    sugs = res.json()
    assert len(sugs) > 0
    sug = sugs[0]
    assert sug["status"] == "pending"
    assert sug["quote"] in text

    # 2. Accept the first suggestion
    acc_res = client.post(f"/suggestions/{sug['id']}/accept")
    assert acc_res.status_code == 200
    assert acc_res.json()["status"] == "accepted"

    # Verify that an annotation was created
    anns_res = client.get(f"/documents/{doc_id}/annotations")
    assert anns_res.status_code == 200
    anns = anns_res.json()
    assert len(anns) == 1
    assert anns[0]["quote"] == sug["quote"]

    # Verify idempotency of accept
    acc_again = client.post(f"/suggestions/{sug['id']}/accept")
    assert acc_again.status_code == 200
    anns_again = client.get(f"/documents/{doc_id}/annotations").json()
    assert len(anns_again) == 1

    # 3. Reject a suggestion if more than one exists
    if len(sugs) > 1:
        sug2 = sugs[1]
        rej_res = client.post(f"/suggestions/{sug2['id']}/reject")
        assert rej_res.status_code == 200
        assert rej_res.json()["status"] == "rejected"

        # Verify idempotency of reject
        rej_again = client.post(f"/suggestions/{sug2['id']}/reject")
        assert rej_again.status_code == 200
        assert rej_again.json()["status"] == "rejected"
