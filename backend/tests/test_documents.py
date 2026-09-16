"""Test document endpoints: upload, retrieval, clean text, deduplication, and limits."""

import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.main import create_app
from backend.app.db import get_db, init_db
from backend.app.settings import get_settings


@pytest.fixture
def client_and_db(tmp_path, monkeypatch):
    """Provide a TestClient connected to a temporary SQLite database and upload folder."""
    db_file = tmp_path / "test_docs.db"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("MAX_UPLOAD_MB", "2")
    monkeypatch.setenv("MAX_PDF_PAGES", "10")

    # Clear cached settings
    get_settings.cache_clear()

    engine = create_engine(f"sqlite:///{db_file}")
    init_db(engine_override=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client, TestingSessionLocal


def test_upload_and_get_document(client_and_db) -> None:
    """Verify upload, background processing, retrieval, and clean text."""
    client, _ = client_and_db
    sample_pdf = Path("sample/sample.pdf")

    with open(sample_pdf, "rb") as f:
        res = client.post(
            "/documents",
            files={"file": ("sample.pdf", f, "application/pdf")},
        )

    assert res.status_code == 200
    data = res.json()
    doc_id = data["document_id"]
    job_id = data["job_id"]
    assert doc_id > 0
    assert job_id is not None

    # Wait briefly for thread to finish processing
    for _ in range(20):
        time.sleep(0.1)
        doc_res = client.get(f"/documents/{doc_id}")
        if doc_res.json()["status"] == "ready":
            break

    doc_data = client.get(f"/documents/{doc_id}").json()
    assert doc_data["status"] == "ready"
    assert doc_data["filename"] == "sample.pdf"

    # Verify /documents/{id}/text
    text_res = client.get(f"/documents/{doc_id}/text")
    assert text_res.status_code == 200
    clean_text = text_res.json()["clean_text"]
    assert "COMPUTING MACHINERY AND INTELLIGENCE" in clean_text

    # Verify duplicate upload returns same document_id without re-processing
    with open(sample_pdf, "rb") as f:
        dup_res = client.post(
            "/documents",
            files={"file": ("sample.pdf", f, "application/pdf")},
        )
    assert dup_res.status_code == 200
    assert dup_res.json()["document_id"] == doc_id
    assert dup_res.json()["job_id"] is None


def test_get_document_404(client_and_db) -> None:
    """Verify 404 for nonexistent document."""
    client, _ = client_and_db
    res = client.get("/documents/99999")
    assert res.status_code == 404
    text_res = client.get("/documents/99999/text")
    assert text_res.status_code == 404


def test_upload_file_size_limit_rejection(client_and_db) -> None:
    """Verify that file exceeding max_upload_mb is rejected with 422."""
    client, _ = client_and_db
    large_content = b"%PDF-1.4 " + (b"0" * (3 * 1024 * 1024))
    res = client.post(
        "/documents",
        files={"file": ("too_big.pdf", large_content, "application/pdf")},
    )
    assert res.status_code == 422
    assert "exceeds maximum allowed size" in res.json()["detail"]


def test_get_job_status_and_404(client_and_db) -> None:
    """Verify job lookup and 404 response."""
    client, _ = client_and_db
    sample_pdf = Path("sample/sample.pdf")
    with open(sample_pdf, "rb") as f:
        res = client.post("/documents", files={"file": ("sample.pdf", f, "application/pdf")})
    job_id = res.json()["job_id"]

    job_res = client.get(f"/jobs/{job_id}")
    assert job_res.status_code == 200
    assert job_res.json()["id"] == job_id

    missing_job = client.get("/jobs/nonexistent-job-uuid")
    assert missing_job.status_code == 404
