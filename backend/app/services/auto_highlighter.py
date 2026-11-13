"""Automated full-document top-down highlight and relationship knowledge graph builder."""

import logging
from typing import Dict, Any, Optional
import numpy as np
from backend.app.settings import get_settings
from backend.app.db import get_session_factory
from backend.app.models import Document, Sentence, Annotation, Suggestion
from backend.app.taxonomy import TAXONOMY_LABELS
from backend.app.services.clean import snap_to_word_boundaries
from backend.app.services.jobs import update_job_status
from backend.app.services.llm import get_llm_client, LLMNotConfiguredError
from backend.app.services.embedder import get_embedder
from backend.app.services.relation_suggester import process_suggest_relations_job
from backend.app.services.ranker import intervals_overlap

import re

logger = logging.getLogger(__name__)


def is_forbidden_header_or_byline(text: str) -> bool:
    """Return True if the text is document front matter, title, byline, page marker, or section header."""
    t = text.strip()
    if not t or len(t) < 5:
        return True
    # All uppercase titles or short headers (e.g. "RESEARCH ARTICLE", "ABSTRACT", "INTRODUCTION")
    if t.isupper() and len(t.split()) <= 12 and not any(char in t for char in ".!?"):
        return True
    # Document title + author bylines (e.g. "By Author Name", "PAPER TITLE By Author")
    if re.match(r"^by\s+[A-Za-z\.\s,]+$", t, re.IGNORECASE):
        return True
    if re.match(r"^[A-Z0-9\s,:\-]{3,80}\s+by\s+[A-Z][a-zA-Z\.\s,]+$", t, re.IGNORECASE):
        return True
    # Standalone section numbers and titles: e.g. "1. Introduction", "2. Related Work", "Section 3.1"
    if re.match(r"^(section\s+)?(\d+(\.\d+)*|[IVXLCDM]+)\.?\s+[A-Za-z\s\-_:]{2,50}$", t, re.IGNORECASE):
        return True
    # Markdown or text header syntax
    if re.match(r"^#{1,6}\s+", t):
        return True
    # Page numbers or footer markers (e.g. "Page 1 of 5", "1 / 10", "Page 2")
    if re.match(r"^(page\s+\d+(\s+of\s+\d+)?|\d+\s*/\s*\d+)$", t, re.IGNORECASE):
        return True
    return False


def strip_section_header_prefix(text: str) -> tuple[str, int]:
    """If text starts with a section header like '1. Section Title Sentence...', strip it and return (stripped_text, offset_delta)."""
    match = re.match(r"^((?:(?:section\s+)?(?:\d+(?:\.\d+)*|[IVXLCDM]+)\.?\s+[A-Za-z\s\-_:]{2,40}\s+))([A-Z].*)$", text)
    if match:
        prefix = match.group(1)
        remainder = match.group(2)
        if len(remainder.split()) >= 3:
            return remainder, len(prefix)
    return text, 0


LABEL_PROTOTYPES = {
    "Claim": "We argue, claim, and hypothesize that this fundamental principle holds true in general.",
    "Evidence": "Empirical experiments, quantitative data, benchmark measurements, and observed statistics demonstrate this.",
    "Definition": "We define this concept, term, or formal system as follows.",
    "Method": "The procedure, experimental method, algorithm, and training protocol were implemented as follows.",
    "Result": "The experimental results, benchmark evaluation scores, and accuracy findings show significant improvement.",
    "Problem": "A major open problem, challenge, limitation, difficulty, or research gap remains unresolved.",
    "Solution": "We propose a novel framework, architectural solution, and algorithm that effectively solves this issue.",
}



