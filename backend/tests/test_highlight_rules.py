"""Test highlight rules: boundary snapping, duplicates, overlaps, stale PATCH, and superseded suggestions."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import create_app
from backend.app.db import get_db, init_db
from backend.app.models import Document, Sentence, Suggestion, Annotation
from backend.app.services.clean import snap_to_word_boundaries


def test_snap_to_word_boundaries_cases() -> None:
    """Verify word boundary snapping for mid-word start, mid-word end, and existing boundaries."""
    text = "The quick brown fox jumps"
    # Word ranges:
    # "The": [0, 3]
    # "quick": [4, 9]
    # "brown": [10, 15]
    # "fox": [16, 19]
    # "jumps": [20, 25]

    # Mid-word start: user dragged starting at index 6 in 'quick' to index 15
    s, e = snap_to_word_boundaries(text, 6, 15)
    assert (s, e) == (4, 15)
    assert text[s:e] == "quick brown"

    # Mid-word end: user dragged from index 4 to index 13 ('bro' in 'brown')
    s, e = snap_to_word_boundaries(text, 4, 13)
    assert (s, e) == (4, 15)
    assert text[s:e] == "quick brown"

    # Already on boundaries
    s, e = snap_to_word_boundaries(text, 4, 15)
    assert (s, e) == (4, 15)
    assert text[s:e] == "quick brown"

    # Surrounding whitespace
    s, e = snap_to_word_boundaries(text, 3, 16)
    assert (s, e) == (4, 15)


@pytest.fixture
def setup_db(tmp_path, monkeypatch):
    """Provide TestClient with temporary DB, seeded taxonomy, and a sample document with clean_text."""
    db_file = tmp_path / "test_highlight.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("DB_PATH", str(db_file))

    engine = create_engine(f"sqlite:///{db_file}")
    init_db(engine_override=engine)
    TestingSession = sessionmaker(bind=engine)

    sample_text = "The quick brown fox jumps over the lazy dog."
    with TestingSession() as session:
        doc = Document(
            filename="quick_fox.pdf",
            file_hash="hash_fox_123",
            status="ready",
            clean_text=sample_text,
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

        # Add a sentence and a pending suggestion over 'brown fox jumps' (indices 10 to 25)
        sent = Sentence(
            document_id=doc_id,
            idx=0,
            start=10,
            end=25,
            page=1,
        )
        session.add(sent)
        session.commit()

        sug = Suggestion(
            document_id=doc_id,
            sentence_id=sent.id,
            score=0.92,
            status="pending",
        )
        session.add(sug)
        session.commit()
        sug_id = sug.id

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, doc_id, sug_id, TestingSession


def test_duplicate_returns_existing_annotation(setup_db) -> None:
    """Creating duplicate annotation returns existing record with HTTP 200."""
    client, doc_id, _, _ = setup_db

    payload = {
        "start": 4,
        "end": 9,
        "quote": "quick",
        "label": "Claim",
        "note": "First creation",
    }
    res1 = client.post(f"/documents/{doc_id}/annotations", json=payload)
    assert res1.status_code == 201
    ann1 = res1.json()

    # Create same (document_id, start, end, label)
    res2 = client.post(f"/documents/{doc_id}/annotations", json=payload)
    assert res2.status_code == 200
    ann2 = res2.json()
    assert ann2["id"] == ann1["id"]
    assert ann2["note"] == "First creation"


def test_overlapping_annotations_accepted(setup_db) -> None:
    """Overlapping ranges and same range with different label are both accepted."""
    client, doc_id, _, _ = setup_db

    # Annotation 1: 'quick brown' (4 to 15), label Claim
    res1 = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": 4, "end": 15, "quote": "quick brown", "label": "Claim"},
    )
    assert res1.status_code == 201
    ann1 = res1.json()

    # Annotation 2: same range (4 to 15), different label Evidence
    res2 = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": 4, "end": 15, "quote": "quick brown", "label": "Evidence"},
    )
    assert res2.status_code == 201
    ann2 = res2.json()
    assert ann2["id"] != ann1["id"]
    assert ann2["label"] == "Evidence"

    # Annotation 3: partial overlap 'brown fox' (10 to 19), label Definition
    res3 = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": 10, "end": 19, "quote": "brown fox", "label": "Definition"},
    )
    assert res3.status_code == 201


def test_stale_patch_returns_409(setup_db) -> None:
    """Stale version in PATCH /annotations/{id} returns 409 Conflict."""
    client, doc_id, _, _ = setup_db

    res = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": 0, "end": 3, "quote": "The", "label": "Claim"},
    )
    assert res.status_code == 201
    ann = res.json()
    ann_id = ann["id"]

    # First update increments version
    res_update = client.patch(
        f"/annotations/{ann_id}",
        json={"note": "Updated note", "version": ann["version"]},
    )
    assert res_update.status_code == 200
    updated = res_update.json()
    assert updated["version"] == ann["version"] + 1

    # Stale update with old version returns 409
    res_stale = client.patch(
        f"/annotations/{ann_id}",
        json={"note": "Stale edit attempt", "version": ann["version"]},
    )
    assert res_stale.status_code == 409
    assert "stale" in res_stale.json()["detail"].lower()


def test_superseded_suggestion_no_longer_appears_as_pending(setup_db) -> None:
    """When an annotation is created over a pending suggestion's range, suggestion is superseded."""
    client, doc_id, sug_id, SessionFactory = setup_db

    # Verify suggestion is initially pending
    pending_res = client.get(f"/documents/{doc_id}/suggestions?status=pending")
    assert pending_res.status_code == 200
    assert any(s["id"] == sug_id for s in pending_res.json())

    # Create annotation over indices 10 to 25 ('brown fox jumps')
    ann_res = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": 10, "end": 25, "quote": "brown fox jumps", "label": "Claim"},
    )
    assert ann_res.status_code == 201

    # In database, suggestion status is superseded
    with SessionFactory() as session:
        sug = session.query(Suggestion).filter(Suggestion.id == sug_id).first()
        assert sug.status == "superseded"

    # Check pending suggestions list excludes superseded
    pending_after = client.get(f"/documents/{doc_id}/suggestions?status=pending")
    assert pending_after.status_code == 200
    assert not any(s["id"] == sug_id for s in pending_after.json())
