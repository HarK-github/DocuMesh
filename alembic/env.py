"""Alembic environment configuration for DocuMesh migrations."""

import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure the repo root is importable so backend.app.* can be found
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load app settings for DATABASE_URL
from backend.app.settings import get_settings
from backend.app.models import Base  # noqa: F401 — import all models for autogenerate
from backend.app.db import normalize_database_url

settings = get_settings()

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Wire DATABASE_URL from settings into Alembic (overrides alembic.ini sqlalchemy.url)
config.set_main_option("sqlalchemy.url", normalize_database_url(settings.database_url))

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script output, no live DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
