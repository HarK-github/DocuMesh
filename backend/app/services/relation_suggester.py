"""Background service for suggesting relations between annotation pairs via LLM."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from sqlalchemy.orm import Session
from backend.app.settings import get_settings
from backend.app.db import get_session_factory
from backend.app.models import Annotation, Relation, RelationType
from backend.app.services.llm import get_llm_client, LLMNotConfiguredError
from backend.app.services.jobs import update_job_status
from backend.app.services.embedder import get_embedder


def _build_prompt(ann1: Dict[str, Any], ann2: Dict[str, Any], valid_types: List[str]) -> str:
    """Construct prompt for relation inference between two annotations."""
    q1 = ann1.get("quote", "")
    l1 = ann1.get("label", "")
    q2 = ann2.get("quote", "")
    l2 = ann2.get("label", "")

    # Exclude technical/structural relation types like similar_to from semantic extraction prompt
    semantic_types = [t for t in valid_types if t != "similar_to"]
    if not semantic_types:
        semantic_types = valid_types

    return f"""Given two passages annotated in a document:

Passage 1:
Quote: "{q1}"
Label: {l1}

Passage 2:
Quote: "{q2}"
Label: {l2}

Permitted relation types: {semantic_types}

Relation Type Guidance:
- "supports": Passage 1 provides evidence, rationale, or proof supporting Passage 2 (or vice versa).
- "refutes": Passage 1 contradicts, counters, or questions Passage 2.
- "defines": Passage 1 defines, names, or specifies a concept/term used in Passage 2.
- "elaborates": Passage 1 provides further detail, depth, or context for Passage 2.
- "causes": Passage 1 directly leads to, causes, or influences Passage 2.
- "relates_to": Passages share a clear conceptual or topical relationship.

Instructions:
1. Determine if a typed relationship exists between these two passages.
2. If a relationship exists, specify "type" (one of the permitted relation types), "direction" ("forward" if Passage 1 relates to Passage 2, or "reverse" if Passage 2 relates to Passage 1), and a 1-2 sentence "reason".
3. If no clear relationship exists, set "type" to null.

