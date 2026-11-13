"""CLI entrypoint for running GraphRAG evaluations on DocuMesh."""

import argparse
import sys
from pathlib import Path
from evals.runner import run_document_evaluation


def generate_markdown_report(report: dict, out_md_path: Path):
    """Format evaluation report into clean readable Markdown."""
    summary = report["summary"]["overall"]
    dev_sum = report["summary"]["dev"]
    held_sum = report["summary"]["held_out"]
    graph = report["graph_quality"]
    hl = report["highlight_quality"]

    md = []
    md.append(f"# DocuMesh Evaluation Report: `{report['tag']}`")
    md.append(f"**Document ID:** {report['document_id']} | **Timestamp:** {report['timestamp']}\n")

    md.append("## 1. Executive Summary")
    md.append("| Metric | Overall | Dev Split | Held-Out Split | Acceptance Target |")
    md.append("| :--- | :--- | :--- | :--- | :--- |")
    md.append(f"| **Gold Span Recall** | {summary.get('gold_span_recall', 0.0) * 100:.1f}% | {dev_sum.get('gold_span_recall', 0.0) * 100:.1f}% | {held_sum.get('gold_span_recall', 0.0) * 100:.1f}% | >= 90.0% |")
    md.append(f"| **Retrieval MRR** | {summary.get('mrr', 0.0):.3f} | {dev_sum.get('mrr', 0.0):.3f} | {held_sum.get('mrr', 0.0):.3f} | - |")
    md.append(f"| **Dangling ID Rate** | {summary.get('dangling_id_rate', 0.0) * 100:.1f}% | {dev_sum.get('dangling_id_rate', 0.0) * 100:.1f}% | {held_sum.get('dangling_id_rate', 0.0) * 100:.1f}% | 0.0% |")
    md.append(f"| **similar_to Share** | {summary.get('similar_to_share', 0.0) * 100:.1f}% | {dev_sum.get('similar_to_share', 0.0) * 100:.1f}% | {held_sum.get('similar_to_share', 0.0) * 100:.1f}% | 0.0% in prompt |")
    md.append(f"| **Judge Correctness** | {summary.get('correctness', 0.0):.2f} / 5 | {dev_sum.get('correctness', 0.0):.2f} / 5 | {held_sum.get('correctness', 0.0):.2f} / 5 | >= 4.0 / 5 |")
    md.append(f"| **Judge Faithfulness** | {summary.get('faithfulness', 0.0):.2f} / 5 | {dev_sum.get('faithfulness', 0.0):.2f} / 5 | {held_sum.get('faithfulness', 0.0):.2f} / 5 | >= 4.5 / 5 |")
    md.append(f"| **Citation Support** | {summary.get('citation_support', 0.0):.2f} / 5 | {dev_sum.get('citation_support', 0.0):.2f} / 5 | {held_sum.get('citation_support', 0.0):.2f} / 5 | >= 4.0 / 5 |")
    md.append(f"| **Completeness** | {summary.get('completeness', 0.0):.2f} / 5 | {dev_sum.get('completeness', 0.0):.2f} / 5 | {held_sum.get('completeness', 0.0):.2f} / 5 | >= 4.0 / 5 |")
    md.append(f"| **Abstention Rate** | {summary.get('abstention_rate', 0.0) * 100:.1f}% | {dev_sum.get('abstention_rate', 0.0) * 100:.1f}% | {held_sum.get('abstention_rate', 0.0) * 100:.1f}% | 100.0% |")
    md.append(f"| **Invented Citations** | {summary.get('invented_citations_count', 0)} | {dev_sum.get('invented_citations_count', 0)} | {held_sum.get('invented_citations_count', 0)} | 0 |")

    md.append("\n## 2. Graph Quality Metrics")
    md.append(f"- **Node Label Accuracy:** {graph['node_label_accuracy'] * 100:.1f}% (vs hand-labeled gold nodes)")
    md.append(f"- **Edge Precision:** {graph['edge_precision'] * 100:.1f}% ({graph['valid_edges']}/{graph['total_edges']} valid typed edges)")
    md.append(f"- **Invalid Edges Count:** {graph['invalid_edges_count']}")
    md.append(f"- **Edges Below Floor Confirmed:** {graph['edges_below_floor_confirmed']} (Target: 0)")
    md.append(f"- **Duplicate Node Rate:** {graph['duplicate_rate'] * 100:.1f}%\n")

    md.append("## 3. Highlight Quality Metrics")
    md.append(f"- **Key Idea Coverage:** {hl['key_idea_recall'] * 100:.1f}% ({hl['key_ideas_covered']}/{hl['key_ideas_total']} key ideas)")
    md.append(f"- **Forbidden Highlights (Headers/Title/Byline):** {hl['forbidden_highlights_count']} (Target: 0)")
    md.append(f"- **Highlight Density:** {hl['density_per_100_words']:.2f} per 100 words ({hl['percent_sentences_highlighted']:.1f}% of sentences)")
    md.append(f"- **Boundary Quality:** {hl['boundary_quality'] * 100:.1f}% complete sentences/clauses\n")

    md.append("## 4. Question-by-Question Breakdown")
    md.append("| ID | Split | Type | Question | Span Recall | Correctness | Faithfulness | Abstention |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for q in report["qa_details"]:
        q_rec = f"{q['retrieval']['gold_span_recall'] * 100:.0f}%" if q['retrieval']['gold_spans_total'] > 0 else "N/A"
        q_abs = "PASS" if q['deterministic_citations']['abstention_pass'] else "FAIL"
        md.append(f"| {q['id']} | {q['split']} | {q['type']} | {q['question']} | {q_rec} | {q['judge']['correctness_mean']:.1f} | {q['judge']['faithfulness_mean']:.1f} | {q_abs} |")

    out_md_path.write_text("\n".join(md), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run DocuMesh GraphRAG evaluation suite.")
    parser.add_argument("--doc", type=int, default=21, help="Document ID to evaluate")
    parser.add_argument("--out", type=str, default="evals/results", help="Output directory")
    parser.add_argument("--tag", type=str, default="baseline", help="Run tag (e.g. baseline, final)")
    parser.add_argument("--repeats", type=int, default=3, help="Judge evaluation repeats for variance check")
    parser.add_argument("--calibration", action="store_true", help="Run calibration check against human sample")
    args = parser.parse_args()

    print(f"\n==================================================")
    print(f"Starting DocuMesh Evaluation: Tag='{args.tag}', Doc={args.doc}")
    print(f"==================================================")

    report = run_document_evaluation(
        document_id=args.doc,
        out_dir=args.out,
        tag=args.tag,
        judge_repeats=args.repeats,
    )

    out_dir = Path(args.out)
    md_file = out_dir / f"{args.tag}.md"
    generate_markdown_report(report, md_file)

    summary = report["summary"]["overall"]
    print("\n--- EVALUATION COMPLETE ---")
    print(f"Report JSON written to {args.out}")
    print(f"Report Markdown written to {md_file}")
    print(f"\nHEADLINE METRICS ({args.tag.upper()}):")
    print(f"  Gold Span Recall:     {summary.get('gold_span_recall', 0.0) * 100:.1f}%")
    print(f"  Dangling ID Rate:     {summary.get('dangling_id_rate', 0.0) * 100:.1f}%")
    print(f"  similar_to Share:     {summary.get('similar_to_share', 0.0) * 100:.1f}%")
    print(f"  Judge Correctness:    {summary.get('correctness', 0.0):.2f} / 5")
    print(f"  Judge Faithfulness:   {summary.get('faithfulness', 0.0):.2f} / 5")
    print(f"  Abstention Rate:      {summary.get('abstention_rate', 0.0) * 100:.1f}%")
    print(f"  Edge Precision:       {report['graph_quality']['edge_precision'] * 100:.1f}%")
    print(f"  Edges Below Floor:    {report['graph_quality']['edges_below_floor_confirmed']}")
    print(f"  Forbidden Highlights: {report['highlight_quality']['forbidden_highlights_count']}")
    print(f"  Key Idea Coverage:    {report['highlight_quality']['key_idea_recall'] * 100:.1f}%")
    print("==================================================\n")


if __name__ == "__main__":
    main()
