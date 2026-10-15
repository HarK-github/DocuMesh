"""Test database initialization and static taxonomy configuration."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.db import init_db
from backend.app.models import Document, Annotation, Relation, Sentence
from backend.app.taxonomy import (
    TAXONOMY_LABELS,
    TAXONOMY_RELATION_TYPES,
    is_valid_label,
    is_valid_relation_type,
)


def test_init_db_creates_tables(tmp_path) -> None:
    """Verify schema creation in a temporary SQLite DB."""
    db_file = tmp_path / "test.db"
    test_url = f"sqlite:///{db_file}"
    engine = create_engine(test_url)

    init_db(engine_override=engine)

    Session = sessionmaker(bind=engine)
    with Session() as session:
        # Check tables exist and are queryable
        assert session.query(Document).count() == 0
        assert session.query(Sentence).count() == 0
        assert session.query(Annotation).count() == 0
        assert session.query(Relation).count() == 0


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

