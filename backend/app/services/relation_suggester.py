"""Background service for suggesting relations between annotation pairs via LLM."""

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Tuple, Optional, Set
import numpy as np
from sqlalchemy.orm import Session
from backend.app.settings import get_settings
from backend.app.db import get_session_factory
from backend.app.models import Annotation, Relation, RelationCache, RejectedPair
from backend.app.taxonomy import TAXONOMY_RELATION_TYPES
from backend.app.services.llm import get_llm_client, LLMNotConfiguredError
from backend.app.services.jobs import update_job_status
from backend.app.services.embedder import get_embedder


SKIP_LABEL_PAIRS = {
    frozenset({"Definition", "Result"}),
    frozenset({"Definition", "Method"}),
}

HIGH_PRIORITY_LABEL_PAIRS = {
    frozenset({"Claim", "Evidence"}),
    frozenset({"Problem", "Solution"}),
}


def make_relation_cache_key(
    quote1: str, label1: str, quote2: str, label2: str, taxonomy_version: str
) -> Tuple[str, bool]:
    """Compute canonical sha256 hash for passage pair and return (cache_key, is_swapped)."""
    p1 = (quote1.strip(), label1 or "")
    p2 = (quote2.strip(), label2 or "")
    if p1 <= p2:
        payload = f"{p1[0]}\x00{p1[1]}\x00{p2[0]}\x00{p2[1]}\x00{taxonomy_version}"
        is_swapped = False
    else:
        payload = f"{p2[0]}\x00{p2[1]}\x00{p1[0]}\x00{p1[1]}\x00{taxonomy_version}"
        is_swapped = True
    key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return key, is_swapped


def _format_few_shot(examples: List[Dict[str, Any]]) -> str:
    """Format confirmed relations into few-shot examples for prompt prefix."""
    if not examples:
        return ""
    lines = ["Confirmed Examples from this Document:"]
    for ex in examples:
        lines.append(
            f'- Passage 1 ({ex["source_label"]}): "{ex["source_quote"]}"\n'
            f'  Passage 2 ({ex["target_label"]}): "{ex["target_quote"]}"\n'
            f'  -> type: "{ex["type"]}" | direction: "forward" | reason: "{ex["reason"]}"'
        )
    return "\n".join(lines) + "\n\n"


def _get_few_shot_examples(
    session: Session,
    document_id: int,
    ann_map: Dict[int, Dict[str, Any]],
    anchor_label: str,
    candidate_labels: Set[str],
    max_examples: int = 3,
) -> List[Dict[str, Any]]:
    """Retrieve up to max_examples confirmed relations sharing label pairs with candidate set."""
    confirmed = (
        session.query(Relation)
        .filter(
            Relation.document_id == document_id,
            Relation.status == "confirmed",
            Relation.type.isnot(None),
            Relation.type != "similar_to",
        )
        .all()
    )
    if not confirmed:
        return []

    examples: List[Dict[str, Any]] = []
    seen = set()
    for rel in confirmed:
        s_ann = ann_map.get(rel.source_id)
        t_ann = ann_map.get(rel.target_id)
        if not s_ann or not t_ann:
            continue
        s_lbl, t_lbl = s_ann.get("label", ""), t_ann.get("label", "")
        pair_labels = {s_lbl, t_lbl}
        if anchor_label in pair_labels and any(cl in pair_labels for cl in candidate_labels):
            pair_key = (min(rel.source_id, rel.target_id), max(rel.source_id, rel.target_id))
            if pair_key in seen:
                continue
            seen.add(pair_key)
            examples.append({
                "source_label": s_lbl,
                "source_quote": s_ann.get("quote", ""),
                "target_label": t_lbl,
                "target_quote": t_ann.get("quote", ""),
                "type": rel.type,
                "reason": rel.reason or "Confirmed typed relationship.",
            })
            if len(examples) >= max_examples:
                break
    return examples


