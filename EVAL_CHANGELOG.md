# Eval Changelog

All modifications to eval questions, gold answers, judge rubrics, and acceptance thresholds are logged here before running evaluations.

## 2026-11-13 - Initial Creation (Phase 1 Baseline)
- Created `evals/data/doc_21_chat_qa.json` with 22 questions (14 dev, 8 held-out), including mandatory questions on the imitation game, interrogator, advantage, and 4 unanswerable questions.
- Created `evals/data/doc_21_graph_gold.json` with 30 hand-labeled nodes and 36 hand-labeled edges.
- Created `evals/data/doc_21_highlight_gold.json` with required key ideas (must-highlight) and section headers/bylines (must-not-highlight).
- Created `evals/judge_prompt.md` with structured scoring rubric (Correctness, Faithfulness, Citation Support, Completeness, Abstention Correctness).
- Created `evals/runner.py` and `evals/run.py` to evaluate retrieval, answer quality, graph quality, and highlight quality.
