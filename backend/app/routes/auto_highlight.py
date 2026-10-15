"""Endpoints for automated full-document highlight and knowledge graph extraction."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.models import Document
from backend.app.schemas import JobResponse, AutoHighlightRequest
from backend.app.services.jobs import create_job, submit_job
from backend.app.services.auto_highlighter import process_auto_highlight_job

router = APIRouter(tags=["Auto Highlight"])


@router.post(
    "/documents/{document_id}/auto-highlight",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def auto_highlight_document(
    document_id: int,
    payload: Optional[AutoHighlightRequest] = None,
    db: Session = Depends(get_db),
) -> JobResponse:
    """Initiate top-down sequential auto-highlighting and graph construction for the entire PDF."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status != "ready" or not doc.clean_text:
        raise HTTPException(
            status_code=422,
            detail="Document text is not yet processed or ready for auto-highlighting",
        )

    mode = payload.mode if (payload and payload.mode) else "llm"

    job = create_job(db, job_type="auto_highlight", document_id=document_id)
    submit_job(job.id, process_auto_highlight_job, document_id, mode)
    return job