You MUST reply with a JSON object in this format:
{{
  "type": "one_of_the_permitted_types_or_null",
  "direction": "forward",
  "reason": "1-2 sentence explanation justifying the relation"
}}
"""


def select_candidate_pairs(
    annotations: List[Dict[str, Any]],
    existing_relations: List[Relation],
    max_pairs: int = 10,
    seed_annotation_id: Optional[int] = None,
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Select and rank high-relevance annotation pairs for relation inference."""
    if len(annotations) < 2:
        return []

    # Exclude pairs that already have a typed relationship (supports, refutes, etc.)
    existing_typed = {
        (min(r.source_id, r.target_id), max(r.source_id, r.target_id))
        for r in existing_relations
        if r.type != "similar_to"
    }
    # Existing similar_to relations are prime candidates to infer typed relations for
    similar_pairs = {
        (min(r.source_id, r.target_id), max(r.source_id, r.target_id))
        for r in existing_relations
        if r.type == "similar_to"
    }

    embedder = get_embedder()
    quotes = [a.get("quote", "") for a in annotations]
    try:
        vecs = embedder.embed(quotes)
    except Exception:
        vecs = None

    candidates: List[Tuple[float, Dict[str, Any], Dict[str, Any]]] = []

    for i in range(len(annotations)):
        for j in range(i + 1, len(annotations)):
            a1, a2 = annotations[i], annotations[j]
            pair_key = (min(a1["id"], a2["id"]), max(a1["id"], a2["id"]))
            if pair_key in existing_typed:
                continue

            score = 0.0

            # Priority 1: Scoped to seed annotation if provided
            if seed_annotation_id is not None:
                if a1["id"] == seed_annotation_id or a2["id"] == seed_annotation_id:
                    score += 10.0
                else:
                    continue

            # Priority 2: Connections established via smart highlight similar_to
            if pair_key in similar_pairs:
                score += 3.0

            # Priority 3: Semantic embedding cosine similarity
            if vecs is not None and len(vecs) > max(i, j):
                try:
                    cos_sim = float(np.dot(vecs[i], vecs[j]))
                    score += max(0.0, cos_sim)
                except Exception:
                    pass

            # Natural ordering: earlier passage as source, later as target
            if a1.get("start", 0) <= a2.get("start", 0):
                candidates.append((score, a1, a2))
            else:
                candidates.append((score, a2, a1))

    candidates.sort(key=lambda x: x[0], reverse=True)

    # Ensure diversity across annotations when no seed is specified
    if seed_annotation_id is None and len(candidates) > max_pairs:
        selected: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        node_counts: Dict[int, int] = {}
        max_per_node = max(2, max_pairs // 3)

        for _, a1, a2 in candidates:
            c1 = node_counts.get(a1["id"], 0)
            c2 = node_counts.get(a2["id"], 0)
            if c1 < max_per_node and c2 < max_per_node:
                selected.append((a1, a2))
                node_counts[a1["id"]] = c1 + 1
                node_counts[a2["id"]] = c2 + 1
                if len(selected) >= max_pairs:
                    break

        if len(selected) < max_pairs:
            for _, a1, a2 in candidates:
                if (a1, a2) not in selected:
                    selected.append((a1, a2))
                    if len(selected) >= max_pairs:
                        break

        return selected[:max_pairs]

    return [(a1, a2) for _, a1, a2 in candidates[:max_pairs]]


def process_suggest_relations_job(
    job_id: str,
    document_id: int,
    seed_annotation_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute LLM relation suggestions across bounded, high-relevance annotation pairs."""
    settings = get_settings()
    session_factory = get_session_factory()

    update_job_status(job_id, status="running", progress=10)

    # Validate LLM configuration
    try:
        llm = get_llm_client()
    except LLMNotConfiguredError as exc:
        update_job_status(job_id, status="failed", error=str(exc))
        raise

    with session_factory() as session:
        ann_rows = (
            session.query(Annotation)
            .filter(Annotation.document_id == document_id)
            .all()
        )
        annotations = [
            {"id": a.id, "quote": a.quote, "label": a.label, "start": a.start, "end": a.end}
            for a in ann_rows
        ]
        existing_relations = (
            session.query(Relation)
            .filter(Relation.document_id == document_id)
            .all()
        )
        taxonomy_types = [r.name for r in session.query(RelationType).all()]

    if len(annotations) < 2:
        return {"suggested_count": 0, "message": "At least 2 annotations are required to infer relations."}

    candidate_pairs = select_candidate_pairs(
        annotations=annotations,
        existing_relations=existing_relations,
        max_pairs=settings.max_relation_pairs,
        seed_annotation_id=seed_annotation_id,
    )

    if not candidate_pairs:
        return {"suggested_count": 0, "message": "No new candidate annotation pairs to analyze."}

    update_job_status(job_id, progress=30)

    # Concurrency control via Semaphore
    semaphore = threading.Semaphore(settings.llm_max_concurrency)
    successful_relations = []
    failed_pairs = []

    def evaluate_pair(pair: Tuple[Dict[str, Any], Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        a1, a2 = pair
        with semaphore:
            try:
                prompt = _build_prompt(a1, a2, taxonomy_types)
                data = llm.complete_json(prompt)

                rel_type = data.get("type")
                reason = data.get("reason", "")
                direction = data.get("direction", "forward")

                if not rel_type or rel_type not in taxonomy_types:
                    failed_pairs.append({
                        "source_id": a1["id"],
                        "target_id": a2["id"],
                        "reason": f"Type '{rel_type}' not in taxonomy or was null",
                    })
                    return None

                # Determine direction: if LLM indicated reverse, swap source and target
                if direction == "reverse":
                    src_id, tgt_id = a2["id"], a1["id"]
                else:
                    src_id, tgt_id = a1["id"], a2["id"]

                return {
                    "document_id": document_id,
                    "source_id": src_id,
                    "target_id": tgt_id,
                    "type": rel_type,
                    "reason": reason,
                }
            except Exception as exc:
                failed_pairs.append({
                    "source_id": a1["id"],
                    "target_id": a2["id"],
                    "error": str(exc),
                })
                return None

    # Run evaluations concurrently
    with ThreadPoolExecutor(max_workers=settings.llm_max_concurrency) as executor:
        futures = [executor.submit(evaluate_pair, pair) for pair in candidate_pairs]
        for f in as_completed(futures):
            res = f.result()
            if res is not None:
                successful_relations.append(res)

    update_job_status(job_id, progress=80)

    # Persist suggested relations
    with session_factory() as session:
        for item in successful_relations:
            rel = Relation(
                document_id=item["document_id"],
                source_id=item["source_id"],
                target_id=item["target_id"],
                type=item["type"],
                status="suggested",
                reason=item["reason"],
                version=1,
            )
            session.add(rel)
        session.commit()

    result = {
        "suggested_count": len(successful_relations),
        "failed_pairs_count": len(failed_pairs),
        "failed_pairs": failed_pairs,
    }

    update_job_status(job_id, status="done", progress=100, result=result)
    return result