def _build_anchor_prompt(
    anchor: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    valid_types: List[str],
    few_shot_examples: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Construct batched prompt for an anchor annotation and its candidate partners."""
    few_shot_block = _format_few_shot(few_shot_examples or [])
    cand_lines = []
    for c in candidates:
        cand_lines.append(
            f'Candidate ID {c["id"]} (Label: {c.get("label", "Unknown")}):\n'
            f'"{c.get("quote", "")}"'
        )
    candidates_text = "\n\n".join(cand_lines)

    return f"""You are an expert relational knowledge graph extraction assistant.
Determine the semantic typed relationship between the Anchor passage and each Candidate passage.

Permitted relation types:
{valid_types}

Label-Aware Dynamic Rules:
- Problem <-> Solution: MUST use "solves" if one passage resolves, addresses, or proposes a solution to the other.
- Claim <-> Evidence: MUST use "supports" (if evidence justifies the claim) or "refutes" (if evidence contradicts it).
- Definition <-> any passage: MUST use "defines" if one passage defines or names a concept used in the other.
- Method <-> Result: MUST use "causes" or "supports".
- Claim <-> Claim / Problem <-> Problem: use "similar_to" (if identical claim/problem), "contrasts_with", or "elaborates".
- Contrasting ideas: use "contrasts_with" when passages express opposing views without direct refutation.
- Conditions / Prerequisites: use "conditional_on" when one passage depends on or assumes the other.
- Sequential / Temporal: use "precedes" when one event/step occurs before another.
- NOTE: "relates_to" is STRICTLY A LAST RESORT FALLBACK. Never use "relates_to" if a more specific relation type applies.

{few_shot_block}Instructions:
1. For each Candidate passage, examine if there is a typed relationship with the Anchor passage.
2. For each Candidate, specify:
   - "candidate_id": the numeric ID of the candidate
   - "type": one of the permitted relation types, or null if no relationship exists
   - "direction": "forward" (Anchor -> Candidate), "reverse" (Candidate -> Anchor), or null if type is null
   - "reason": concise 1-sentence justification (or reason why none)
3. Return ONLY a JSON object with a "relations" array containing one entry per candidate.

Anchor Passage (ID: {anchor["id"]} | Label: {anchor.get("label", "Unknown")}):
"{anchor.get("quote", "")}"

Candidate Passages:
{candidates_text}

JSON Response Format:
{{
  "relations": [
    {{
      "candidate_id": <candidate_id>,
      "type": "one_of_the_permitted_types_or_null",
      "direction": "forward",
      "reason": "1-sentence justification"
    }}
  ]
}}
"""



def select_candidate_pairs(
    annotations: List[Dict[str, Any]],
    existing_relations: List[Relation],
    max_pairs: int = 10,
    seed_annotation_id: Optional[int] = None,
    rejected_pairs: Optional[Set[Tuple[int, int]]] = None,
    min_cos_sim: float = 0.25,
) -> List[Tuple[Dict[str, Any], Dict[str, Any], float]]:
    """Select and rank high-relevance annotation pairs for relation inference."""
    if len(annotations) < 2:
        return []

    existing_typed = {
        (min(r.source_id, r.target_id), max(r.source_id, r.target_id))
        for r in existing_relations
        if r.type != "similar_to"
    }
    similar_pairs = {
        (min(r.source_id, r.target_id), max(r.source_id, r.target_id))
        for r in existing_relations
        if r.type == "similar_to"
    }
    rejected_set = set(rejected_pairs or set())
    for r in existing_relations:
        if r.status == "rejected":
            rejected_set.add((min(r.source_id, r.target_id), max(r.source_id, r.target_id)))

    embedder = get_embedder()
    quotes = [a.get("quote", "") for a in annotations]
    try:
        vecs = embedder.embed(quotes)
    except Exception:
        vecs = None

    candidates: List[Tuple[float, Dict[str, Any], Dict[str, Any], float]] = []

    for i in range(len(annotations)):
        for j in range(i + 1, len(annotations)):
            a1, a2 = annotations[i], annotations[j]
            pair_key = (min(a1["id"], a2["id"]), max(a1["id"], a2["id"]))
            if pair_key in existing_typed or pair_key in rejected_set:
                continue

            l1, l2 = a1.get("label", ""), a2.get("label", "")
            lbl_pair = frozenset({l1, l2})

            # Free filter 1: prune non-relational label pairs (unless connected via similar_to)
            if pair_key not in similar_pairs and lbl_pair in SKIP_LABEL_PAIRS:
                continue

            cos_sim = 0.0
            if vecs is not None and len(vecs) > max(i, j):
                try:
                    cos_sim = float(np.dot(vecs[i], vecs[j]))
                except Exception:
                    cos_sim = 0.0

            # Free filter 2: similarity floor (unless connected via similar_to)
            if vecs is not None and pair_key not in similar_pairs:
                if cos_sim < min_cos_sim:
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

            # Priority 3: High-priority label pairs (e.g. Claim <-> Evidence, Problem <-> Solution)
            if lbl_pair in HIGH_PRIORITY_LABEL_PAIRS:
                score += 3.0

            # Priority 4: Embedding cosine similarity
            score += max(0.0, cos_sim)

            # Natural ordering: earlier passage as source, later as target
            if a1.get("start", 0) <= a2.get("start", 0):
                candidates.append((score, a1, a2, cos_sim))
            else:
                candidates.append((score, a2, a1, cos_sim))

    candidates.sort(key=lambda x: x[0], reverse=True)

    # Ensure diversity across annotations when no seed is specified
    if seed_annotation_id is None and len(candidates) > max_pairs:
        selected: List[Tuple[float, Dict[str, Any], Dict[str, Any], float]] = []
        node_counts: Dict[int, int] = {}
        max_per_node = max(2, max_pairs // 3)

        for item in candidates:
            _, a1, a2, _ = item
            c1 = node_counts.get(a1["id"], 0)
            c2 = node_counts.get(a2["id"], 0)
            if c1 < max_per_node and c2 < max_per_node:
                selected.append(item)
                node_counts[a1["id"]] = c1 + 1
                node_counts[a2["id"]] = c2 + 1
                if len(selected) >= max_pairs:
                    break

        if len(selected) < max_pairs:
            for item in candidates:
                if item not in selected:
                    selected.append(item)
                    if len(selected) >= max_pairs:
                        break

        return [(a1, a2, cs) for _, a1, a2, cs in selected[:max_pairs]]

    return [(a1, a2, cs) for _, a1, a2, cs in candidates[:max_pairs]]


def process_suggest_relations_job(
    job_id: str,
    document_id: int,
    seed_annotation_id: Optional[int] = None,
    target_status: str = "suggested",
    max_pairs_override: Optional[int] = None,
    progress_range: Tuple[int, int] = (10, 100),
    auto_complete_job: bool = True,
    force_heuristic: bool = False,
) -> Dict[str, Any]:
    """Execute LLM relation suggestions using anchor batching, caching, and prune filters."""
    settings = get_settings()
    session_factory = get_session_factory()

    p_start, p_end = progress_range
    if job_id:
        update_job_status(job_id, status="running", progress=p_start)

    # Validate LLM configuration
    llm = None
    if not force_heuristic:
        try:
            llm = get_llm_client()
        except LLMNotConfiguredError as exc:
            if auto_complete_job:
                if job_id:
                    update_job_status(job_id, status="failed", error=str(exc))
                raise
            llm = None

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
        ann_map = {a["id"]: a for a in annotations}
        existing_relations = (
            session.query(Relation)
            .filter(Relation.document_id == document_id)
            .all()
        )
        rejected_rows = (
            session.query(RejectedPair)
            .filter(RejectedPair.document_id == document_id)
            .all()
        )
        rejected_pairs = {(r.ann_id_min, r.ann_id_max) for r in rejected_rows}
        taxonomy_types = TAXONOMY_RELATION_TYPES

    if len(annotations) < 2:
        return {"suggested_count": 0, "message": "At least 2 annotations are required to infer relations."}

    eff_max_pairs = max_pairs_override or settings.max_relation_pairs
    candidate_pairs = select_candidate_pairs(
        annotations=annotations,
        existing_relations=existing_relations,
        max_pairs=eff_max_pairs,
        seed_annotation_id=seed_annotation_id,
        rejected_pairs=rejected_pairs,
        min_cos_sim=settings.min_relation_cos_sim,
    )

    if not candidate_pairs:
        return {"suggested_count": 0, "message": "No new candidate annotation pairs to analyze."}

    if job_id:
        update_job_status(job_id, progress=p_start + int(0.25 * (p_end - p_start)))

    pair_cos_map = {(min(a1["id"], a2["id"]), max(a1["id"], a2["id"])): cs for a1, a2, cs in candidate_pairs}

    # Group candidate partners by anchor (up to 8 candidates per anchor)
    anchor_candidates: Dict[int, List[Dict[str, Any]]] = {}
    assigned_pairs: Set[Tuple[int, int]] = set()

    if seed_annotation_id is not None and seed_annotation_id in ann_map:
        anchor_candidates[seed_annotation_id] = []
        for a1, a2, _ in candidate_pairs:
            pair_key = (min(a1["id"], a2["id"]), max(a1["id"], a2["id"]))
            other = a2 if a1["id"] == seed_annotation_id else a1
            if len(anchor_candidates[seed_annotation_id]) < 8:
                anchor_candidates[seed_annotation_id].append(other)
                assigned_pairs.add(pair_key)

    for a1, a2, _ in candidate_pairs:
        pair_key = (min(a1["id"], a2["id"]), max(a1["id"], a2["id"]))
        if pair_key in assigned_pairs:
            continue
        anchor_id = a1["id"]
        if anchor_id not in anchor_candidates:
            anchor_candidates[anchor_id] = []
        if len(anchor_candidates[anchor_id]) < 8:
            anchor_candidates[anchor_id].append(a2)
            assigned_pairs.add(pair_key)
        else:
            anchor_id_2 = a2["id"]
            if anchor_id_2 not in anchor_candidates:
                anchor_candidates[anchor_id_2] = []
            if len(anchor_candidates[anchor_id_2]) < 8:
                anchor_candidates[anchor_id_2].append(a1)
                assigned_pairs.add(pair_key)

    taxonomy_version = hashlib.md5(",".join(sorted(taxonomy_types)).encode("utf-8")).hexdigest()[:8]

    successful_relations: List[Dict[str, Any]] = []
    failed_pairs: List[Dict[str, Any]] = []
    anchors_to_call: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = []

    # Check database cache for known pairs
    with session_factory() as session:
        for anchor_id, cands in anchor_candidates.items():
            anchor_ann = ann_map[anchor_id]
            uncached_cands = []
            for cand in cands:
                cache_key, is_swapped = make_relation_cache_key(
                    anchor_ann["quote"], anchor_ann.get("label", ""),
                    cand["quote"], cand.get("label", ""),
                    taxonomy_version,
                )
                cached_entry = session.query(RelationCache).filter(RelationCache.cache_key == cache_key).first()
                if cached_entry:
                    try:
                        cached_data = json.loads(cached_entry.result_json)
                        rel_type = cached_data.get("type")
                        if rel_type and rel_type in taxonomy_types:
                            canon_dir = cached_data.get("direction", "forward")
                            if is_swapped:
                                actual_dir = "reverse" if canon_dir == "forward" else "forward"
                            else:
                                actual_dir = canon_dir

                            src_id = cand["id"] if actual_dir == "reverse" else anchor_ann["id"]
                            tgt_id = anchor_ann["id"] if actual_dir == "reverse" else cand["id"]
                            pair_key = (min(anchor_ann["id"], cand["id"]), max(anchor_ann["id"], cand["id"]))
                            cos_sim = pair_cos_map.get(pair_key, 0.0)

                            successful_relations.append({
                                "document_id": document_id,
                                "source_id": src_id,
                                "target_id": tgt_id,
                                "type": rel_type,
                                "reason": cached_data.get("reason", "Retrieved from cache"),
                                "cos_score": cos_sim,
                            })
                    except Exception:
                        uncached_cands.append(cand)
                else:
                    uncached_cands.append(cand)

            if uncached_cands:
                anchors_to_call.append((anchor_ann, uncached_cands))

    semaphore = threading.Semaphore(settings.llm_max_concurrency)

    def evaluate_anchor(anchor_info: Tuple[Dict[str, Any], List[Dict[str, Any]]]) -> None:
        anchor_ann, cands = anchor_info
        cand_map = {c["id"]: c for c in cands}
        cand_labels = {c.get("label", "") for c in cands}

        with session_factory() as session:
            few_shots = _get_few_shot_examples(
                session, document_id, ann_map,
                anchor_ann.get("label", ""), cand_labels, max_examples=3
            )

        prompt = _build_anchor_prompt(anchor_ann, cands, taxonomy_types, few_shots)

        with semaphore:
            try:
                data = llm.complete_json(prompt)
            except Exception as exc:
                for c in cands:
                    failed_pairs.append({
                        "source_id": anchor_ann["id"],
                        "target_id": c["id"],
                        "error": str(exc),
                    })
                return

        rel_items = []
        if isinstance(data, list):
            rel_items = data
        elif isinstance(data, dict):
            if "relations" in data and isinstance(data["relations"], list):
                rel_items = data["relations"]
            elif "candidates" in data and isinstance(data["candidates"], list):
                rel_items = data["candidates"]
            elif "type" in data:
                if len(cands) == 1:
                    item = dict(data)
                    item["candidate_id"] = cands[0]["id"]
                    rel_items = [item]
                else:
                    rel_items = [data]

        new_cached_entries = []

        for item in rel_items:
            cid = item.get("candidate_id")
            if cid is None or cid not in cand_map:
                continue
            cand = cand_map[cid]

            rel_type = item.get("type") or item.get("relation")
            reason = item.get("reason", "")
            direction = item.get("direction", "forward")

            cache_key, is_swapped = make_relation_cache_key(
                anchor_ann["quote"], anchor_ann.get("label", ""),
                cand["quote"], cand.get("label", ""),
                taxonomy_version,
            )

            if is_swapped:
                canon_dir = "reverse" if direction == "forward" else "forward"
            else:
                canon_dir = direction

            cache_payload = {
                "type": rel_type if (rel_type in taxonomy_types) else None,
                "direction": canon_dir,
                "reason": reason,
            }
            new_cached_entries.append((cache_key, json.dumps(cache_payload)))

            if not rel_type or rel_type not in taxonomy_types:
                failed_pairs.append({
                    "source_id": anchor_ann["id"],
                    "target_id": cid,
                    "reason": f"Type '{rel_type}' not in taxonomy or was null",
                })
                continue

            if direction == "reverse":
                src_id, tgt_id = cid, anchor_ann["id"]
            else:
                src_id, tgt_id = anchor_ann["id"], cid

            pair_key = (min(anchor_ann["id"], cid), max(anchor_ann["id"], cid))
            cos_sim = pair_cos_map.get(pair_key, 0.0)

            successful_relations.append({
                "document_id": document_id,
                "source_id": src_id,
                "target_id": tgt_id,
                "type": rel_type,
                "reason": reason,
                "cos_score": cos_sim,
            })

        if new_cached_entries:
            with session_factory() as session:
                for ck, cjson in new_cached_entries:
                    existing = session.query(RelationCache).filter(RelationCache.cache_key == ck).first()
                    if not existing:
                        session.add(RelationCache(cache_key=ck, result_json=cjson))
                try:
                    session.commit()
                except Exception:
                    session.rollback()

    if anchors_to_call and llm is not None:
        with ThreadPoolExecutor(max_workers=settings.llm_max_concurrency) as executor:
            futures = [executor.submit(evaluate_anchor, a_info) for a_info in anchors_to_call]
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception:
                    pass
    elif anchors_to_call and llm is None:
        # Fallback heuristic inference when LLM is offline or not configured
        from backend.app.routes.suggestions import infer_dynamic_relation
        for a_ann, cands in anchors_to_call:
            for c in cands:
                s_id, t_id, dyn_type = infer_dynamic_relation(
                    a_ann.get("label"), c.get("label"), a_ann["id"], c["id"]
                )
                if dyn_type in taxonomy_types:
                    pair_key = (min(a_ann["id"], c["id"]), max(a_ann["id"], c["id"]))
                    cos_sim = pair_cos_map.get(pair_key, 0.0)
                    successful_relations.append({
                        "document_id": document_id,
                        "source_id": s_id,
                        "target_id": t_id,
                        "type": dyn_type,
                        "reason": f"Semantic link established by taxonomy rules (cos_sim={round(cos_sim, 3)})",
                        "cos_score": cos_sim,
                    })

    if job_id:
        update_job_status(job_id, progress=p_start + int(0.85 * (p_end - p_start)))

    # Persist relations (with target_status, e.g. confirmed or suggested)
    with session_factory() as session:
        for item in successful_relations:
            exists = (
                session.query(Relation)
                .filter(
                    Relation.document_id == item["document_id"],
                    Relation.source_id == item["source_id"],
                    Relation.target_id == item["target_id"],
                    Relation.type == item["type"],
                )
                .first()
            )
            if not exists:
                rel = Relation(
                    document_id=item["document_id"],
                    source_id=item["source_id"],
                    target_id=item["target_id"],
                    type=item["type"],
                    status=target_status,
                    reason=item["reason"],
                    cos_score=item.get("cos_score"),
                    version=1,
                )
                session.add(rel)
        session.commit()

    result = {
        "suggested_count": len(successful_relations),
        "created_count": len(successful_relations),
        "failed_pairs_count": len(failed_pairs),
        "failed_pairs": failed_pairs,
    }

    if auto_complete_job:
        if job_id:
            update_job_status(job_id, status="done", progress=100, result=result)
    else:
        if job_id:
            update_job_status(job_id, progress=p_end)

    return result
