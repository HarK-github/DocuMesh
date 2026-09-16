"""Background job execution manager with ThreadPoolExecutor."""

import uuid
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Optional
from sqlalchemy.orm import Session
from backend.app.settings import get_settings
from backend.app.db import get_session_factory
from backend.app.models import Job

_executor: Optional[ThreadPoolExecutor] = None


def get_executor() -> ThreadPoolExecutor:
    """Return shared background job thread pool executor."""
    global _executor
    if _executor is None:
        settings = get_settings()
        _executor = ThreadPoolExecutor(max_workers=settings.max_workers, thread_name_prefix="job_worker")
    return _executor


def create_job(db: Session, job_type: str, document_id: Optional[int] = None) -> Job:
    """Create and persist a new queued job."""
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        type=job_type,
        document_id=document_id,
        status="queued",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job_status(
    job_id: str,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    result: Optional[Any] = None,
    error: Optional[str] = None,
) -> None:
    """Update job progress, status, result, or error in a short-lived session."""
    session_factory = get_session_factory()
    with session_factory() as session:
        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = progress
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
        session.commit()


def _job_wrapper(job_id: str, func: Callable, *args: Any, **kwargs: Any) -> None:
    """Execute job function in background thread with status tracking."""
    update_job_status(job_id, status="running", progress=10)
    try:
        res = func(job_id, *args, **kwargs)
        update_job_status(job_id, status="done", progress=100, result=res)
    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}"
        update_job_status(job_id, status="failed", error=err_msg)


def submit_job(job_id: str, func: Callable, *args: Any, **kwargs: Any) -> None:
    """Submit task to the thread pool."""
    executor = get_executor()
    executor.submit(_job_wrapper, job_id, func, *args, **kwargs)


def cleanup_stale_jobs() -> None:
    """Mark jobs left in running or queued state on startup as failed."""
    session_factory = get_session_factory()
    with session_factory() as session:
        stale_jobs = session.query(Job).filter(Job.status.in_(["running", "queued"])).all()
        for job in stale_jobs:
            job.status = "failed"
            job.error = "Aborted due to server restart"
        session.commit()
