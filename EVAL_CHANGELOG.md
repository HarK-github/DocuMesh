# Eval Changelog

All modifications to eval questions, gold answers, judge rubrics, and acceptance thresholds are logged here before running evaluations.

## 2026-11-13 - Initial Creation (Phase 1 Baseline)
- Created `evals/data/doc_21_chat_qa.json` with 22 questions (14 dev, 8 held-out), including mandatory questions on the imitation game, interrogator, advantage, and 4 unanswerable questions.
- Created `evals/data/doc_21_graph_gold.json` with 30 hand-labeled nodes and 36 hand-labeled edges.
- Created `evals/data/doc_21_highlight_gold.json` with required key ideas (must-highlight) and section headers/bylines (must-not-highlight).
- Created `evals/judge_prompt.md` with structured scoring rubric (Correctness, Faithfulness, Citation Support, Completeness, Abstention Correctness).
- Created `evals/runner.py` and `evals/run.py` to evaluate retrieval, answer quality, graph quality, and highlight quality.

## 2026-11-13 - Phase 3 Milestone (Retrieval and Context Assembly)
- Evaluated retrieval and context assembly fixes (`evals/results/phase3.md`).
- Results compared to Baseline:
  - Gold Span Recall: 36.1% -> 100.0% (Acceptance target >= 90.0%)
  - Dangling ID Rate: 34.7% -> 0.0% (Acceptance target: 0.0%)
  - `similar_to` Edge Share in Context: 52.4% -> 0.0% (Acceptance target: 0.0%)
  - LLM Judge Correctness: 4.65 -> 4.50 / 5 (Acceptance target >= 4.0 / 5)
  - LLM Judge Faithfulness: 4.61 -> 4.50 / 5 (Acceptance target >= 4.5 / 5)
  - Citation Support: 4.88 -> 4.95 / 5 (Acceptance target >= 4.0 / 5)
  - Abstention Rate: 100.0% -> 100.0% (Acceptance target: 100.0%)
  - Invented Citations: 0 -> 0 (Acceptance target: 0)

