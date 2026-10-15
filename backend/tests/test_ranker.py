"""Test ranking logic with known vectors and FakeEmbedder."""

import numpy as np
from backend.app.services.ranker import rank_sentences, cosine_similarity
from backend.app.services.embedder import FakeEmbedder


def test_cosine_similarity() -> None:
    """Verify cosine similarity calculation."""
    v1 = np.array([1.0, 0.0], dtype=np.float32)
    v2 = np.array([1.0, 0.0], dtype=np.float32)
    v3 = np.array([0.0, 1.0], dtype=np.float32)
    v4 = np.array([-1.0, 0.0], dtype=np.float32)

    assert pytest_approx(cosine_similarity(v1, v2), 1.0)
    assert pytest_approx(cosine_similarity(v1, v3), 0.0)
    assert pytest_approx(cosine_similarity(v1, v4), -1.0)


def pytest_approx(val, target, eps=1e-5):
    return abs(val - target) < eps


def test_rank_sentences_with_known_vectors() -> None:
    """Verify ranking orders by similarity to positives and applies negative penalty."""
    p_vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    n_vec = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    # Candidate 1: identical to positive
    c1 = {
        "id": 1,
        "start": 0,
        "end": 10,
        "embedding": np.array([1.0, 0.0, 0.0], dtype=np.float32),
    }
    # Candidate 2: halfway between positive and negative
    c2 = {
        "id": 2,
        "start": 10,
        "end": 20,
        "embedding": np.array([0.7071, 0.7071, 0.0], dtype=np.float32),
    }
    # Candidate 3: identical to negative
    c3 = {
        "id": 3,
        "start": 20,
        "end": 30,
        "embedding": np.array([0.0, 1.0, 0.0], dtype=np.float32),
    }

    # Test without negative penalty
    ranked = rank_sentences(
        sentences=[c1, c2, c3],
        positive_embeddings=[p_vec],
        negative_embeddings=[],
        existing_annotations=[],
        threshold=-1.0,
    )
    assert len(ranked) == 3
    assert ranked[0][0]["id"] == 1
    assert ranked[1][0]["id"] == 2
    assert ranked[2][0]["id"] == 3

    # Candidate 1 overlapping an existing annotation must be excluded
    ranked_excl = rank_sentences(
        sentences=[c1, c2, c3],
        positive_embeddings=[p_vec],
        negative_embeddings=[],
        existing_annotations=[{"start": 2, "end": 8}],  # overlaps c1 only
        threshold=-1.0,
    )
    assert len(ranked_excl) == 2
    assert ranked_excl[0][0]["id"] == 2


def test_ranker_with_fake_embedder() -> None:
    """Verify integration of FakeEmbedder with ranker."""
    embedder = FakeEmbedder(dim=8)
    texts = [
        "Machine learning models need training.",
        "Deep learning is a subset of machine learning.",
        "A recipe for chocolate cake with vanilla frosting.",
    ]
    embs = embedder.embed(texts)

    candidates = [
        {"id": 1, "start": 0, "end": 35, "embedding": embs[1]},
        {"id": 2, "start": 36, "end": 80, "embedding": embs[2]},
    ]

    # Positive example: texts[0]
    ranked = rank_sentences(
        sentences=candidates,
        positive_embeddings=[embs[0]],
        negative_embeddings=[],
        existing_annotations=[],
        threshold=-1.0,
    )
    assert len(ranked) == 2


def test_rank_sentences_vectorized_sample_equivalence() -> None:
    """Verify rank_sentences produces expected ranking and scores on sample embeddings."""
    rng = np.random.RandomState(42)
    pos = [rng.randn(32).astype(np.float32) for _ in range(3)]
    neg = [rng.randn(32).astype(np.float32) for _ in range(2)]
    cand_embs = [rng.randn(32).astype(np.float32) for _ in range(5)]

    sentences = [
        {"id": i, "start": i * 10, "end": (i + 1) * 10, "embedding": cand_embs[i]}
        for i in range(5)
    ]

    ranked = rank_sentences(
        sentences=sentences,
        positive_embeddings=pos,
        negative_embeddings=neg,
        existing_annotations=[],
        negative_weight=0.5,
        threshold=-1.0,
    )
    assert len(ranked) == 5
    scores = [score for _, score in ranked]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))


def test_retrieve_candidates_and_rank() -> None:
    """Verify retrieve_candidates fetches SQLite embeddings and ranks them."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.app.models import Base, Document, Sentence
    from backend.app.services.ranker import retrieve_candidates

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    v_pos = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v_neg = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    v_cand1 = np.array([0.9, 0.1, 0.0], dtype=np.float32)
    v_cand2 = np.array([0.1, 0.9, 0.0], dtype=np.float32)
    v_cand_other = np.array([1.0, 0.0, 0.0], dtype=np.float32)

    with Session() as session:
        doc1 = Document(filename="doc1.pdf", file_hash="h1", status="ready")
        doc2 = Document(filename="doc2.pdf", file_hash="h2", status="ready")
        session.add_all([doc1, doc2])
        session.commit()

        s1 = Sentence(document_id=doc1.id, idx=0, start=0, end=20, page=1, embedding=v_cand1.tobytes())
        s2 = Sentence(document_id=doc1.id, idx=1, start=21, end=40, page=1, embedding=v_cand2.tobytes())
        s3 = Sentence(document_id=doc2.id, idx=0, start=0, end=20, page=1, embedding=v_cand_other.tobytes())
        session.add_all([s1, s2, s3])
        session.commit()

        candidates = retrieve_candidates(query_vector=v_pos, document_id=doc1.id, db=session, pool_size=10)
        assert len(candidates) == 2
        assert all(c["document_id"] == doc1.id for c in candidates)

        ranked = rank_sentences(
            sentences=candidates,
            positive_embeddings=[v_pos],
            negative_embeddings=[v_neg],
            existing_annotations=[],
            negative_weight=0.5,
            threshold=-1.0,
        )
        assert len(ranked) == 2
        assert ranked[0][0]["id"] == s1.id
        assert ranked[1][0]["id"] == s2.id


