"""Database engine, session management, and schema initialization."""

import json
import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from backend.app.settings import get_settings
from backend.app.models import Base, Label, RelationType

_engine = None
_SessionLocal = None


def reset_engine() -> None:
    """Reset cached engine and session factory (useful for tests)."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


def get_engine(database_url: str = None):
    """Create or return SQLAlchemy engine configured for SQLite WAL safety."""
    global _engine, _SessionLocal
    settings = get_settings()
    url = database_url or settings.database_url

    if database_url is None and _engine is not None and str(_engine.url) == url:
        return _engine

    # Ensure parent directory exists for file-based SQLite
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        db_file = url.replace("sqlite:///", "")
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)

    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(url, connect_args=connect_args)

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms};")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

    if database_url is None:
        _engine = engine
        _SessionLocal = None
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


def seed_taxonomy(db: Session, config_path: str = None) -> None:
    """Seed taxonomy labels and relation types from config/taxonomy.json."""
    if config_path is None:
        # Resolve config/taxonomy.json relative to repo root
        repo_root = Path(__file__).resolve().parent.parent.parent
        config_path = str(repo_root / "config" / "taxonomy.json")

    if not os.path.exists(config_path):
        return

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    labels = data.get("labels", [])
    for label_name in labels:
        if not db.query(Label).filter(Label.name == label_name).first():
            db.add(Label(name=label_name))

    relation_types = data.get("relation_types", [])
    for rel_name in relation_types:
        if not db.query(RelationType).filter(RelationType.name == rel_name).first():
            db.add(RelationType(name=rel_name))

    db.commit()


def init_db(engine_override=None, config_path: str = None) -> None:
    """Create all database tables and seed taxonomy."""
    target_engine = engine_override or get_engine()
    Base.metadata.create_all(bind=target_engine)

    session_factory = get_session_factory(target_engine)
    with session_factory() as session:
        seed_taxonomy(session, config_path=config_path)
