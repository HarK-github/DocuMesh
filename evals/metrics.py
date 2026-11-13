"""Deterministic and statistical evaluation metric functions for GraphRAG quality."""

import re
from typing import Dict, Any, List, Set, Tuple


def normalize_whitespace(text: str) -> str:
    """Normalize consecutive whitespace and trim for robust string matching."""
    return " ".join(text.strip().split())


def compute_span_overlap(gold_span: str, context_text: str) -> bool:
    """Check if gold span is present in context text (exact or normalized substring)."""
    norm_gold = normalize_whitespace(gold_span).lower()
    norm_ctx = normalize_whitespace(context_text).lower()
    if not norm_gold:
        return True
    return norm_gold in norm_ctx


def evaluate_retrieval(
    context_text: str,
    gold_spans: List[str],
    retrieved_candidate_texts: List[str],
) -> Dict[str, Any]:
    """Compute gold span recall @ context, and MRR / recall@k on candidate list."""
    if not gold_spans:
        return {
            "gold_spans_total": 0,
            "gold_spans_recalled": 0,
            "gold_span_recall": 1.0,
            "mrr": 1.0,
            "recall_at_1": 1.0,
            "recall_at_3": 1.0,
            "recall_at_5": 1.0,
        }

    recalled_count = 0
    for span in gold_spans:
        if compute_span_overlap(span, context_text):
            recalled_count += 1
    recall = recalled_count / len(gold_spans)

    # Compute MRR across candidate ranked texts
    ranks = []
    for span in gold_spans:
        norm_span = normalize_whitespace(span).lower()
        found_rank = None
        for r_idx, c_text in enumerate(retrieved_candidate_texts, start=1):
            if norm_span in normalize_whitespace(c_text).lower():
                found_rank = r_idx
                break
        ranks.append(found_rank)

    reciprocal_ranks = [1.0 / r for r in ranks if r is not None]
    mrr = sum(reciprocal_ranks) / len(gold_spans) if reciprocal_ranks else 0.0

    r_at_1 = sum(1 for r in ranks if r is not None and r <= 1) / len(gold_spans)
    r_at_3 = sum(1 for r in ranks if r is not None and r <= 3) / len(gold_spans)
    r_at_5 = sum(1 for r in ranks if r is not None and r <= 5) / len(gold_spans)

    return {
        "gold_spans_total": len(gold_spans),
        "gold_spans_recalled": recalled_count,
        "gold_span_recall": round(recall, 4),
        "mrr": round(mrr, 4),
        "recall_at_1": round(r_at_1, 4),
        "recall_at_3": round(r_at_3, 4),
        "recall_at_5": round(r_at_5, 4),
    }


def analyze_context_structure(context_text: str) -> Dict[str, Any]:
    """Measure context size, dangling node IDs, and similar_to share in graph lines."""
    char_len = len(context_text)
    approx_tokens = len(re.findall(r"\S+", context_text))

    # Identify all node IDs defined with text in context:
    # e.g. [a12] (Label) "..." or [s12] text or [r12] ...
    defined_sentence_ids = set(re.findall(r"\[s(\d+)\]", context_text))
    defined_ann_ids = set(re.findall(r"\[a(\d+)\]\s*\([A-Za-z]+\)", context_text))

    # All node IDs referenced inside graph edges:
    # e.g. [r12] a92 --solves--> a89 or s10 --rel--> s12
    edge_lines = re.findall(r"\[r\d+\]\s+([as]\d+)\s+--([a-zA-Z_]+)-->\s+([as]\d+)", context_text)
    
    total_edge_refs = 0
    dangling_refs = 0
    dangling_ids: Set[str] = set()
    similar_to_count = 0

    for src_id, rel_type, tgt_id in edge_lines:
        if rel_type == "similar_to":
            similar_to_count += 1
        
        # Check src
        total_edge_refs += 1
        if src_id.startswith("a"):
            aid = src_id[1:]
            if aid not in defined_ann_ids:
                dangling_refs += 1
                dangling_ids.add(src_id)
        elif src_id.startswith("s"):
            sid = src_id[1:]
            if sid not in defined_sentence_ids:
                dangling_refs += 1
                dangling_ids.add(src_id)

        # Check tgt
        total_edge_refs += 1
        if tgt_id.startswith("a"):
            aid = tgt_id[1:]
            if aid not in defined_ann_ids:
                dangling_refs += 1
                dangling_ids.add(tgt_id)
        elif tgt_id.startswith("s"):
            sid = tgt_id[1:]
            if sid not in defined_sentence_ids:
                dangling_refs += 1
                dangling_ids.add(tgt_id)

    dangling_rate = (dangling_refs / total_edge_refs) if total_edge_refs > 0 else 0.0
    similar_to_share = (similar_to_count / len(edge_lines)) if edge_lines else 0.0

    return {
        "context_chars": char_len,
        "context_approx_tokens": approx_tokens,
        "total_edge_lines": len(edge_lines),
        "similar_to_edges": similar_to_count,
        "similar_to_share": round(similar_to_share, 4),
        "total_edge_refs": total_edge_refs,
        "dangling_refs_count": dangling_refs,
        "dangling_ids": sorted(list(dangling_ids)),
        "dangling_id_rate": round(dangling_rate, 4),
    }


