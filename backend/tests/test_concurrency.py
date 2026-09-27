"""Concurrency and stress tests: 20 parallel creates, stale edits, simultaneous uploads, and job cleanup."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.main import create_app
from backend.app.db import get_db, init_db, reset_engine
from backend.app.models import Document, Annotation, Job
from backend.app.services.jobs import cleanup_stale_jobs, create_job, update_job_status
from backend.app.settings import get_settings


@pytest.fixture
def concurrency_env(tmp_path, monkeypatch):
    """Set up temporary database for concurrency tests."""
    db_file = tmp_path / "test_concurrency.db"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "fake")
    monkeypatch.setenv("SQLITE_BUSY_TIMEOUT_MS", "10000")

    get_settings.cache_clear()
    reset_engine()

    engine = create_engine(f"sqlite:///{db_file}")
    init_db(engine_override=engine)
    TestingSession = sessionmaker(bind=engine)

    # Insert document with 20 distinct sentences
    sentences = [f"Sentence number {i} is here." for i in range(25)]
    text = " ".join(sentences)

    with TestingSession() as s:
        doc = Document(filename="concurrency.pdf", file_hash="hash_conc_1", status="ready", clean_text=text)
        s.add(doc)
        s.commit()
        doc_id = doc.id

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, doc_id, text, sentences, TestingSession


def test_twenty_parallel_annotation_creates(concurrency_env) -> None:
    """Verify 20 parallel annotation creates without lost writes or SQLite lock errors."""
    client, doc_id, text, sentences, SessionFactory = concurrency_env

    def create_one(i: int):
        quote = sentences[i]
        start = text.index(quote)
        end = start + len(quote)
        return client.post(
            f"/documents/{doc_id}/annotations",
            json={
                "start": start,
                "end": end,
                "quote": quote,
                "label": "Claim",
                "note": f"Parallel item {i}",
            },
        )

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_one, i) for i in range(20)]
        results = [f.result() for f in futures]

    # Every request must succeed with 201
    status_codes = [r.status_code for r in results]
    assert status_codes == [201] * 20

    # Verify all 20 records persisted
    with SessionFactory() as session:
        count = session.query(Annotation).filter(Annotation.document_id == doc_id).count()
        assert count == 20


def test_stale_patch_conflict_409(concurrency_env) -> None:
    """Verify 409 conflict returned when updating an out-of-date annotation version."""
    client, doc_id, text, sentences, _ = concurrency_env
    quote = sentences[0]
    start = text.index(quote)
    end = start + len(quote)

    ann = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": start, "end": end, "quote": quote, "label": "Claim"},
    ).json()

    # Worker 1 updates annotation, bumping version to 2
    res1 = client.patch(f"/annotations/{ann['id']}", json={"note": "Update 1", "version": 1})
    assert res1.status_code == 200
    assert res1.json()["version"] == 2

    # Worker 2 attempts update with old version 1 -> must return 409
    res2 = client.patch(f"/annotations/{ann['id']}", json={"note": "Update 2", "version": 1})
    assert res2.status_code == 409
    assert "Stale edit" in res2.json()["detail"]


def test_simultaneous_duplicate_uploads(concurrency_env) -> None:
    """Verify two simultaneous uploads of the same PDF produce exactly one document."""
    client, _, _, _, SessionFactory = concurrency_env
    sample_pdf = Path("sample/sample.pdf")
    with open(sample_pdf, "rb") as f:
        pdf_bytes = f.read()

    def upload():
        return client.post(
            "/documents",
            files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(upload)
        f2 = executor.submit(upload)
        r1 = f1.result()
        r2 = f2.result()

    assert r1.status_code == 200
    assert r2.status_code == 200

    # Both must reference the exact same document ID
    assert r1.json()["document_id"] == r2.json()["document_id"]


def test_job_cleanup_on_startup(concurrency_env) -> None:
    """Verify that jobs left in running or queued status are marked failed on startup."""
    _, _, _, _, SessionFactory = concurrency_env

    with SessionFactory() as session:
        j1 = create_job(session, "test_job")
        j1_id = str(j1.id)
        update_job_status(j1_id, status="running")
        j2 = create_job(session, "test_job_2")
        j2_id = str(j2.id)

    cleanup_stale_jobs()

    with SessionFactory() as session:
        job1 = session.query(Job).filter(Job.id == j1_id).first()
        job2 = session.query(Job).filter(Job.id == j2_id).first()
        assert job1.status == "failed"
        assert "server restart" in job1.error
        assert job2.status == "failed"
