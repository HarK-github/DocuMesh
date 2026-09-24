"""Embedding service interface with SentenceTransformer and Fake implementations."""

from abc import ABC, abstractmethod
from typing import List, Optional
import hashlib
import numpy as np
from backend.app.settings import get_settings


class BaseEmbedder(ABC):
    """Abstract embedder interface for generating vector representations."""

    @abstractmethod
    def embed(self, texts: List[str]) -> np.ndarray:
        """Convert a list of text strings into an (N, D) normalized numpy float32 array."""
        pass


class FakeEmbedder(BaseEmbedder):
    """Deterministic fake embedder for testing without model overhead."""

    def __init__(self, dim: int = 16) -> None:
        self.dim = dim

    def embed(self, texts: List[str]) -> np.ndarray:
        """Generate deterministic pseudo-random normalized unit vectors from text hashes."""
        vectors = []
        for t in texts:
            # Seed numpy with hash of string
            h = int(hashlib.md5(t.encode("utf-8")).hexdigest(), 16) % (2**31)
            rng = np.random.RandomState(h)
            v = rng.randn(self.dim).astype(np.float32)
            norm = np.linalg.norm(v)
            if norm > 0:
                v = v / norm
            vectors.append(v)
        return np.vstack(vectors) if vectors else np.empty((0, self.dim), dtype=np.float32)


class SentenceTransformerEmbedder(BaseEmbedder):
    """Real sentence-transformers embedder with batching."""

    def __init__(self, model_name: str = None) -> None:
        from sentence_transformers import SentenceTransformer
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model_name
        self.batch_size = settings.embed_batch_size
        self._model = SentenceTransformer(self.model_name)

    def embed(self, texts: List[str]) -> np.ndarray:
        """Compute normalized dense embeddings using SentenceTransformer."""
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
        embeddings = self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(embeddings, dtype=np.float32)


_shared_embedder: Optional[BaseEmbedder] = None


def get_embedder(force_fake: bool = False) -> BaseEmbedder:
    """Return shared embedder instance, using FakeEmbedder if specified or in tests."""
    global _shared_embedder
    settings = get_settings()

    if force_fake or settings.embedding_model_name == "fake":
        return FakeEmbedder()

    if _shared_embedder is None:
        try:
            _shared_embedder = SentenceTransformerEmbedder()
        except Exception:
            _shared_embedder = FakeEmbedder()

    return _shared_embedder


def set_shared_embedder(embedder: Optional[BaseEmbedder]) -> None:
    """Explicitly override embedder (useful for test fixtures)."""
    global _shared_embedder
    _shared_embedder = embedder
