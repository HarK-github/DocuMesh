"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import List, Union
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for backend services and storage."""

    # Storage and database
    database_url: str = Field(
        default="sqlite:///./data/app.db",
        alias="DATABASE_URL",
        description="SQLAlchemy database connection string",
    )
    db_path: str = Field(
        default="./data/app.db",
        alias="DB_PATH",
        description="Path to SQLite database file",
    )
    upload_dir: str = Field(
        default="./uploads",
        alias="UPLOAD_DIR",
        description="Directory for uploaded PDF files",
    )
    sqlite_busy_timeout_ms: int = Field(
        default=5000,
        alias="SQLITE_BUSY_TIMEOUT_MS",
        description="Busy timeout in ms for SQLite WAL concurrency",
    )

    # Ingestion limits
    max_upload_mb: int = Field(
        default=15,
        alias="MAX_UPLOAD_MB",
        description="Max permitted PDF file size in MB",
    )
    max_pdf_pages: int = Field(
        default=50,
        alias="MAX_PDF_PAGES",
        description="Max permitted pages per uploaded PDF",
    )

    # Embeddings and smart suggestions
    embedding_model_name: str = Field(
        default="all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL_NAME",
        description="Sentence-transformers model identifier",
    )
    embed_batch_size: int = Field(
        default=32,
        alias="EMBED_BATCH_SIZE",
        description="Batch size for embedding sentence chunks",
    )
    suggestion_count: int = Field(
        default=5,
        alias="SUGGESTION_COUNT",
        description="Max number of highlight suggestions returned",
    )
    similarity_threshold: float = Field(
        default=0.35,
        alias="SIMILARITY_THRESHOLD",
        description="Cosine similarity threshold for suggestions",
    )

    # LLM configuration (suggested relations)
    llm_provider: str = Field(
        default="fake",
        alias="LLM_PROVIDER",
        description="LLM provider: fake, openai",
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        alias="LLM_MODEL",
        description="Model name for relation extraction",
    )
    llm_api_key: str = Field(
        default="",
        alias="LLM_API_KEY",
        description="API key for chosen LLM provider",
    )
    llm_max_concurrency: int = Field(
        default=3,
        alias="LLM_MAX_CONCURRENCY",
        description="Max concurrent LLM API requests via semaphore",
    )
    llm_timeout_seconds: float = Field(
        default=30.0,
        alias="LLM_TIMEOUT_SECONDS",
        description="Timeout per LLM request in seconds",
    )
    max_relation_pairs: int = Field(
        default=10,
        alias="MAX_RELATION_PAIRS",
        description="Cap on annotation pairs checked per relation suggestion run",
    )

    # Threading and concurrency
    max_workers: int = Field(
        default=4,
        alias="MAX_WORKERS",
        description="Worker thread count for background job executor",
    )

    # CORS configuration
    cors_origins: Union[List[str], str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        alias="CORS_ORIGINS",
        description="Allowed CORS origin patterns",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
