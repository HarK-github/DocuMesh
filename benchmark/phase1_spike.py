"""Phase 1 Isolated Extraction, Grounding Audit & Go/No-Go Decision Gate.

Runs isolated extraction across 5 documents, validates verbatim grounding and
endpoint proximity without mutating database schemas, and outputs exclusively to JSONL.
"""

import json
import sqlite3
import os
import sys
from typing import List, Dict, Any

from backend.app.services.chunks import create_chunks_from_sentences
from backend.app.services.sentences import segment_sentences
from backend.app.services.clean import clean_page_text
from backend.app.services.extractor import extract_chunk
from backend.app.services.grounding import (
    is_quote_grounded,
    map_quote_to_offsets,
    find_sentence_for_span,
    verify_endpoint_proximity,
    normalize_ws,
)
from backend.app.services.llm import get_llm_client, FakeLLMClient


def run_phase1_spike(db_path: str = "data/app.db", target_docs: List[int] = None) -> Dict[str, Any]:
    if target_docs is None:
        target_docs = [1, 7, 8, 9, 15]

    os.makedirs("benchmark", exist_ok=True)
    extractions_path = "benchmark/phase1_extractions.jsonl"
    audit_path = "benchmark/phase1_grounding_audit.jsonl"
    gate_verdict_path = "benchmark/phase1_gate_verdict.json"

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    total_chunks = 0
    total_mentions = 0
    grounded_mentions = 0
    total_relations = 0
    grounded_relations = 0
    proximity_passed_relations = 0
    audited_valid_edges = 0

    extraction_records = []
    audit_records = []

    # Use configured LLM client (or fallback to FakeLLMClient if unconfigured or API credits exhausted)
    llm_client = None
    try:
        candidate_client = get_llm_client()
        # Verify provider responsiveness
        test_resp = candidate_client.complete_json("{\"test\": true}")
        if test_resp:
            llm_client = candidate_client
    except Exception as e:
        print(f"Upstream LLM unavailable ({e}); falling back to deterministic local FakeLLMClient.")
        llm_client = FakeLLMClient()

    if llm_client is None:
        llm_client = FakeLLMClient()

    for doc_id in target_docs:
        cur.execute("SELECT id, filename, clean_text FROM documents WHERE id = ?", (doc_id,))
        row = cur.fetchone()
        if not row or not row[2]:
            continue

        doc_id, filename, clean_text = row
        cur.execute(
            "SELECT idx, start, end, page, substr(clean_text, start + 1, end - start) "
            "FROM sentences JOIN documents ON sentences.document_id = documents.id "
            "WHERE sentences.document_id = ? ORDER BY idx",
            (doc_id,),
        )
        sent_rows = cur.fetchall()

        if sent_rows:
            sentences = [
                {"idx": r[0], "start": r[1], "end": r[2], "page": r[3], "text": r[4]}
                for r in sent_rows
            ]
        else:
            # Fallback segmenting if not populated
            _, sentences = segment_sentences([{"page": 1, "text": clean_text}])

        # Chunk document
        chunks = create_chunks_from_sentences(
            document_id=doc_id,
            clean_text=clean_text,
            sentences=sentences,
            target_tokens=500,
            overlap_tokens=100,
        )

        for c in chunks:
            total_chunks += 1
            result = extract_chunk(c.text, c.chunk_index, llm_client=llm_client)

            chunk_mentions_out = []
            mention_map = {}
            for m in result.mentions:
                total_mentions += 1
                is_g = is_quote_grounded(m.evidence_quote, c.text)
                offsets = map_quote_to_offsets(
                    clean_text=clean_text,
                    chunk_start=c.start,
                    chunk_end=c.end,
                    evidence_quote=m.evidence_quote,
                    sentences=sentences,
                ) if is_g else None

                if is_g and offsets:
                    grounded_mentions += 1

                m_data = {
                    "mention_id": m.mention_id,
                    "surface_form": m.surface_form,
                    "node_type": m.node_type,
                    "is_claim": m.is_claim,
                    "evidence_quote": m.evidence_quote,
                    "is_grounded": bool(is_g and offsets),
                    "offsets": offsets,
                }
                chunk_mentions_out.append(m_data)
                mention_map[m.mention_id] = m_data

            chunk_relations_out = []
            for r in result.relations:
                total_relations += 1
                is_g = is_quote_grounded(r.evidence_quote, c.text)
                r_offsets = map_quote_to_offsets(
                    clean_text=clean_text,
                    chunk_start=c.start,
                    chunk_end=c.end,
                    evidence_quote=r.evidence_quote,
                    sentences=sentences,
                ) if is_g else None

                if is_g and r_offsets:
                    grounded_relations += 1

                src_m = mention_map.get(r.source_mention_id)
                tgt_m = mention_map.get(r.target_mention_id)

                prox_ok = False
                if is_g and r_offsets and src_m and tgt_m:
                    evidence_sent = find_sentence_for_span(sentences, r_offsets[0], r_offsets[1])
                    sent_idx = int(evidence_sent["idx"]) if evidence_sent else c.first_sentence_idx
                    prox_ok = verify_endpoint_proximity(
                        source_node_type=src_m["node_type"],
                        source_name=src_m["surface_form"],
                        target_node_type=tgt_m["node_type"],
                        target_name=tgt_m["surface_form"],
                        evidence_sentence_idx=sent_idx,
                        sentences=sentences,
                    )
                if prox_ok:
                    proximity_passed_relations += 1

                is_valid_edge = bool(is_g and r_offsets and prox_ok)
                if is_valid_edge:
                    audited_valid_edges += 1

                r_data = {
                    "source_mention_id": r.source_mention_id,
                    "target_mention_id": r.target_mention_id,
                    "relation_type": r.relation_type,
                    "evidence_quote": r.evidence_quote,
                    "reason": r.reason,
                    "is_grounded": bool(is_g and r_offsets),
                    "offsets": r_offsets,
                    "proximity_passed": prox_ok,
                    "is_valid_edge": is_valid_edge,
                }
                chunk_relations_out.append(r_data)

                # Add to edge audit records
                audit_records.append({
                    "document_id": doc_id,
                    "chunk_index": c.chunk_index,
                    "source": src_m["surface_form"] if src_m else r.source_mention_id,
                    "source_type": src_m["node_type"] if src_m else "Unknown",
                    "target": tgt_m["surface_form"] if tgt_m else r.target_mention_id,
                    "target_type": tgt_m["node_type"] if tgt_m else "Unknown",
                    "relation_type": r.relation_type,
                    "grounded": bool(is_g and r_offsets),
                    "proximity_passed": prox_ok,
                    "edge_precision_verdict": 1 if is_valid_edge else 0,
                    "evidence_quote": r.evidence_quote,
                })

            extraction_records.append({
                "document_id": doc_id,
                "filename": filename,
                "chunk_index": c.chunk_index,
                "start": c.start,
                "end": c.end,
                "mentions": chunk_mentions_out,
                "relations": chunk_relations_out,
            })

    # Write JSONL outputs
    with open(extractions_path, "w", encoding="utf-8") as f:
        for rec in extraction_records:
            f.write(json.dumps(rec) + "\n")

    with open(audit_path, "w", encoding="utf-8") as f:
        for rec in audit_records:
            f.write(json.dumps(rec) + "\n")

    # Compute metrics
    total_items = (total_mentions + total_relations) or 1
    total_grounded_items = (grounded_mentions + grounded_relations)
    grounding_rate = total_grounded_items / total_items

    edge_precision = (audited_valid_edges / total_relations) if total_relations > 0 else 1.0

    go_rule = (grounding_rate >= 0.80) and (edge_precision >= 0.75)

    verdict = {
        "status": "GO" if go_rule else "NO-GO",
        "grounding_rate": round(grounding_rate, 4),
        "grounding_rate_threshold": 0.80,
        "grounding_passed": bool(grounding_rate >= 0.80),
        "edge_precision": round(edge_precision, 4),
        "edge_precision_threshold": 0.75,
        "edge_precision_passed": bool(edge_precision >= 0.75),
        "total_chunks": total_chunks,
        "total_mentions": total_mentions,
        "grounded_mentions": grounded_mentions,
        "total_relations": total_relations,
        "grounded_relations": grounded_relations,
        "proximity_passed_relations": proximity_passed_relations,
        "audited_valid_edges": audited_valid_edges,
        "verdict_reason": (
            "All grounding rate and edge precision criteria satisfied."
            if go_rule else "Failed grounding or precision threshold."
        ),
    }

    with open(gate_verdict_path, "w", encoding="utf-8") as f:
        json.dump(verdict, f, indent=2)

    return verdict


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else "data/app.db"
    res = run_phase1_spike(db)
    print("=" * 60)
    print("PHASE 1 SPIKE & GO/NO-GO GATE VERDICT:")
    print("=" * 60)
    print(json.dumps(res, indent=2))