def evaluate_deterministic_citations(
    answer: str,
    active_ids: Set[str],
    is_unanswerable: bool,
) -> Dict[str, Any]:
    """Verify citations in answer: all cited IDs exist, no invented IDs, and abstention check."""
    cited_ids = re.findall(r"\[([sar]\d+)\]", answer)
    total_cited = len(cited_ids)

    valid_cited = [cid for cid in cited_ids if cid in active_ids]
    invented_cited = [cid for cid in cited_ids if cid not in active_ids]

    # Check unanswerable abstention
    abstention_keywords = [
        "couldn't find",
        "could not find",
        "cannot find",
        "not mentioned",
        "does not mention",
        "not state",
        "does not state",
        "not provided",
        "no information",
    ]
    has_abstention_phrase = any(kw in answer.lower() for kw in abstention_keywords)
    abstention_pass = True
    if is_unanswerable:
        abstention_pass = has_abstention_phrase

    citation_accuracy = (len(valid_cited) / total_cited) if total_cited > 0 else (1.0 if not is_unanswerable else 1.0)

    return {
        "total_citations": total_cited,
        "valid_citations_count": len(valid_cited),
        "invented_citations_count": len(invented_cited),
        "invented_citations": invented_cited,
        "citation_accuracy": round(citation_accuracy, 4),
        "abstention_pass": abstention_pass,
        "has_abstention_phrase": has_abstention_phrase,
    }


def evaluate_graph_quality(
    current_nodes: List[Dict[str, Any]],
    current_edges: List[Dict[str, Any]],
    gold_graph: Dict[str, Any],
    min_similarity_floor: float = 0.35,
) -> Dict[str, Any]:
    """Compute node label accuracy, edge precision, duplicate rate, and similarity floor violations."""
    gold_nodes = {n["id"]: n for n in gold_graph.get("nodes", [])}
    gold_edges = gold_graph.get("edges", [])
    duplicate_groups = gold_graph.get("duplicate_groups", [])

    # 1. Node label accuracy
    labeled_correct = 0
    evaluable_nodes = 0
    per_class = {}

    for n in current_nodes:
        nid = f"a{n['id']}" if isinstance(n['id'], int) else str(n['id'])
        if nid in gold_nodes:
            g_node = gold_nodes[nid]
            expected = g_node.get("expected_label")
            actual = n.get("label")
            evaluable_nodes += 1
            if expected == actual:
                labeled_correct += 1
            if expected:
                cls_stat = per_class.setdefault(expected, {"correct": 0, "total": 0})
                cls_stat["total"] += 1
                if expected == actual:
                    cls_stat["correct"] += 1

    node_acc = (labeled_correct / evaluable_nodes) if evaluable_nodes > 0 else 0.0

    # 2. Edge precision & floor violations
    valid_gold_pairs = {}
    for ge in gold_edges:
        key = (ge["source_id"], ge["target_id"])
        valid_gold_pairs[key] = ge

    valid_edge_count = 0
    invalid_edges = []
    edges_below_floor_confirmed = 0

    for ce in current_edges:
        src = f"a{ce['source_id']}" if isinstance(ce['source_id'], int) else str(ce['source_id'])
        tgt = f"a{ce['target_id']}" if isinstance(ce['target_id'], int) else str(ce['target_id'])
        rel_type = ce.get("type") or ce.get("relation_type")
        status = ce.get("status", "confirmed")
        cos_score = ce.get("cos_score") or ce.get("score") or 0.0

        # Check floor rule
        if rel_type != "similar_to" and status == "confirmed" and cos_score is not None:
            if 0 < cos_score < min_similarity_floor and "reason" in ce and "taxonomy rules" in str(ce["reason"]):
                edges_below_floor_confirmed += 1

        # Check against gold
        pair_key = (src, tgt)
        if pair_key in valid_gold_pairs:
            g_edge = valid_gold_pairs[pair_key]
            if g_edge.get("is_valid"):
                valid_edge_count += 1
            else:
                invalid_edges.append({
                    "source": src,
                    "target": tgt,
                    "type": rel_type,
                    "reason": g_edge.get("rationale", "Marked invalid in gold dataset"),
                })
        else:
            # If not in gold, check if similar_to or spurious
            if rel_type == "similar_to":
                invalid_edges.append({
                    "source": src,
                    "target": tgt,
                    "type": rel_type,
                    "reason": "similar_to non-semantic edge",
                })
            else:
                # Heuristic: LLM typed edges with detailed reason are considered plausible
                if ce.get("reason") and "taxonomy rules" not in str(ce.get("reason")):
                    valid_edge_count += 1
                else:
                    invalid_edges.append({
                        "source": src,
                        "target": tgt,
                        "type": rel_type,
                        "reason": f"Spurious taxonomy edge (score={cos_score})",
                    })

    total_edges = len(current_edges)
    edge_precision = (valid_edge_count / total_edges) if total_edges > 0 else 0.0

    # 3. Duplicate node rate
    # Check if duplicate groups are merged or present as separate standalone nodes
    present_node_ids = {f"a{n['id']}" if isinstance(n['id'], int) else str(n['id']) for n in current_nodes}
    unmerged_duplicate_pairs = 0
    total_duplicate_pairs = 0

    for group in duplicate_groups:
        total_duplicate_pairs += 1
        present_in_group = [nid for nid in group if nid in present_node_ids]
        if len(present_in_group) > 1:
            unmerged_duplicate_pairs += 1

    duplicate_rate = (unmerged_duplicate_pairs / total_duplicate_pairs) if total_duplicate_pairs > 0 else 0.0

    return {
        "node_count": len(current_nodes),
        "node_label_accuracy": round(node_acc, 4),
        "per_class_accuracy": per_class,
        "total_edges": total_edges,
        "valid_edges": valid_edge_count,
        "invalid_edges_count": len(invalid_edges),
        "invalid_edges": invalid_edges[:10],
        "edge_precision": round(edge_precision, 4),
        "edges_below_floor_confirmed": edges_below_floor_confirmed,
        "duplicate_rate": round(duplicate_rate, 4),
    }


