"""Vector store interface and implementations for sentence similarity retrieval."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np

from backend.app.settings import get_settings


class BaseVectorStore(ABC):
    """Abstract interface for storing and querying sentence embedding vectors."""

    @abstractmethod
    def add(self, items: List[Dict[str, Any]]) -> None:
        """Add or upsert items to the store.

        Each item dict must contain:
        - 'id': str
        - 'vector': np.ndarray or List[float]
        - 'metadata': dict (e.g. {document_id, sentence_id, start, end, page})
        """
        pass

    @abstractmethod
    def query(
        self,
        vector: np.ndarray,
        k: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query top k similar items. Returns list of dicts: {'id': str, 'score': float, 'metadata': dict}."""
        pass

    @abstractmethod
    def delete(self, ids: List[str]) -> None:
        """Delete items by ID."""
        pass

    @abstractmethod
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Return count of items matching filters (or total if filters is None)."""
        pass


class FakeVectorStore(BaseVectorStore):
    """In-memory vector store for unit tests."""

    def __init__(self) -> None:
        self._items: Dict[str, Dict[str, Any]] = {}

    def add(self, items: List[Dict[str, Any]]) -> None:
        """Add normalized vectors to memory."""
        for item in items:
            v = np.asarray(item["vector"], dtype=np.float32)
            norm = np.linalg.norm(v)
            if norm > 0:
                v = v / norm
            self._items[str(item["id"])] = {
                "id": str(item["id"]),
                "vector": v,
                "metadata": dict(item.get("metadata", {})),
            }

    def query(
        self,
        vector: np.ndarray,
        k: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Calculate cosine similarity and return top k matching items."""
        if not self._items or k <= 0:
            return []

        q = np.asarray(vector, dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm

        candidates = []
        for it in self._items.values():
            if filters:
                if not all(it["metadata"].get(fk) == fv for fk, fv in filters.items()):
                    continue
            sim = float(np.dot(q, it["vector"]))
            candidates.append({
                "id": it["id"],
                "score": round(sim, 4),
                "metadata": dict(it["metadata"]),
                "vector": it["vector"],
            })

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:k]

    def delete(self, ids: List[str]) -> None:
        """Remove items from memory."""
        for i in ids:
            self._items.pop(str(i), None)

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count in-memory items."""
        if not filters:
            return len(self._items)
        return sum(
            1
            for it in self._items.values()
            if all(it["metadata"].get(fk) == fv for fk, fv in filters.items())
        )


class ChromaVectorStore(BaseVectorStore):
    """Persistent Chroma vector store with cosine similarity."""

    def __init__(self, path: Optional[str] = None) -> None:
        import chromadb

        settings = get_settings()
        db_path = path or settings.vector_store_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=db_path)
        self._collection = self._client.get_or_create_collection(
            name="document_sentences",
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, items: List[Dict[str, Any]]) -> None:
        """Add or upsert items into Chroma collection."""
        if not items:
            return

        ids = []
        embeddings = []
        metadatas = []

        for it in items:
            ids.append(str(it["id"]))
            vec = it["vector"]
            if isinstance(vec, np.ndarray):
                embeddings.append(vec.tolist())
            else:
                embeddings.append(list(vec))
            metadatas.append(dict(it.get("metadata", {})))

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def _format_where(self, filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Format dictionary into Chroma where filter structure."""
        if not filters:
            return None
        if len(filters) == 1:
            return filters
        return {"$and": [{k: v} for k, v in filters.items()]}

    def query(
        self,
        vector: np.ndarray,
        k: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query collection and return similarity scores."""
        total = self._collection.count()
        if total == 0 or k <= 0:
            return []

        vec = vector.tolist() if isinstance(vector, np.ndarray) else list(vector)
        where = self._format_where(filters)
        n_res = min(k, total)

        results = self._collection.query(
            query_embeddings=[vec],
            n_results=n_res,
            where=where,
            include=["metadatas", "distances", "embeddings"],
        )

        output = []
        ids_list = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        embs_list = results.get("embeddings", [[]])[0] if results.get("embeddings") is not None else [None] * len(ids_list)

        for item_id, dist, meta, emb in zip(ids_list, distances, metadatas, embs_list):
            similarity = round(float(1.0 - dist), 4)
            output.append({
                "id": str(item_id),
                "score": similarity,
                "metadata": dict(meta) if meta else {},
                "vector": np.asarray(emb, dtype=np.float32) if emb is not None else None,
            })

        output.sort(key=lambda x: x["score"], reverse=True)
        return output

    def delete(self, ids: List[str]) -> None:
        """Delete items by id."""
        if not ids:
            return
        self._collection.delete(ids=[str(i) for i in ids])

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count items matching where clause."""
        if not filters:
            return self._collection.count()
        where = self._format_where(filters)
        res = self._collection.get(where=where)
        return len(res.get("ids", []))


def rebuild_vector_store_if_needed(db: Any, store: Optional[BaseVectorStore] = None) -> int:
    """Ensure all ready documents have their sentence vectors indexed in the vector store."""
    from backend.app.models import Document, Sentence

    vstore = store if store is not None else get_vector_store()
    ready_docs = db.query(Document).filter(Document.status == "ready").all()
    rebuilt_count = 0

    for doc in ready_docs:
        count = vstore.count({"document_id": doc.id})
        if count == 0:
            sentences = (
                db.query(Sentence)
                .filter(Sentence.document_id == doc.id, Sentence.embedding.isnot(None))
                .all()
            )
            items = []
            for s in sentences:
                items.append({
                    "id": f"doc_{doc.id}_sent_{s.id}",
                    "vector": np.frombuffer(s.embedding, dtype=np.float32),
                    "metadata": {
                        "document_id": doc.id,
                        "sentence_id": s.id,
                        "start": s.start,
                        "end": s.end,
                        "page": s.page,
                    },
                })
            if items:
                vstore.add(items)
                rebuilt_count += len(items)

    return rebuilt_count


_shared_vector_store: Optional[BaseVectorStore] = None


def get_vector_store() -> BaseVectorStore:
    """Return configured vector store instance."""
    global _shared_vector_store
    if _shared_vector_store is not None:
        return _shared_vector_store

    settings = get_settings()
    if settings.vector_store == "fake":
        _shared_vector_store = FakeVectorStore()
    elif settings.vector_store == "chroma":
        _shared_vector_store = ChromaVectorStore()
    else:
        raise ValueError(f"Unsupported VECTOR_STORE: {settings.vector_store}")

    return _shared_vector_store


def set_shared_vector_store(store: Optional[BaseVectorStore]) -> None:
    """Explicitly override vector store instance (for test mocking)."""
    global _shared_vector_store
    _shared_vector_store = store

