"""Ranking service for smart highlight suggestions based on embedding similarity."""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from backend.app.settings import get_settings
def retrieve_candidates(
    query_vector: np.ndarray,
    document_id: int,
    db: Optional[Any] = None,
    pool_size: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Retrieve top candidates for a document using SQLite embeddings and NumPy dot product."""
    settings = get_settings()
    k = pool_size if pool_size is not None else settings.candidate_pool_size

    def _query(session: Any) -> List[Dict[str, Any]]:
        from backend.app.models import Sentence

        sents = (
            session.query(Sentence)
            .filter(Sentence.document_id == document_id, Sentence.embedding.isnot(None))
            .all()
        )
        if not sents:
            return []

        q_norm = np.linalg.norm(query_vector)
        q_vec = query_vector / q_norm if q_norm > 0 else query_vector

        vectors = np.stack([np.frombuffer(s.embedding, dtype=np.float32) for s in sents])
        v_norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / np.where(v_norms == 0, 1.0, v_norms)

        sims = vectors @ q_vec

        candidates = []
        for s, vec, score in zip(sents, vectors, sims):
            candidates.append({
                "id": s.id,
                "sentence_id": s.id,
                "document_id": document_id,
                "start": s.start,
                "end": s.end,
                "page": s.page,
                "embedding": vec,
                "vector": vec,
                "score": float(score),
            })
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:k]

    if db is not None:
        return _query(db)

    from backend.app.db import get_session_factory

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        return _query(session)



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


def compute_candidate_score(
    candidate_vec: np.ndarray,
    positive_embeddings: List[np.ndarray],
    negative_embeddings: List[np.ndarray],
    neg_weight: float = 0.5,
) -> float:
    """Pure scoring function: max_sim(cand, positives) - NEG_WEIGHT * max_sim(cand, negatives)."""
    if not positive_embeddings:
        return 0.0

    pos_sim = max(cosine_similarity(candidate_vec, p) for p in positive_embeddings)
    neg_sim = (
        max(cosine_similarity(candidate_vec, n) for n in negative_embeddings)
        if negative_embeddings
        else 0.0
    )
    return float(pos_sim - neg_weight * neg_sim)


def select_diverse_candidates_mmr(
    candidates: List[Dict[str, Any]],
    mmr_lambda: float = 0.7,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Greedily select candidates maximizing MMR_LAMBDA * score - (1 - MMR_LAMBDA) * max_sim(cand, already_picked)."""
    if not candidates or limit <= 0:
        return []

    remaining = list(candidates)
    selected = []

    while remaining and len(selected) < limit:
        best_cand = None
        best_mmr_score = -float("inf")
        best_idx = -1

        for idx, cand in enumerate(remaining):
            cand_score = cand["score"]
            c_vec = cand.get("vector") if cand.get("vector") is not None else cand.get("embedding")

            if not selected:
                mmr_score = cand_score
            else:
                max_sim_picked = max(
                    cosine_similarity(
                        c_vec,
                        s.get("vector") if s.get("vector") is not None else s.get("embedding"),
                    )
                    for s in selected
                )
                mmr_score = mmr_lambda * cand_score - (1.0 - mmr_lambda) * max_sim_picked

            if mmr_score > best_mmr_score:
                best_mmr_score = mmr_score
                best_cand = cand
                best_idx = idx

        if best_cand is not None and best_idx >= 0:
            selected.append(best_cand)
            remaining.pop(best_idx)
        else:
            break

    return selected



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

    # Stack and normalize embeddings
    pos_matrix = np.vstack(positive_embeddings)
    pos_norms = np.linalg.norm(pos_matrix, axis=1, keepdims=True)
    pos_matrix = pos_matrix / np.where(pos_norms == 0, 1.0, pos_norms)

    neg_matrix = None
    if negative_embeddings:
        neg_matrix = np.vstack(negative_embeddings)
        neg_norms = np.linalg.norm(neg_matrix, axis=1, keepdims=True)
        neg_matrix = neg_matrix / np.where(neg_norms == 0, 1.0, neg_norms)

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

        sent_norm = np.linalg.norm(sent_emb)
        sent_vec = sent_emb / sent_norm if sent_norm > 0 else sent_emb

        # 2. Compute mean similarity to positive examples
        mean_pos = float((pos_matrix @ sent_vec).mean())

        # 3. Compute weighted penalty for negative examples
        neg_penalty = 0.0
        if neg_matrix is not None and len(neg_matrix) > 0:
            neg_penalty = negative_weight * float((neg_matrix @ sent_vec).mean())

        final_score = mean_pos - neg_penalty

        # 4. Check threshold
        if final_score >= min_threshold:
            scored_candidates.append((s, round(final_score, 4)))

    # 5. Sort descending by score and cap at limit
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    return scored_candidates[:limit]
