"""Test database initialization and static taxonomy configuration."""

from sqlalchemy.orm import sessionmaker
from backend.app.db import init_db
from backend.app.models import Document, Annotation, Relation, Sentence
from backend.app.taxonomy import (
    TAXONOMY_LABELS,
    TAXONOMY_RELATION_TYPES,
    is_valid_label,
    is_valid_relation_type,
)


def test_init_db_creates_tables(engine) -> None:
    """Verify schema creation in PostgreSQL."""
    init_db(engine_override=engine)

    Session = sessionmaker(bind=engine)
    with Session() as session:
        # Check tables exist and are queryable
        assert session.query(Document).filter(Document.id == -999).count() == 0
        assert session.query(Sentence).filter(Sentence.id == -999).count() == 0
        assert session.query(Annotation).filter(Annotation.id == -999).count() == 0
        assert session.query(Relation).filter(Relation.id == -999).count() == 0


def test_taxonomy_configuration() -> None:
    """Verify static taxonomy labels and relation types."""
    assert "Claim" in TAXONOMY_LABELS
    assert "Evidence" in TAXONOMY_LABELS
    assert "supports" in TAXONOMY_RELATION_TYPES
    assert "refutes" in TAXONOMY_RELATION_TYPES

    assert is_valid_label("Claim") is True
    assert is_valid_label("InvalidLabel") is False
    assert is_valid_relation_type("supports") is True
    assert is_valid_relation_type("invalid_rel") is False


def test_postgres_engine_pool_configuration(monkeypatch) -> None:
    """Verify that PostgreSQL engine is initialized with connection pool and pre-ping."""
    from backend.app.db import get_engine, reset_engine
    from backend.app.settings import get_settings

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@localhost:5432/documesh")
    monkeypatch.setenv("DB_POOL_SIZE", "7")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "15")

    get_settings.cache_clear()
    reset_engine()

    engine = get_engine()
    try:
        assert engine.pool._pre_ping is True
        assert engine.pool.size() == 7
        assert engine.pool._max_overflow == 15
    finally:
        reset_engine()
        get_settings.cache_clear()


def test_normalize_database_url() -> None:
    """Verify that postgres:// and postgresql:// are normalized to postgresql+psycopg2://."""
    from backend.app.db import normalize_database_url

    assert normalize_database_url("postgres://u:p@localhost/db") == "postgresql+psycopg2://u:p@localhost/db"
    assert normalize_database_url("postgresql://u:p@localhost/db") == "postgresql+psycopg2://u:p@localhost/db"
    assert normalize_database_url("postgresql+psycopg2://u:p@localhost/db") == "postgresql+psycopg2://u:p@localhost/db"
