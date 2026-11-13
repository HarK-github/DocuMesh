# DocuMesh Evaluation Report: `phase6_doc20`
**Document ID:** 20 | **Timestamp:** 2026-11-13T08:37:45.730840+00:00

## 1. Executive Summary
| Metric | Overall | Dev Split | Held-Out Split | Acceptance Target |
| :--- | :--- | :--- | :--- | :--- |
| **Gold Span Recall** | 100.0% | 100.0% | 100.0% | >= 90.0% |
| **Retrieval MRR** | 0.400 | 0.429 | 0.333 | - |
| **Dangling ID Rate** | 0.0% | 0.0% | 0.0% | 0.0% |
| **similar_to Share** | 0.0% | 0.0% | 0.0% | 0.0% in prompt |
| **Judge Correctness** | 4.54 / 5 | 4.38 / 5 | 4.80 / 5 | >= 4.0 / 5 |
| **Judge Faithfulness** | 4.54 / 5 | 4.38 / 5 | 4.80 / 5 | >= 4.5 / 5 |
| **Citation Support** | 5.00 / 5 | 5.00 / 5 | 5.00 / 5 | >= 4.0 / 5 |
| **Completeness** | 4.54 / 5 | 4.38 / 5 | 4.80 / 5 | >= 4.0 / 5 |
| **Abstention Rate** | 100.0% | 100.0% | 100.0% | 100.0% |
| **Invented Citations** | 0 | 0 | 0 | 0 |

## 2. Graph Quality Metrics
- **Node Label Accuracy:** 90.9% (vs hand-labeled gold nodes)
- **Edge Precision:** 100.0% (3/3 valid typed edges)
- **Invalid Edges Count:** 0
- **Edges Below Floor Confirmed:** 0 (Target: 0)
- **Duplicate Node Rate:** 0.0%

## 3. Highlight Quality Metrics
- **Key Idea Coverage:** 100.0% (7/7 key ideas)
- **Forbidden Highlights (Headers/Title/Byline):** 0 (Target: 0)
- **Highlight Density:** 1.76 per 100 words (13.5% of sentences)
- **Boundary Quality:** 94.7% complete sentences/clauses

## 4. Question-by-Question Breakdown
| ID | Split | Type | Question | Span Recall | Correctness | Faithfulness | Abstention |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| q1 | dev | definitional | What is the outer-join trap described in the lab? | 100% | 4.0 | 4.0 | PASS |
| q2 | dev | definitional | What is the anti-join pattern according to the document? | 100% | 4.0 | 4.0 | PASS |
| q3 | dev | factual | What dataset and deliverable SQL file are used in Lab 2? | 100% | 5.0 | 5.0 | PASS |
| q4 | dev | factual | How do you enable foreign keys in SQLite for each session? | 100% | 5.0 | 5.0 | PASS |
| q5 | dev | factual | What is the checkpoint result for the top student in Q4? | 100% | 4.0 | 4.0 | PASS |
| q6 | dev | factual | What is the result of the row-explosion demonstration in Q24? | 100% | 4.0 | 4.0 | PASS |
| q7 | dev | multi_hop | How do you avoid self-pairs and mirror duplicates when finding pairs of instructors in the same department? | 100% | 4.0 | 4.0 | PASS |
| q8 | dev | unanswerable | What is the instructor's personal phone number or email address? | N/A | 5.0 | 5.0 | PASS |
| q9 | held_out | factual | Which instructors are listed when running python3 explore.py Physics? | 100% | 5.0 | 5.0 | PASS |
| q10 | held_out | factual | Which sections have no assigned instructor in Q18? | 100% | 5.0 | 5.0 | PASS |
| q11 | held_out | multi_hop | Why should parameterized queries with question marks be used in explore.py instead of f-strings? | 100% | 4.0 | 4.0 | PASS |
| q12 | held_out | unanswerable | What is the exact calendar due date and submission timestamp for Lab 2? | N/A | 5.0 | 5.0 | PASS |
| q13 | held_out | unanswerable | What version of PostgreSQL is required to run the university schema? | N/A | 5.0 | 5.0 | PASS |