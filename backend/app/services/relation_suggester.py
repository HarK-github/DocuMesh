"""Background service for suggesting relations between annotation pairs via LLM."""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.orm import Session
from backend.app.settings import get_settings
from backend.app.db import get_session_factory
from backend.app.models import Annotation, Relation, RelationType
from backend.app.services.llm import get_llm_client, LLMNotConfiguredError
from backend.app.services.jobs import update_job_status


def _build_prompt(ann1: Dict[str, Any], ann2: Dict[str, Any], valid_types: List[str]) -> str:
    """Construct prompt for relation inference between two annotations."""
    q1 = ann1.get("quote", "")
    l1 = ann1.get("label", "")
    q2 = ann2.get("quote", "")
    l2 = ann2.get("label", "")
    return f"""Given two passages annotated in a document:

Passage 1 (Source):
Quote: "{q1}"
Label: {l1}

Passage 2 (Target):
Quote: "{q2}"
Label: {l2}

Permitted relation types: {valid_types}

Determine if there is a typed relationship where Passage 1 relates to Passage 2.
You MUST reply with a JSON object containing:
- "type": exactly one string from the permitted relation types, or null if no clear relationship exists.
- "reason": a short explanation (1-2 sentences) justifying the relation.
"""


def process_suggest_relations_job(job_id: str, document_id: int) -> Dict[str, Any]:
    """Execute LLM relation suggestions across bounded annotation pairs."""
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
            {"id": a.id, "quote": a.quote, "label": a.label}
            for a in ann_rows
        ]
        existing_relations = (
            session.query(Relation)
            .filter(Relation.document_id == document_id)
            .all()
        )
        existing_pairs = {(r.source_id, r.target_id) for r in existing_relations}
        taxonomy_types = [r.name for r in session.query(RelationType).all()]

    if len(annotations) < 2:
        return {"suggested_count": 0, "message": "At least 2 annotations are required to infer relations."}

    candidate_pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for a1 in annotations:
        for a2 in annotations:
            if a1["id"] != a2["id"] and (a1["id"], a2["id"]) not in existing_pairs:
                candidate_pairs.append((a1, a2))

    # Cap pairs from settings
    candidate_pairs = candidate_pairs[: settings.max_relation_pairs]
    if not candidate_pairs:
        return {"suggested_count": 0, "message": "No new annotation pairs to analyze."}

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

                if not rel_type or rel_type not in taxonomy_types:
                    failed_pairs.append({
                        "source_id": a1["id"],
                        "target_id": a2["id"],
                        "reason": f"Type '{rel_type}' not in taxonomy or was null",
                    })
                    return None

                return {
                    "document_id": document_id,
                    "source_id": a1["id"],
                    "target_id": a2["id"],
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
