"""Ranking service for smart highlight suggestions based on embedding similarity."""

from typing import List, Dict, Any, Tuple
import numpy as np
from backend.app.settings import get_settings


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute cosine similarity between two 1D vectors."""
    dot = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))


def intervals_overlap(start1: int, end1: int, start2: int, end2: int) -> bool:
    """Return True if two intervals overlap."""
    return max(start1, start2) < min(end1, end2)


def rank_sentences(
    sentences: List[Dict[str, Any]],
    positive_embeddings: List[np.ndarray],
    negative_embeddings: List[np.ndarray],
    existing_annotations: List[Dict[str, Any]],
    negative_weight: float = 0.5,
    threshold: float = None,
    top_k: int = None,
) -> List[Tuple[Dict[str, Any], float]]:
    """Score and rank candidate sentences relative to positive and negative examples."""
    settings = get_settings()
    min_threshold = threshold if threshold is not None else settings.similarity_threshold
    limit = top_k if top_k is not None else settings.suggestion_count

    if not positive_embeddings:
        return []

    # Stack embeddings
    pos_matrix = np.vstack(positive_embeddings)
    neg_matrix = np.vstack(negative_embeddings) if negative_embeddings else None

    scored_candidates = []

    for s in sentences:
        # 1. Exclude sentences already covered by existing annotations
        s_start = int(s["start"])
        s_end = int(s["end"])
        is_covered = any(
            intervals_overlap(s_start, s_end, int(a["start"]), int(a["end"]))
            for a in existing_annotations
        )
        if is_covered:
            continue

        sent_emb = s.get("embedding")
        if sent_emb is None:
            continue

        # 2. Compute mean similarity to positive examples
        pos_sims = [cosine_similarity(sent_emb, p) for p in pos_matrix]
        mean_pos = float(np.mean(pos_sims)) if pos_sims else 0.0

        # 3. Compute weighted penalty for negative examples
        neg_penalty = 0.0
        if neg_matrix is not None and len(neg_matrix) > 0:
            neg_sims = [cosine_similarity(sent_emb, n) for n in neg_matrix]
            neg_penalty = negative_weight * float(np.mean(neg_sims))

        final_score = mean_pos - neg_penalty

        # 4. Check threshold
        if final_score >= min_threshold:
            scored_candidates.append((s, round(final_score, 4)))

    # 5. Sort descending by score and cap at limit
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    return scored_candidates[:limit]
