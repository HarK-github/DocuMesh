"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import List, Union
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for backend services and storage (PostgreSQL)."""

    # Storage and database
    database_url: str = Field(
        default="postgresql://user:password@localhost:5432/documesh",
        alias="DATABASE_URL",
        description="SQLAlchemy PostgreSQL connection string",
    )
    upload_dir: str = Field(
        default="./uploads",
        alias="UPLOAD_DIR",
        description="Directory for uploaded PDF files",
    )
    db_pool_size: int = Field(
        default=5,
        alias="DB_POOL_SIZE",
        description="PostgreSQL connection pool size",
    )
    db_max_overflow: int = Field(
        default=10,
        alias="DB_MAX_OVERFLOW",
        description="PostgreSQL max overflow connections above pool_size",
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
    candidate_pool_size: int = Field(
        default=30,
        alias="CANDIDATE_POOL_SIZE",
        description="Candidate pool size retrieved from vector store",
    )
    neg_weight: float = Field(
        default=0.5,
        alias="NEG_WEIGHT",
        description="Negative penalty weight for rejected suggestions",
    )
    mmr_lambda: float = Field(
        default=0.7,
        alias="MMR_LAMBDA",
        description="MMR diversity trade-off parameter between 0 and 1",
    )
    max_pending_per_seed: int = Field(
        default=10,
        alias="MAX_PENDING_PER_SEED",
        description="Maximum pending suggestions allowed per seed annotation",
    )

    # LLM configuration (suggested relations & document chat)
    llm_provider: str = Field(
        default="fake",
        alias="LLM_PROVIDER",
        description="LLM provider: fake, openai, huggingface, openrouter",
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        alias="LLM_MODEL",
        description="Model name for relation extraction & chat",
    )
    llm_api_key: str = Field(
        default="",
        alias="LLM_API_KEY",
        description="API key for chosen LLM provider",
    )
    openrouter_key: str = Field(
        default="",
        alias="OPENROUTER_KEY",
        description="OpenRouter API key for LLM chat and relation suggestion",
    )
    openrouter_endpoint: str = Field(
        default="https://openrouter.ai/api/v1/chat/completions",
        alias="OPENROUTER_ENDPOINT",
        description="OpenRouter chat completions API endpoint",
    )
    hf_token: str = Field(
        default="",
        alias="HF_TOKEN",
        description="Hugging Face user access token for serverless inference",
    )
    hf_endpoint: str = Field(
        default="https://router.huggingface.co/hf-inference/v1/chat/completions",
        alias="HF_ENDPOINT",
        description="OpenAI-compatible router endpoint for Hugging Face inference",
    )
    hf_provider: str = Field(
        default="",
        alias="HF_PROVIDER",
        description="Provider identifier for Hugging Face serverless inference (empty for default HF serverless)",
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
    min_relation_cos_sim: float = Field(
        default=0.40,
        alias="MIN_RELATION_COS_SIM",
        description="Minimum cosine similarity floor for candidate relation pairs (0.40 empirically separates semantic links from noise)",
    )
    chunk_target_tokens: int = Field(
        default=250,
        alias="CHUNK_TARGET_TOKENS",
        description="Target BPE token size per lexical chunk (aligned with 256-token sentence-transformers capacity)",
    )
    chunk_overlap_tokens: int = Field(
        default=50,
        alias="CHUNK_OVERLAP_TOKENS",
        description="Overlap BPE tokens between consecutive lexical chunks (~20% overlap prevents boundary loss)",
    )
    chat_top_k_chunks: int = Field(
        default=4,
        alias="CHAT_TOP_K_CHUNKS",
        description="Top lexical chunks retrieved for grounding chat questions",
    )
    auto_highlight_batch_size: int = Field(
        default=20,
        alias="AUTO_HIGHLIGHT_BATCH_SIZE",
        description="Batch size for sequential sentence classification in auto-highlight",
    )
    auto_highlight_max_pairs: int = Field(
        default=100,
        alias="AUTO_HIGHLIGHT_MAX_PAIRS",
        description="Cap on annotation pairs evaluated for full graph construction in auto-highlight",
    )
    auto_highlight_proto_threshold: float = Field(
        default=0.18,
        alias="AUTO_HIGHLIGHT_PROTO_THRESHOLD",
        description="Cosine similarity floor for prototype sentence classification in auto-highlight",
    )

    # Graph-aware document chat settings
    chat_top_k_sentences: int = Field(
        default=5,
        alias="CHAT_TOP_K_SENTENCES",
        description="Top sentence count to retrieve for document chat",
    )
    chat_top_k_annotations: int = Field(
        default=5,
        alias="CHAT_TOP_K_ANNOTATIONS",
        description="Top annotation count to retrieve for document chat",
    )
    chat_neighbor_hops: int = Field(
        default=2,
        alias="CHAT_NEIGHBOR_HOPS",
        description="Max relation hops to traverse from retrieved annotations",
    )
    chat_max_history: int = Field(
        default=5,
        alias="CHAT_MAX_HISTORY",
        description="Max dialogue turns kept in chat history context",
    )
    chat_max_context_chars: int = Field(
        default=3000,
        alias="CHAT_MAX_CONTEXT_CHARS",
        description="Max character budget for compacted context passed to LLM",
    )
    chat_min_relevance: float = Field(
        default=0.15,
        alias="CHAT_MIN_RELEVANCE",
        description="Minimum cosine relevance floor for vector chat context",
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
