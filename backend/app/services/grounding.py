"""Verbatim evidence grounding and character offset mapping service."""

import re
from typing import List, Dict, Any, Optional, Tuple


def normalize_ws(text: str) -> str:
    """Normalize whitespace: replace sequences of whitespace with a single space and strip."""
    return re.sub(r"\s+", " ", text).strip()


def is_quote_grounded(evidence_quote: str, chunk_text: str) -> bool:
    """Check if normalized evidence quote is an exact substring of normalized chunk text."""
    if not evidence_quote or not chunk_text:
        return False
    norm_quote = normalize_ws(evidence_quote)
    norm_chunk = normalize_ws(chunk_text)
    return norm_quote in norm_chunk


def map_quote_to_offsets(
    clean_text: str,
    chunk_start: int,
    chunk_end: int,
    evidence_quote: str,
    sentences: Optional[List[Dict[str, Any]]] = None,
    ref_sentence_idx: Optional[int] = None,
) -> Optional[Tuple[int, int]]:
    """Map normalized evidence quote back to exact [start, end) offsets in clean_text.

    Uses a whitespace-tolerant regex with deterministic multi-match disambiguation:
    1. Prioritize match overlapping or closest to ref_sentence_idx (if provided).
    2. Fall back to first occurrence strictly bounded by [chunk_start, chunk_end].
    """
    if not is_quote_grounded(evidence_quote, clean_text[chunk_start:chunk_end]):
        return None

    words = normalize_ws(evidence_quote).split(" ")
    pattern = re.compile(r"\s+".join(re.escape(w) for w in words), re.IGNORECASE)
    chunk_slice = clean_text[chunk_start:chunk_end]

    matches = list(pattern.finditer(chunk_slice))
    if not matches:
        return None

    candidate_spans = []
    for m in matches:
        abs_start = chunk_start + m.start()
        abs_end = chunk_start + m.end()
        if abs_start >= chunk_start and abs_end <= chunk_end:
            candidate_spans.append((abs_start, abs_end))

    if not candidate_spans:
        return None

    if len(candidate_spans) == 1 or ref_sentence_idx is None or not sentences:
        return candidate_spans[0]

    # Multi-match disambiguation: select match closest to ref_sentence_idx
    best_span = candidate_spans[0]
    min_dist = float("inf")

    for span in candidate_spans:
        covering_sent = find_sentence_for_span(sentences, span[0], span[1])
        if covering_sent:
            dist = abs(int(covering_sent["idx"]) - ref_sentence_idx)
            if dist < min_dist:
                min_dist = dist
                best_span = span

    return best_span


def find_sentence_for_span(
    sentences: List[Dict[str, Any]], start: int, end: int
) -> Optional[Dict[str, Any]]:
    """Find the sentence that best covers or overlaps the given character span."""
    if not sentences:
        return None

    # Check for direct containment
    for s in sentences:
        if s["start"] <= start and s["end"] >= end:
            return s

    # Check for overlap
    best_sent = None
    max_overlap = -1
    for s in sentences:
        overlap = max(0, min(end, s["end"]) - max(start, s["start"]))
        if overlap > max_overlap:
            max_overlap = overlap
            best_sent = s

    if max_overlap > 0:
        return best_sent

    # Fallback to closest sentence by distance to start
    return min(sentences, key=lambda s: abs(s["start"] - start))


def verify_endpoint_proximity(
    source_node_type: str,
    source_name: str,
    target_node_type: str,
    target_name: str,
    evidence_sentence_idx: int,
    sentences: List[Dict[str, Any]],
) -> bool:
    """Verify endpoint proximity rules according to DocuMesh GraphRAG specification.

    - Claim/Result endpoints: Proximity check is waived because the claim's own span is evidence.
    - Concept endpoints: Both endpoints must appear in the evidence sentence or within +-1 adjacent sentence.
    """
    claim_types = {"Claim", "Result"}

    source_waived = source_node_type in claim_types
    target_waived = target_node_type in claim_types

    if source_waived and target_waived:
        return True

    # Identify sentence window: [evidence_sentence_idx - 1, evidence_sentence_idx + 1]
    window_sentences = [
        s for s in sentences
        if abs(int(s["idx"]) - evidence_sentence_idx) <= 1
    ]
    if not window_sentences:
        return False

    window_text = " ".join(s.get("text", "") for s in window_sentences).lower()
    norm_window = normalize_ws(window_text)

    if not source_waived:
        norm_source = normalize_ws(source_name).lower()
        if norm_source not in norm_window:
            return False

    if not target_waived:
        norm_target = normalize_ws(target_name).lower()
        if norm_target not in norm_window:
            return False

    return True
