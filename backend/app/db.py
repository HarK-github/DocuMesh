"""Database engine, session management, and schema initialization (PostgreSQL + pgvector)."""

from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from backend.app.settings import get_settings
from backend.app.models import Base

_engine = None
_SessionLocal = None


def reset_engine() -> None:
    """Reset cached engine and session factory (useful for tests)."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


def normalize_database_url(url: str) -> str:
    """Normalize PostgreSQL URLs for SQLAlchemy and psycopg2 driver compatibility.

    Render and older configs provide postgres://, and generic configs provide postgresql://,
    which in SQLAlchemy 2.0+ default to the psycopg3 driver. This normalizes both to postgresql+psycopg2://.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def get_engine(database_url: str = None):
    """Create or return a pooled PostgreSQL SQLAlchemy engine."""
    global _engine, _SessionLocal
    settings = get_settings()
    raw_url = database_url or settings.database_url
    url = normalize_database_url(raw_url)

    if database_url is None and _engine is not None and str(_engine.url) == url:
        return _engine

    engine_kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs["pool_size"] = settings.db_pool_size
        engine_kwargs["max_overflow"] = settings.db_max_overflow

    engine = create_engine(url, **engine_kwargs)

    if database_url is None:
        _engine = engine
    return engine


def get_session_factory(engine=None):
    """Return sessionmaker bound to the engine."""
    global _SessionLocal
    if engine is None and _SessionLocal is not None:
        return _SessionLocal

    target_engine = engine or get_engine()
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=target_engine)

    if engine is None:
        _SessionLocal = session_factory
    return session_factory


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a short-lived database session."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def init_db(engine_override=None) -> None:
    """Ensure vector extension is loaded and create all database tables."""
    target_engine = engine_override or get_engine()
    if not str(target_engine.url).startswith("sqlite"):
        with target_engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
    Base.metadata.create_all(bind=target_engine)

    # Safe migration for existing SQLite databases
    if str(target_engine.url).startswith("sqlite"):
        with target_engine.connect() as conn:
            for col_stmt in [
                "ALTER TABLE chunks ADD COLUMN page INTEGER DEFAULT 1;",
                "ALTER TABLE chunks ADD COLUMN text TEXT;",
            ]:
                try:
                    conn.execute(text(col_stmt))
                    conn.commit()
                except Exception:
                    pass


