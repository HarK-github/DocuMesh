"""Test database initialization and taxonomy seeding."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.db import init_db
from backend.app.models import Label, RelationType, Document


def test_init_db_creates_tables_and_seeds(tmp_path) -> None:
    """Verify schema creation and taxonomy seeding in a temporary SQLite DB."""
    db_file = tmp_path / "test.db"
    test_url = f"sqlite:///{db_file}"
    engine = create_engine(test_url)

    init_db(engine_override=engine)

    Session = sessionmaker(bind=engine)
    with Session() as session:
        # Check taxonomy seeded
        labels = session.query(Label).all()
        assert len(labels) > 0
        label_names = [l.name for l in labels]
        assert "Claim" in label_names
        assert "Evidence" in label_names

        rel_types = session.query(RelationType).all()
        assert len(rel_types) > 0
        rel_names = [r.name for r in rel_types]
        assert "supports" in rel_names

        # Check document table exists and is queryable
        docs = session.query(Document).all()
        assert len(docs) == 0