def evaluate_highlight_quality(
    current_annotations: List[Dict[str, Any]],
    gold_highlights: Dict[str, Any],
    clean_text: str,
) -> Dict[str, Any]:
    """Measure key-idea coverage, must-not-highlight violations, density, and boundary quality."""
    must_highlight = gold_highlights.get("must_highlight", [])
    must_not_highlight = gold_highlights.get("must_not_highlight", [])

    total_words = len(re.findall(r"\S+", clean_text)) if clean_text else 1
    total_sentences = max(1, len(re.split(r"[.!?]+", clean_text)))

    ann_quotes = [normalize_whitespace(a.get("quote", "")).lower() for a in current_annotations]

    # 1. Key idea coverage (Recall)
    covered_key_ideas = 0
    for ki in must_highlight:
        ki_norm = normalize_whitespace(ki["text"]).lower()
        if any(ki_norm in aq or aq in ki_norm for aq in ann_quotes):
            covered_key_ideas += 1

    key_idea_recall = (covered_key_ideas / len(must_highlight)) if must_highlight else 1.0

    # 2. Must not highlight violations (Headers, bylines, titles)
    forbidden_violations = 0
    violation_samples = []
    for f in must_not_highlight:
        f_norm = normalize_whitespace(f["text"]).lower()
        for a in current_annotations:
            aq = normalize_whitespace(a.get("quote", "")).lower()
            if f_norm in aq or aq in f_norm:
                forbidden_violations += 1
                violation_samples.append({
                    "id": a.get("id"),
                    "quote": a.get("quote"),
                    "reason": f.get("reason"),
                })
                break

    # 3. Density
    density_per_100_words = (len(current_annotations) / total_words) * 100.0
    percent_sentences_highlighted = (len(current_annotations) / total_sentences) * 100.0

    # 4. Boundary quality (% ending in punctuation or self-contained)
    clean_boundaries = 0
    for a in current_annotations:
        quote = a.get("quote", "").strip()
        if quote and quote[-1] in ".!?'\"”":
            clean_boundaries += 1
    boundary_quality = (clean_boundaries / len(current_annotations)) if current_annotations else 1.0

    return {
        "annotations_count": len(current_annotations),
        "key_ideas_total": len(must_highlight),
        "key_ideas_covered": covered_key_ideas,
        "key_idea_recall": round(key_idea_recall, 4),
        "forbidden_highlights_count": forbidden_violations,
        "forbidden_samples": violation_samples,
        "density_per_100_words": round(density_per_100_words, 2),
        "percent_sentences_highlighted": round(percent_sentences_highlighted, 2),
        "boundary_quality": round(boundary_quality, 4),
    }
