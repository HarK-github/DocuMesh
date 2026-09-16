"""Document management and upload endpoints."""

import hashlib
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from backend.app.settings import get_settings
from backend.app.db import get_db
from backend.app.models import Document
from backend.app.schemas import (
    DocumentResponse,
    DocumentUploadResponse,
    DocumentTextResponse,
)
from backend.app.services.extract import get_pdf_page_count
from backend.app.services.jobs import create_job, submit_job
from backend.app.services.ingest import process_document

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload a PDF, validate constraints, and initiate background ingestion."""
    settings = get_settings()
    content = await file.read()

    # 1. Size limit validation
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds maximum allowed size of {settings.max_upload_mb}MB",
        )

    # 2. PDF page count validation
    try:
        page_count = get_pdf_page_count(content)
        if page_count > settings.max_pdf_pages:
            raise HTTPException(
                status_code=422,
                detail=f"PDF page count ({page_count}) exceeds limit of {settings.max_pdf_pages}",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid PDF file: {str(exc)}")

    # 3. Deduplication via SHA-256 hash
    file_hash = hashlib.sha256(content).hexdigest()
    existing = db.query(Document).filter(Document.file_hash == file_hash).first()
    if existing:
        return DocumentUploadResponse(
            document_id=existing.id,
            job_id=None,
            status=existing.status,
            filename=existing.filename,
        )

    # 4. Save file to disk
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / f"{file_hash}.pdf"
    with open(saved_path, "wb") as f:
        f.write(content)

    # 5. Create document and background job
    doc = Document(
        filename=file.filename or "document.pdf",
        file_hash=file_hash,
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    job = create_job(db, job_type="ingestion", document_id=doc.id)
    submit_job(job.id, process_document, doc.id, str(saved_path))

    return DocumentUploadResponse(
        document_id=doc.id,
        job_id=job.id,
        status=doc.status,
        filename=doc.filename,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)) -> DocumentResponse:
    """Retrieve document metadata by ID."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{document_id}/text", response_model=DocumentTextResponse)
def get_document_text(document_id: int, db: Session = Depends(get_db)) -> DocumentTextResponse:
    """Retrieve clean segmented text for an ingested document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentTextResponse(
        id=doc.id,
        filename=doc.filename,
        clean_text=doc.clean_text,
    )


@router.get("/{document_id}/pdf")
def get_document_pdf(document_id: int, db: Session = Depends(get_db)):
    """Serve the raw PDF file for rendering in the browser PDF viewer."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    settings = get_settings()
    pdf_path = Path(settings.upload_dir) / f"{doc.file_hash}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=doc.filename,
    )
