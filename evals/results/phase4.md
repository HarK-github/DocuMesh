# DocuMesh Evaluation Report: `phase4`
**Document ID:** 21 | **Timestamp:** 2026-11-13T08:23:41.534229+00:00

## 1. Executive Summary
| Metric | Overall | Dev Split | Held-Out Split | Acceptance Target |
| :--- | :--- | :--- | :--- | :--- |
| **Gold Span Recall** | 100.0% | 100.0% | 100.0% | >= 90.0% |
| **Retrieval MRR** | 0.357 | 0.301 | 0.471 | - |
| **Dangling ID Rate** | 0.0% | 0.0% | 0.0% | 0.0% |
| **similar_to Share** | 0.0% | 0.0% | 0.0% | 0.0% in prompt |
| **Judge Correctness** | 4.45 / 5 | 4.43 / 5 | 4.50 / 5 | >= 4.0 / 5 |
| **Judge Faithfulness** | 4.45 / 5 | 4.43 / 5 | 4.50 / 5 | >= 4.5 / 5 |
| **Citation Support** | 4.95 / 5 | 4.93 / 5 | 5.00 / 5 | >= 4.0 / 5 |
| **Completeness** | 4.41 / 5 | 4.43 / 5 | 4.38 / 5 | >= 4.0 / 5 |
| **Abstention Rate** | 100.0% | 100.0% | 100.0% | 100.0% |
| **Invented Citations** | 0 | 0 | 0 | 0 |

## 2. Graph Quality Metrics
- **Node Label Accuracy:** 38.1% (vs hand-labeled gold nodes)
- **Edge Precision:** 100.0% (13/13 valid typed edges)
- **Invalid Edges Count:** 0
- **Edges Below Floor Confirmed:** 0 (Target: 0)
- **Duplicate Node Rate:** 0.0%

## 3. Highlight Quality Metrics
- **Key Idea Coverage:** 69.2% (9/13 key ideas)
- **Forbidden Highlights (Headers/Title/Byline):** 5 (Target: 0)
- **Highlight Density:** 3.87 per 100 words (61.8% of sentences)
- **Boundary Quality:** 90.5% complete sentences/clauses

## 4. Question-by-Question Breakdown
| ID | Split | Type | Question | Span Recall | Correctness | Faithfulness | Abstention |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| q1 | dev | definitional | What is the imitation game? | 100% | 4.0 | 4.0 | PASS |
| q2 | dev | factual | What does the interrogator do? | 100% | 4.0 | 4.0 | PASS |
| q3 | dev | why_purpose | Why does Turing replace 'Can machines think?' | 100% | 4.0 | 4.0 | PASS |
| q4 | dev | factual | What advantage does the imitation game have? | 100% | 5.0 | 5.0 | PASS |
| q5 | dev | factual | What happens when a machine takes the part of A? | 100% | 4.0 | 4.0 | PASS |
| q6 | dev | factual | What are the three parts of a digital computer? | 100% | 5.0 | 5.0 | PASS |
| q7 | dev | definitional | What is a universal machine according to Turing? | 100% | 5.0 | 5.0 | PASS |
| q8 | dev | factual | How does the human computer operate according to the text? | 100% | 4.0 | 4.0 | PASS |
| q9 | dev | why_purpose | Why is it unnecessary to design various new machines for different computing processes? | 100% | 5.0 | 5.0 | PASS |
| q10 | dev | factual | Can engineers or chemists make artificial human skin according to the author? | 100% | 4.0 | 4.0 | PASS |
| q11 | dev | multi_hop | How does the imitation game separate physical capacities from intellectual capacities? | 100% | 4.0 | 4.0 | PASS |
| q12 | dev | multi_hop | What connects the rules supplied in a book to the operations of a digital computer? | 100% | 4.0 | 4.0 | PASS |
| q13 | dev | unanswerable | What year was the Turing machine first built in hardware? | N/A | 5.0 | 5.0 | PASS |
| q14 | dev | unanswerable | What programming language was used to program the digital computer? | N/A | 5.0 | 5.0 | PASS |
| q15 | held_out | factual | Can digital computers mimic discrete state machines? | 100% | 5.0 | 5.0 | PASS |
| q16 | held_out | definitional | What role does the 'Store' play in a digital computer? | 100% | 4.0 | 4.0 | PASS |
| q17 | held_out | factual | What is the function of the executive unit in a digital computer? | 100% | 4.0 | 4.0 | PASS |
| q18 | held_out | factual | What does the control component do in a digital computer? | 100% | 4.0 | 4.0 | PASS |
| q19 | held_out | why_purpose | Why would dressing a thinking machine in artificial flesh be of little interest? | 100% | 5.0 | 5.0 | PASS |
| q20 | held_out | comparison | Compare the role of the human computer with the digital computer. | 100% | 4.0 | 4.0 | PASS |
| q21 | held_out | unanswerable | How many vacuum tubes or transistors did Turing's computer use? | N/A | 5.0 | 5.0 | PASS |
| q22 | held_out | unanswerable | Who was the first female programmer mentioned in the text? | N/A | 5.0 | 5.0 | PASS |