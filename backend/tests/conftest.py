"""Shared pytest fixtures for PostgreSQL + pgvector test environment."""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.db import init_db, normalize_database_url, reset_engine
import backend.app.db as app_db
from backend.app.settings import get_settings

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    os.environ.get("DATABASE_URL", "sqlite:///./backend/data/test_runner.db"),
)

os.environ["DATABASE_URL"] = normalize_database_url(TEST_DB_URL)
os.environ["EMBEDDING_MODEL_NAME"] = "fake"
get_settings.cache_clear()
reset_engine()


@pytest.fixture(scope="session")
def engine():
    """Session-scoped database engine with schema created once."""
    url = normalize_database_url(TEST_DB_URL)
    if "sqlite" in url:
        eng = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
        from sqlalchemy import event
        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            dbapi_connection.isolation_level = None
    else:
        eng = create_engine(url, pool_pre_ping=True)
    init_db(engine_override=eng)
    return eng


@pytest.fixture
def db_session(engine, monkeypatch):
    """Function-scoped session wrapped in a transaction that is rolled back."""
    connection = engine.connect()
    transaction = connection.begin()
    TestingSession = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")

    monkeypatch.setattr(app_db, "_SessionLocal", TestingSession)
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    get_settings.cache_clear()

    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        app_db.reset_engine()
        get_settings.cache_clear()
