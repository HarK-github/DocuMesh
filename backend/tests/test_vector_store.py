"""Tests for vector store interface, implementations, and startup rebuild."""

import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models import Base, Document, Sentence
from backend.app.services.vector_store import (
    FakeVectorStore,
    rebuild_vector_store_if_needed,
)
from backend.app.services.ranker import retrieve_candidates, rank_sentences


def test_fake_vector_store_add_query_filter() -> None:
    """Test adding items, querying with filters, and similarity calculation."""
    store = FakeVectorStore()
    v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    v3 = np.array([0.7071, 0.7071, 0.0], dtype=np.float32)

    store.add([
        {
            "id": "item1",
            "vector": v1,
            "metadata": {"document_id": 1, "sentence_id": 101, "start": 0, "end": 10, "page": 1},
        },
        {
            "id": "item2",
            "vector": v2,
            "metadata": {"document_id": 1, "sentence_id": 102, "start": 10, "end": 20, "page": 1},
        },
        {
            "id": "item3",
            "vector": v3,
            "metadata": {"document_id": 2, "sentence_id": 201, "start": 0, "end": 15, "page": 1},
        },
    ])

    # Count without filter
    assert store.count() == 3
    # Count with filter
    assert store.count({"document_id": 1}) == 2
    assert store.count({"document_id": 2}) == 1

    # Query with filter for document_id == 1
    query_vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    results = store.query(vector=query_vec, k=5, filters={"document_id": 1})

    assert len(results) == 2
    assert results[0]["id"] == "item1"
    assert abs(results[0]["score"] - 1.0) < 1e-3
    assert results[0]["metadata"]["sentence_id"] == 101
    assert results[1]["id"] == "item2"
    assert abs(results[1]["score"] - 0.0) < 1e-3


def test_fake_vector_store_delete() -> None:
    """Test deleting items by ID."""
    store = FakeVectorStore()
    v = np.array([1.0, 0.0], dtype=np.float32)
    store.add([
        {"id": "a", "vector": v, "metadata": {"document_id": 1}},
        {"id": "b", "vector": v, "metadata": {"document_id": 1}},
    ])
    assert store.count() == 2

    store.delete(["a"])
    assert store.count() == 1
    results = store.query(v, k=5)
    assert len(results) == 1
    assert results[0]["id"] == "b"


def test_rebuild_from_sqlite_when_empty() -> None:
    """Test rebuilding vectors from SQLite into store when store is empty."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()

    v1 = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
    v2 = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)

    # Document 1 is ready with 2 sentences
    doc1 = Document(filename="doc1.pdf", file_hash="hash1", status="ready", clean_text="Hello world. Foo bar.")
    db.add(doc1)
    db.flush()

    s1 = Sentence(
        document_id=doc1.id,
        idx=0,
        start=0,
        end=12,
        page=1,
        embedding=v1.tobytes(),
    )
    s2 = Sentence(
        document_id=doc1.id,
        idx=1,
        start=13,
        end=21,
        page=1,
        embedding=v2.tobytes(),
    )
    db.add_all([s1, s2])

    # Document 2 is processing (not ready) - should NOT be rebuilt
    doc2 = Document(filename="doc2.pdf", file_hash="hash2", status="processing")
    db.add(doc2)
    db.flush()
    s3 = Sentence(
        document_id=doc2.id,
        idx=0,
        start=0,
        end=5,
        page=1,
        embedding=v1.tobytes(),
    )
    db.add(s3)
    db.commit()

    store = FakeVectorStore()
    assert store.count() == 0

    # Rebuild
    count = rebuild_vector_store_if_needed(db, store=store)
    assert count == 2
    assert store.count({"document_id": doc1.id}) == 2
    assert store.count({"document_id": doc2.id}) == 0

    # Calling again should not re-index
    count_again = rebuild_vector_store_if_needed(db, store=store)
    assert count_again == 0
    assert store.count() == 2

    db.close()


def test_ranker_working_through_fake_store() -> None:
    """Test retrieve_candidates from vector store and subsequent ranking."""
    store = FakeVectorStore()
    v_pos = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v_neg = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    v_cand1 = np.array([0.9, 0.1, 0.0], dtype=np.float32)
    v_cand2 = np.array([0.1, 0.9, 0.0], dtype=np.float32)
    v_cand_other_doc = np.array([1.0, 0.0, 0.0], dtype=np.float32)

    store.add([
        {
            "id": "d1_s1",
            "vector": v_cand1,
            "metadata": {"document_id": 1, "sentence_id": 101, "start": 0, "end": 20, "page": 1},
        },
        {
            "id": "d1_s2",
            "vector": v_cand2,
            "metadata": {"document_id": 1, "sentence_id": 102, "start": 21, "end": 40, "page": 1},
        },
        {
            "id": "d2_s1",
            "vector": v_cand_other_doc,
            "metadata": {"document_id": 2, "sentence_id": 201, "start": 0, "end": 20, "page": 1},
        },
    ])

    candidates = retrieve_candidates(query_vector=v_pos, document_id=1, store=store, pool_size=10)
    assert len(candidates) == 2
    assert all(c["document_id"] == 1 for c in candidates)

    ranked = rank_sentences(
        sentences=candidates,
        positive_embeddings=[v_pos],
        negative_embeddings=[v_neg],
        existing_annotations=[],
        negative_weight=0.5,
        threshold=-1.0,
    )

    assert len(ranked) == 2
    # Candidate 1 should be ranked higher than Candidate 2
    assert ranked[0][0]["sentence_id"] == 101
    assert ranked[1][0]["sentence_id"] == 102
