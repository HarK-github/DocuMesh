"""Tests for pgvector functionality: write/read roundtrip, filtered cosine ranking, ordering, and migration conversion."""

import numpy as np
from backend.app.models import Document, Sentence, EMBEDDING_DIM
from backend.app.services.ranker import retrieve_candidates


def test_vector_write_read_roundtrip(db_session) -> None:
    """Verify vector embeddings write and read back cleanly from pgvector."""
    doc = Document(filename="roundtrip.pdf", file_hash="hash_rt_1", status="ready")
    db_session.add(doc)
    db_session.commit()

    rng = np.random.RandomState(42)
    orig_vec = rng.randn(EMBEDDING_DIM).astype(np.float32)
    orig_vec = orig_vec / np.linalg.norm(orig_vec)

    sentence = Sentence(
        document_id=doc.id,
        idx=0,
        start=0,
        end=50,
        page=1,
        embedding=orig_vec,
    )
    db_session.add(sentence)
    db_session.commit()

    fetched = db_session.query(Sentence).filter(Sentence.id == sentence.id).first()
    assert fetched is not None
    assert fetched.embedding is not None

    arr = np.asarray(fetched.embedding, dtype=np.float32)
    assert arr.shape == (EMBEDDING_DIM,)
    assert np.allclose(arr, orig_vec, atol=1e-5)


def test_filtered_cosine_ranking_doc_and_page(db_session) -> None:
    """Verify filtered cosine distance ranking by document_id and page."""
    doc1 = Document(filename="doc1.pdf", file_hash="hash_f1", status="ready")
    doc2 = Document(filename="doc2.pdf", file_hash="hash_f2", status="ready")
    db_session.add_all([doc1, doc2])
    db_session.commit()

    v_base = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    v_base[0] = 1.0

    # s1: doc1, page 1
    s1 = Sentence(document_id=doc1.id, idx=0, start=0, end=10, page=1, embedding=v_base)
    # s2: doc1, page 2
    s2 = Sentence(document_id=doc1.id, idx=1, start=11, end=20, page=2, embedding=v_base)
    # s3: doc2, page 2
    s3 = Sentence(document_id=doc2.id, idx=0, start=0, end=10, page=2, embedding=v_base)

    db_session.add_all([s1, s2, s3])
    db_session.commit()

    # Query with document_id=doc1 and page=2 filter
    results = retrieve_candidates(
        query_vector=v_base,
        document_id=doc1.id,
        db=db_session,
        page=2,
    )

    assert len(results) == 1
    assert results[0]["id"] == s2.id
    assert results[0]["document_id"] == doc1.id
    assert results[0]["page"] == 2


def test_cosine_ranking_correct_ordering(db_session) -> None:
    """Verify candidates are ordered by cosine similarity descending."""
    doc = Document(filename="ordering.pdf", file_hash="hash_ord", status="ready")
    db_session.add(doc)
    db_session.commit()

    q_vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    q_vec[0] = 1.0

    # High similarity candidate
    v_high = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    v_high[0] = 0.95
    v_high[1] = 0.05
    v_high /= np.linalg.norm(v_high)

    # Medium similarity candidate
    v_med = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    v_med[0] = 0.60
    v_med[1] = 0.40
    v_med /= np.linalg.norm(v_med)

    # Low similarity candidate
    v_low = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    v_low[1] = 1.0

    s_high = Sentence(document_id=doc.id, idx=0, start=0, end=10, page=1, embedding=v_high)
    s_med = Sentence(document_id=doc.id, idx=1, start=11, end=20, page=1, embedding=v_med)
    s_low = Sentence(document_id=doc.id, idx=2, start=21, end=30, page=1, embedding=v_low)

    db_session.add_all([s_med, s_low, s_high])  # Add in mixed order
    db_session.commit()

    candidates = retrieve_candidates(
        query_vector=q_vec,
        document_id=doc.id,
        db=db_session,
        pool_size=10,
    )

    assert len(candidates) == 3
    assert candidates[0]["id"] == s_high.id
    assert candidates[1]["id"] == s_med.id
    assert candidates[2]["id"] == s_low.id

    assert candidates[0]["score"] > candidates[1]["score"] > candidates[2]["score"]
    assert np.isclose(candidates[0]["score"], float(1.0 - (1.0 - np.dot(q_vec, v_high))), atol=1e-4)


def test_migration_blob_to_vector_conversion(db_session) -> None:
    """Verify that legacy float32 blob byte buffers convert cleanly to pgvector Vector column."""
    rng = np.random.RandomState(123)
    original_floats = rng.randn(EMBEDDING_DIM).astype(np.float32)

    # Legacy storage: float32 byte buffer
    blob_bytes = original_floats.tobytes()

    # Migration conversion logic (from alembic/versions/c1f2e3d4a5b6_migrate_to_pgvector.py)
    converted_vector = np.frombuffer(blob_bytes, dtype=np.float32).tolist()

    doc = Document(filename="migration_test.pdf", file_hash="hash_mig_1", status="ready")
    db_session.add(doc)
    db_session.commit()

    sentence = Sentence(
        document_id=doc.id,
        idx=0,
        start=0,
        end=30,
        page=1,
        embedding=converted_vector,
    )
    db_session.add(sentence)
    db_session.commit()

    retrieved = db_session.query(Sentence).filter(Sentence.id == sentence.id).first()
    assert retrieved is not None
    assert np.allclose(np.asarray(retrieved.embedding, dtype=np.float32), original_floats, atol=1e-5)
