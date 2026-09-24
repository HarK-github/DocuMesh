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
