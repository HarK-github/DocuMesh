"""Evaluation runner for GraphRAG quality (Retrieval, Answer, Graph, Highlights)."""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from backend.app.db import get_session_factory
from backend.app.models import Document, Annotation, Relation, Sentence
from backend.app.services.chat_context import (
    CHAT_SYSTEM_PROMPT,
    retrieve_chat_context,
    build_chat_context,
    validate_citations,
)
from backend.app.services.llm import get_llm_client
from backend.app.settings import get_settings
from evals.metrics import (
    evaluate_retrieval,
    analyze_context_structure,
    evaluate_deterministic_citations,
    evaluate_graph_quality,
    evaluate_highlight_quality,
)

logger = logging.getLogger(__name__)


def load_judge_rubric() -> str:
    """Load judge rubric prompt from markdown file."""
    rubric_path = Path(__file__).parent / "judge_prompt.md"
    if rubric_path.exists():
        return rubric_path.read_text(encoding="utf-8")
    return "You are an impartial judge. Score the answer 1-5 for correctness, faithfulness, citation_support, completeness."


def parse_judge_json(response_text: str) -> Dict[str, Any]:
    """Extract and parse structured JSON from LLM judge response."""
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        # Fallback regex extraction of score numbers
        c_score = re.search(r'"correctness":\s*\{\s*"score":\s*([1-5])', cleaned)
        f_score = re.search(r'"faithfulness":\s*\{\s*"score":\s*([1-5])', cleaned)
        cit_score = re.search(r'"citation_support":\s*\{\s*"score":\s*([1-5])', cleaned)
        comp_score = re.search(r'"completeness":\s*\{\s*"score":\s*([1-5])', cleaned)
        abs_match = re.search(r'"abstention":\s*\{\s*"verdict":\s*"([^"]+)"', cleaned)
        return {
            "correctness": {"score": int(c_score.group(1)) if c_score else 3, "reasons": "Parsed from regex"},
            "faithfulness": {"score": int(f_score.group(1)) if f_score else 3, "reasons": "Parsed from regex"},
            "citation_support": {"score": int(cit_score.group(1)) if cit_score else 3, "reasons": "Parsed from regex"},
            "completeness": {"score": int(comp_score.group(1)) if comp_score else 3, "reasons": "Parsed from regex"},
            "abstention": {"verdict": abs_match.group(1) if abs_match else "n/a", "reasons": "Parsed from regex"},
        }


def call_judge(
    llm,
    rubric: str,
    question: str,
    answer: str,
    context_text: str,
    gold_answer: str,
    is_unanswerable: bool,
) -> Dict[str, Any]:
    """Execute LLM judge evaluation against the structured rubric."""
    prompt = f"""{rubric}

=== EVALUATION TASK ===
Question: {question}
Question Type: {"Unanswerable" if is_unanswerable else "Answerable"}
Gold Answer: {gold_answer}

Generated Answer Under Evaluation:
{answer}

Context Text Provided to Generator:
{context_text}

Instructions:
Evaluate the Generated Answer using ONLY the rubric rules.
Return ONLY valid JSON matching the schema in the rubric.
"""
    messages = [
        {"role": "system", "content": "You are an impartial evaluation judge. Output ONLY valid JSON."},
        {"role": "user", "content": prompt},
    ]
    resp = llm.complete(messages)
    return parse_judge_json(resp)