def process_auto_highlight_job(
    job_id: str,
    document_id: int,
    mode: str = "llm",
) -> Dict[str, Any]:
    """Execute end-to-end sequential top-down document annotation sweep and full graph construction."""
    settings = get_settings()
    session_factory = get_session_factory()

    update_job_status(job_id, status="running", progress=5)

    with session_factory() as session:
        doc = session.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")
        if not doc.clean_text:
            raise ValueError(f"Document {document_id} clean_text is empty or not yet processed")

        clean_text = doc.clean_text
        labels = TAXONOMY_LABELS

        # 1. Existing annotations to skip covered ranges
        existing_anns = (
            session.query(Annotation)
            .filter(Annotation.document_id == document_id)
            .all()
        )
        existing_intervals = [(a.start, a.end) for a in existing_anns]

        # 2. Sentences ordered by idx (document order)
        sentence_rows = (
            session.query(Sentence)
            .filter(Sentence.document_id == document_id)
            .order_by(Sentence.idx.asc())
            .all()
        )
        sentences_to_process = []
        for s in sentence_rows:
            # Skip if overlapping existing annotation
            if any(intervals_overlap(s.start, s.end, es, ee) for es, ee in existing_intervals):
                continue
            s_quote = clean_text[s.start:s.end].strip()
            # Skip very short fragments (< 15 chars) and headers/bylines
            if len(s_quote) < 15 or is_forbidden_header_or_byline(s_quote):
                continue
            sentences_to_process.append({
                "id": s.id,
                "idx": s.idx,
                "start": s.start,
                "end": s.end,
                "page": s.page,
                "text": s_quote,
                "embedding": s.embedding,
            })

    # ==========================================
    # PHASE A: Sequential Sentence Classification
    # ==========================================
    update_job_status(job_id, progress=10)

    use_llm = (mode == "llm")
    llm = None
    if use_llm:
        try:
            llm = get_llm_client()
        except LLMNotConfiguredError:
            use_llm = False

    batch_size = max(5, settings.auto_highlight_batch_size)
    created_annotations = []
    total_to_process = len(sentences_to_process)
    proto_threshold = getattr(settings, "auto_highlight_proto_threshold", 0.18)
    llm_success_chunks = 0
    llm_failed_chunks = 0

    if total_to_process > 0:
        chunk_count = (total_to_process + batch_size - 1) // batch_size

        # Precompute prototype vectors if using embedding mode
        proto_vectors = {}
        embedder = None
        if not use_llm:
            embedder = get_embedder()
            proto_texts = [LABEL_PROTOTYPES.get(l, l) for l in labels]
            proto_matrix = embedder.embed(proto_texts)
            for i, l in enumerate(labels):
                if i < len(proto_matrix):
                    proto_vectors[l] = proto_matrix[i]

        for chunk_idx in range(chunk_count):
            start_i = chunk_idx * batch_size
            chunk = sentences_to_process[start_i : start_i + batch_size]

            classifications: Dict[int, Optional[str]] = {}

            if use_llm and llm:
                # Build batched sentence prompt
                sent_lines = []
                for s in chunk:
                    sent_lines.append(f'[{s["idx"]}] "{s["text"]}"')
                sentences_block = "\n".join(sent_lines)

                prompt = f"""You are an expert document analyst performing full-document taxonomy classification.
Classify each numbered sentence into exactly one label from the taxonomy, or null if the sentence is filler, an organizational transition, header/footer, reference citation, or non-substantive.

Permitted Taxonomy Labels:
{labels}

Classification Guidelines:
- "Claim": Main assertion, hypothesis, central argument, or finding statement.
- "Evidence": Empirical data, factual proof, quotation, statistic, or experimental measurement supporting a claim.
- "Definition": Formal naming or conceptual definition of a term, system, mechanism, or coined framework.
- "Method": Description of algorithmic step, experimental procedure, technique, or protocol of inquiry.
- "Result": Quantitative outcome, observed performance, theorem proof, or benchmark score.
- "Problem": Research gap, deficiency, limitation, paradox, objection, or open question addressed. Do NOT label introducing a coined concept as Problem simply because the sentence mentions the word 'problem'.
- "Solution": System design, proposal, resolution, algorithm, or theorem solving the problem.
- null: Document title, author byline, section headers (e.g. '1. Introduction', '2. Methodology'), page headers/footers, acknowledgments, transitional commentary, or reference citations. These MUST be returned as null.

Few-Shot Examples:
- "ATTENTION IS ALL YOU NEED By Ashish Vaswani et al." -> null (Document title and author byline)
- "1. Introduction and Related Work" -> null (Section header)
- "Existing sequence transduction models rely heavily on complex recurrent or convolutional neural networks." -> "Problem" (Describes existing limitations and research gap)
- "We define an attention function as mapping a query and a set of key-value pairs to an output." -> "Definition" (Formal conceptual definition of a mechanism)
- "The Transformer allows for significantly more parallelization and reaches a new state of the art in translation quality." -> "Result" (Experimental finding and empirical score)
- "We evaluated the model on the WMT 2014 English-to-German translation task using standard BLEU metrics." -> "Method" (Procedural experimental protocol)
- "Table 1 shows that our model achieves 28.4 BLEU, outperforming previous ensembles by over 2.0 BLEU." -> "Evidence" (Empirical quantitative proof supporting the claim)
- "We propose the Transformer, a model architecture eschewing recurrence and entirely relying on self-attention." -> "Solution" (Architectural solution addressing the problem)

Instructions:
1. For each sentence, assign a label or null.
2. Return ONLY a valid JSON object in this format:
{{
  "classifications": [
    {{"idx": <sentence_idx>, "label": "one_of_the_labels_or_null"}}
  ]
}}

Sentences to classify:
{sentences_block}
"""
                try:
                    res_data = llm.complete_json(prompt)
                    items = []
                    if isinstance(res_data, dict):
                        items = res_data.get("classifications") or res_data.get("sentences") or []
                    elif isinstance(res_data, list):
                        items = res_data

                    for item in items:
                        if isinstance(item, dict) and "idx" in item:
                            c_label = item.get("label")
                            if c_label in labels:
                                classifications[item["idx"]] = c_label
                except Exception as exc:
                    logger.warning(
                        "LLM auto-highlight chunk %d classification failed: %s. Falling back to embedding prototype classification.",
                        chunk_idx,
                        exc,
                    )
                    llm_failed_chunks += 1
                else:
                    if classifications:
                        llm_success_chunks += 1

            # Embedding fallback for unclassified sentences in chunk
            if not use_llm or (use_llm and len(classifications) == 0):
                if embedder is None:
                    embedder = get_embedder()
                if not proto_vectors:
                    proto_texts = [LABEL_PROTOTYPES.get(l, l) for l in labels]
                    proto_matrix = embedder.embed(proto_texts)
                    for i, l in enumerate(labels):
                        if i < len(proto_matrix):
                            proto_vectors[l] = proto_matrix[i]

                for s in chunk:
                    if s["idx"] in classifications:
                        continue
                    s_vec = None
                    if s["embedding"] is not None:
                        try:
                            s_vec = np.asarray(s["embedding"], dtype=np.float32)
                        except Exception:
                            s_vec = None
                    if s_vec is None:
                        try:
                            s_vec = embedder.embed([s["text"]])[0]
                        except Exception:
                            s_vec = None

                    if s_vec is not None:
                        best_sim = -1.0
                        best_label = None
                        for l_name, p_vec in proto_vectors.items():
                            sim = float(np.dot(s_vec, p_vec))
                            if sim > best_sim:
                                best_sim = sim
                                best_label = l_name

                        if best_sim >= proto_threshold:
                            classifications[s["idx"]] = best_label

            # Persist annotations for classified sentences in this chunk
            with session_factory() as session:
                for s in chunk:
                    if is_forbidden_header_or_byline(s["text"]):
                        continue
                    chosen_label = classifications.get(s["idx"])
                    if not chosen_label or chosen_label not in labels:
                        continue

                    # Snap boundaries
                    snapped_s, snapped_e = snap_to_word_boundaries(clean_text, s["start"], s["end"])
                    quote_text = clean_text[snapped_s:snapped_e].strip()
                    if not quote_text:
                        continue

                    # Strip any leading section header prefix (e.g. "1. Section Name ")
                    stripped_quote, offset_delta = strip_section_header_prefix(quote_text)
                    if offset_delta > 0:
                        snapped_s += offset_delta
                        quote_text = stripped_quote

                    # Check duplicate
                    exists = (
                        session.query(Annotation)
                        .filter(
                            Annotation.document_id == document_id,
                            Annotation.start == snapped_s,
                            Annotation.end == snapped_e,
                            Annotation.label == chosen_label,
                        )
                        .first()
                    )
                    if not exists:
                        ann_obj = Annotation(
                            document_id=document_id,
                            start=snapped_s,
                            end=snapped_e,
                            quote=quote_text,
                            label=chosen_label,
                            note="Auto-highlighted",
                            version=1,
                        )
                        session.add(ann_obj)
                        session.flush()
                        created_annotations.append(ann_obj.id)

                        # Supersede any overlapping pending suggestions
                        overlapping_sugs = (
                            session.query(Suggestion)
                            .filter(
                                Suggestion.document_id == document_id,
                                Suggestion.status == "pending",
                            )
                            .all()
                        )
                        for sug in overlapping_sugs:
                            if sug.sentence:
                                if intervals_overlap(sug.sentence.start, sug.sentence.end, snapped_s, snapped_e):
                                    sug.status = "superseded"

                session.commit()

            # Update progress between 10% and 55%
            chunk_prog = 10 + int(45 * (chunk_idx + 1) / chunk_count)
            update_job_status(job_id, progress=min(55, chunk_prog))

    # ==========================================
    # PHASE B: Graph Relationship Construction
    # ==========================================
    update_job_status(job_id, progress=55)

    # Determine effective mode and whether heuristic relation suggestion should be forced
    llm_completely_failed = (use_llm and llm_failed_chunks > 0 and llm_success_chunks == 0)
    if llm_completely_failed:
        effective_mode = "embedding_fallback"
        should_force_heuristic = True
    elif use_llm:
        effective_mode = "llm"
        should_force_heuristic = False
    else:
        effective_mode = "embedding"
        should_force_heuristic = True

    rel_res = process_suggest_relations_job(
        job_id=job_id,
        document_id=document_id,
        seed_annotation_id=None,
        target_status="confirmed",
        max_pairs_override=settings.auto_highlight_max_pairs,
        progress_range=(55, 95),
        auto_complete_job=False,
        force_heuristic=should_force_heuristic,
    )

    created_relations_count = rel_res.get("created_count", 0)

    final_result = {
        "annotations_created": len(created_annotations),
        "relations_created": created_relations_count,
        "mode": effective_mode,
    }

    update_job_status(job_id, status="done", progress=100, result=final_result)
    return final_result

