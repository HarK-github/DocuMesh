"""Tests for full-document auto-highlight and knowledge graph construction."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import create_app
from backend.app.db import get_db, init_db, reset_engine
from backend.app.settings import get_settings
from backend.app.models import Document, Sentence, Annotation, Relation, Job
from backend.app.services.auto_highlighter import process_auto_highlight_job


@pytest.fixture
def auto_highlight_setup(tmp_path, monkeypatch):
    """Provide TestClient with temporary DB, seeded taxonomy, and sample document with sentences."""
    db_file = tmp_path / "test_auto_highlight.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "fake")
    monkeypatch.setenv("SIMILARITY_THRESHOLD", "0.0")

    get_settings.cache_clear()
    reset_engine()

    engine = create_engine(f"sqlite:///{db_file}")
    init_db(engine_override=engine)
    TestingSession = sessionmaker(bind=engine)

    sample_text = (
        "Can machines think? "
        "We claim that digital computers can simulate human intelligence. "
        "The imitation game provides empirical evidence for this hypothesis. "
        "Digital computers are defined as discrete-state electronic systems. "
        "Our method executes iterative computational simulations across states. "
        "The experimental results demonstrate ninety percent accuracy in trials. "
        "The proposed architecture solves the fundamental intelligence challenge."
    )

    with TestingSession() as session:
        doc = Document(
            filename="turing_auto.pdf",
            file_hash="hash_auto_12345",
            status="ready",
            clean_text=sample_text,
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

        # Add sentences
        sentences_text = [
            "Can machines think?",
            "We claim that digital computers can simulate human intelligence.",
            "The imitation game provides empirical evidence for this hypothesis.",
            "Digital computers are defined as discrete-state electronic systems.",
            "Our method executes iterative computational simulations across states.",
            "The experimental results demonstrate ninety percent accuracy in trials.",
            "The proposed architecture solves the fundamental intelligence challenge.",
        ]

        curr = 0
        for idx, s_str in enumerate(sentences_text):
            start = sample_text.index(s_str, curr)
            end = start + len(s_str)
            curr = end
            sent = Sentence(
                document_id=doc_id,
                idx=idx,
                start=start,
                end=end,
                page=1,
            )
            session.add(sent)
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
        yield client, doc_id, sample_text, TestingSession


def test_auto_highlight_endpoint_validation(auto_highlight_setup) -> None:
    """Verify endpoint rejects missing document and unready documents."""
    client, doc_id, _, TestingSession = auto_highlight_setup

    # Non-existent doc
    res = client.post("/documents/9999/auto-highlight", json={"mode": "llm"})
    assert res.status_code == 404

    # Processing doc (not ready)
    with TestingSession() as session:
        unready = Document(filename="unready.pdf", file_hash="unready_123", status="processing")
        session.add(unready)
        session.commit()
        unready_id = unready.id

    res2 = client.post(f"/documents/{unready_id}/auto-highlight", json={"mode": "llm"})
    assert res2.status_code == 422


def test_auto_highlight_execution_and_full_graph_construction(auto_highlight_setup) -> None:
    """Verify that process_auto_highlight_job runs Phase A (annotations) and Phase B (graph relations)."""
    _, doc_id, _, TestingSession = auto_highlight_setup

    # Create job record
    with TestingSession() as session:
        job = Job(id="job_auto_test_1", type="auto_highlight", document_id=doc_id, status="queued")
        session.add(job)
        session.commit()

    result = process_auto_highlight_job(
        job_id="job_auto_test_1",
        document_id=doc_id,
        mode="llm",
    )

    assert result["annotations_created"] > 0
    assert result["relations_created"] >= 0

    with TestingSession() as session:
        # Check job completion
        j = session.query(Job).filter(Job.id == "job_auto_test_1").first()
        assert j.status == "done"
        assert j.progress == 100

        # Check annotations created in sequential order with confirmed status
        anns = session.query(Annotation).filter(Annotation.document_id == doc_id).all()
        assert len(anns) == result["annotations_created"]
        for a in anns:
            assert a.note == "Auto-highlighted"
            assert a.start < a.end
            assert len(a.quote) > 0

        # Check relations created with confirmed status
        rels = session.query(Relation).filter(Relation.document_id == doc_id).all()
        for r in rels:
            assert r.status == "confirmed"
            assert r.source_id != r.target_id


def test_auto_highlight_skips_covered_ranges(auto_highlight_setup) -> None:
    """Verify auto-highlight does not re-annotate ranges already covered by manual annotations."""
    _, doc_id, sample_text, TestingSession = auto_highlight_setup

    # Pre-add manual annotation covering the first sentence
    q = "Can machines think?"
    s = sample_text.index(q)
    e = s + len(q)
    with TestingSession() as session:
        manual_ann = Annotation(
            document_id=doc_id,
            start=s,
            end=e,
            quote=q,
            label="Problem",
            note="Manual annotation",
            version=1,
        )
        session.add(manual_ann)
        session.commit()

    with TestingSession() as session:
        job = Job(id="job_auto_test_2", type="auto_highlight", document_id=doc_id, status="queued")
        session.add(job)
        session.commit()

    result = process_auto_highlight_job(
        job_id="job_auto_test_2",
        document_id=doc_id,
        mode="llm",
    )

    with TestingSession() as session:
        # Check that the manual annotation remains untouched
        man = session.query(Annotation).filter(Annotation.note == "Manual annotation").first()
        assert man is not None
        assert man.quote == q

        # No duplicate annotation was created over the first sentence
        first_sentence_anns = (
            session.query(Annotation)
            .filter(Annotation.document_id == doc_id, Annotation.start == s, Annotation.end == e)
            .all()
        )
        assert len(first_sentence_anns) == 1


def test_auto_highlight_embedding_fallback_mode(auto_highlight_setup) -> None:
    """Verify auto-highlight works in mode='embedding' without LLM."""
    _, doc_id, _, TestingSession = auto_highlight_setup

    with TestingSession() as session:
        job = Job(id="job_auto_test_3", type="auto_highlight", document_id=doc_id, status="queued")
        session.add(job)
        session.commit()

    result = process_auto_highlight_job(
        job_id="job_auto_test_3",
        document_id=doc_id,
        mode="embedding",
    )

    assert result["annotations_created"] > 0
    assert result["mode"] == "embedding"

    with TestingSession() as session:
        j = session.query(Job).filter(Job.id == "job_auto_test_3").first()
        assert j.status == "done"