def run_document_evaluation(
    document_id: int,
    out_dir: str = "evals/results",
    tag: str = "eval",
    judge_repeats: int = 3,
    save_contexts: bool = True,
) -> Dict[str, Any]:
    """Execute complete end-to-end evaluation suite for a document."""
    settings = get_settings()
    llm = get_llm_client()
    rubric = load_judge_rubric()
    session_factory = get_session_factory()

    data_dir = Path(__file__).parent / "data"
    qa_path = data_dir / f"doc_{document_id}_chat_qa.json"
    graph_path = data_dir / f"doc_{document_id}_graph_gold.json"
    highlight_path = data_dir / f"doc_{document_id}_highlight_gold.json"

    if not qa_path.exists():
        raise FileNotFoundError(f"QA dataset not found: {qa_path}")
    if not graph_path.exists():
        raise FileNotFoundError(f"Graph gold dataset not found: {graph_path}")
    if not highlight_path.exists():
        raise FileNotFoundError(f"Highlight gold dataset not found: {highlight_path}")

    with open(qa_path, "r", encoding="utf-8") as f:
        qa_items = json.load(f)
    with open(graph_path, "r", encoding="utf-8") as f:
        graph_gold = json.load(f)
    with open(highlight_path, "r", encoding="utf-8") as f:
        highlight_gold = json.load(f)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    contexts_dir = out_path / "contexts"
    if save_contexts:
        contexts_dir.mkdir(parents=True, exist_ok=True)

    with session_factory() as session:
        doc = session.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found in database")
        clean_text = doc.clean_text or ""
        ann_rows = session.query(Annotation).filter(Annotation.document_id == document_id).all()
        rel_rows = session.query(Relation).filter(Relation.document_id == document_id).all()

        current_annotations = [
            {"id": a.id, "quote": a.quote, "label": a.label, "start": a.start, "end": a.end, "note": a.note}
            for a in ann_rows
        ]
        current_relations = [
            {
                "id": r.id,
                "source_id": r.source_id,
                "target_id": r.target_id,
                "type": r.type,
                "status": r.status,
                "reason": r.reason,
                "cos_score": r.cos_score,
            }
            for r in rel_rows
        ]

    # 1. Graph Quality Evaluation
    graph_metrics = evaluate_graph_quality(
        current_nodes=current_annotations,
        current_edges=current_relations,
        gold_graph=graph_gold,
        min_similarity_floor=settings.min_relation_cos_sim or 0.35,
    )

    # 2. Highlight Quality Evaluation
    highlight_metrics = evaluate_highlight_quality(
        current_annotations=current_annotations,
        gold_highlights=highlight_gold,
        clean_text=clean_text,
    )

    # 3. Chat QA & Retrieval Evaluation
    qa_results = []
    
    for q_item in qa_items:
        qid = q_item["id"]
        q_text = q_item["question"]
        gold_ans = q_item["gold_answer"]
        gold_spans = q_item.get("gold_spans", [])
        q_type = q_item.get("type", "factual")
        split = q_item.get("split", "dev")
        is_unanswerable = (q_type == "unanswerable")

        # Execute retrieval using unmodified app service
        with session_factory() as session:
            retrieval = retrieve_chat_context(
                db=session,
                document_id=document_id,
                question=q_text,
                settings=settings,
                mode="hybrid",
            )
            formatted = build_chat_context(retrieval, max_chars=settings.chat_max_context_chars)

        context_text = formatted.context_text
        active_ids = formatted.active_ids

        # Candidate texts for MRR
        candidate_texts = [s["text"] for s in retrieval.sentences] + [a["quote"] for a in retrieval.annotations]

        # Retrieval metrics
        ret_metrics = evaluate_retrieval(context_text, gold_spans, candidate_texts)
        ctx_struct = analyze_context_structure(context_text)

        # Log system prompt and context to file
        system_content = f"{CHAT_SYSTEM_PROMPT}\n\n=== Context (hybrid mode) ===\n{context_text}"
        if save_contexts:
            ctx_file = contexts_dir / f"{tag}_{qid}.txt"
            with open(ctx_file, "w", encoding="utf-8") as f:
                f.write(f"QUESTION: {q_text}\nTYPE: {q_type}\nSPLIT: {split}\n\n=== SYSTEM PROMPT + CONTEXT ===\n{system_content}\n")

        # Generate answer from LLM
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": q_text},
        ]
        start_t = time.time()
        answer = llm.complete(messages)
        latency_s = round(time.time() - start_t, 2)

        # Deterministic citation checks
        det_cit = evaluate_deterministic_citations(answer, active_ids, is_unanswerable)

        # LLM Judge evaluation (run judge_repeats times for mean & spread)
        judge_runs = []
        for r_idx in range(judge_repeats):
            j_eval = call_judge(
                llm=llm,
                rubric=rubric,
                question=q_text,
                answer=answer,
                context_text=context_text,
                gold_answer=gold_ans,
                is_unanswerable=is_unanswerable,
            )
            judge_runs.append(j_eval)

        # Compute mean and spread
        c_scores = [jr.get("correctness", {}).get("score", 3) for jr in judge_runs]
        f_scores = [jr.get("faithfulness", {}).get("score", 3) for jr in judge_runs]
        cit_scores = [jr.get("citation_support", {}).get("score", 3) for jr in judge_runs]
        comp_scores = [jr.get("completeness", {}).get("score", 3) for jr in judge_runs]
        abs_verdicts = [jr.get("abstention", {}).get("verdict", "n/a") for jr in judge_runs]

        qa_eval = {
            "id": qid,
            "question": q_text,
            "type": q_type,
            "split": split,
            "answer": answer,
            "latency_seconds": latency_s,
            "retrieval": ret_metrics,
            "context_structure": ctx_struct,
            "deterministic_citations": det_cit,
            "judge": {
                "correctness_mean": round(float(np.mean(c_scores)), 2),
                "correctness_spread": round(float(np.ptp(c_scores)), 2),
                "faithfulness_mean": round(float(np.mean(f_scores)), 2),
                "faithfulness_spread": round(float(np.ptp(f_scores)), 2),
                "citation_support_mean": round(float(np.mean(cit_scores)), 2),
                "completeness_mean": round(float(np.mean(comp_scores)), 2),
                "abstention_verdict": abs_verdicts[0],
                "judge_reasons": judge_runs[0].get("correctness", {}).get("reasons", ""),
                "all_runs": judge_runs,
            },
        }
        qa_results.append(qa_eval)

    # 4. Aggregations across dev, held_out, and overall
    def aggregate_split(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not items:
            return {}
        answerable = [it for it in items if it["type"] != "unanswerable"]
        unanswerable = [it for it in items if it["type"] == "unanswerable"]

        mean_span_recall = np.mean([it["retrieval"]["gold_span_recall"] for it in answerable]) if answerable else 1.0
        mean_mrr = np.mean([it["retrieval"]["mrr"] for it in answerable]) if answerable else 1.0
        mean_dangling_rate = np.mean([it["context_structure"]["dangling_id_rate"] for it in items])
        mean_similar_to_share = np.mean([it["context_structure"]["similar_to_share"] for it in items])

        mean_correctness = np.mean([it["judge"]["correctness_mean"] for it in items])
        mean_faithfulness = np.mean([it["judge"]["faithfulness_mean"] for it in items])
        mean_citation_support = np.mean([it["judge"]["citation_support_mean"] for it in items])
        mean_completeness = np.mean([it["judge"]["completeness_mean"] for it in items])

        abs_correct = sum(1 for it in unanswerable if it["deterministic_citations"]["abstention_pass"])
        abstention_rate = (abs_correct / len(unanswerable)) if unanswerable else 1.0

        invented_cits_total = sum(it["deterministic_citations"]["invented_citations_count"] for it in items)

        return {
            "count": len(items),
            "gold_span_recall": round(float(mean_span_recall), 4),
            "mrr": round(float(mean_mrr), 4),
            "dangling_id_rate": round(float(mean_dangling_rate), 4),
            "similar_to_share": round(float(mean_similar_to_share), 4),
            "correctness": round(float(mean_correctness), 2),
            "faithfulness": round(float(mean_faithfulness), 2),
            "citation_support": round(float(mean_citation_support), 2),
            "completeness": round(float(mean_completeness), 2),
            "abstention_rate": round(float(abstention_rate), 4),
            "invented_citations_count": invented_cits_total,
        }

    dev_items = [it for it in qa_results if it["split"] == "dev"]
    held_out_items = [it for it in qa_results if it["split"] == "held_out"]

    report = {
        "document_id": document_id,
        "tag": tag,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall": aggregate_split(qa_results),
            "dev": aggregate_split(dev_items),
            "held_out": aggregate_split(held_out_items),
        },
        "graph_quality": graph_metrics,
        "highlight_quality": highlight_metrics,
        "qa_details": qa_results,
    }

    # Save JSON result
    json_path = out_path / f"{tag}_{int(time.time())}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report
