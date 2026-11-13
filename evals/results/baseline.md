# DocuMesh Evaluation Report: `baseline`
**Document ID:** 21 | **Timestamp:** 2026-11-13T07:52:12.503976+00:00

## 1. Executive Summary
| Metric | Overall | Dev Split | Held-Out Split | Acceptance Target |
| :--- | :--- | :--- | :--- | :--- |
| **Gold Span Recall** | 36.1% | 34.7% | 38.9% | >= 90.0% |
| **Retrieval MRR** | 0.504 | 0.447 | 0.618 | - |
| **Dangling ID Rate** | 34.7% | 32.1% | 39.3% | 0.0% |
| **similar_to Share** | 52.4% | 55.5% | 47.1% | 0.0% in prompt |
| **Judge Correctness** | 4.65 / 5 | 4.59 / 5 | 4.75 / 5 | >= 4.0 / 5 |
| **Judge Faithfulness** | 4.61 / 5 | 4.52 / 5 | 4.75 / 5 | >= 4.5 / 5 |
| **Citation Support** | 4.76 / 5 | 4.69 / 5 | 4.88 / 5 | >= 4.0 / 5 |
| **Completeness** | 4.65 / 5 | 4.59 / 5 | 4.75 / 5 | >= 4.0 / 5 |
| **Abstention Rate** | 100.0% | 100.0% | 100.0% | 100.0% |
| **Invented Citations** | 1 | 1 | 0 | 0 |

## 2. Graph Quality Metrics
- **Node Label Accuracy:** 39.1% (vs hand-labeled gold nodes)
- **Edge Precision:** 25.9% (14/54 valid typed edges)
- **Invalid Edges Count:** 40
- **Edges Below Floor Confirmed:** 0 (Target: 0)
- **Duplicate Node Rate:** 100.0%

## 3. Highlight Quality Metrics
- **Key Idea Coverage:** 84.6% (11/13 key ideas)
- **Forbidden Highlights (Headers/Title/Byline):** 5 (Target: 0)
- **Highlight Density:** 4.24 per 100 words (67.7% of sentences)
- **Boundary Quality:** 91.3% complete sentences/clauses

## 4. Question-by-Question Breakdown
| ID | Split | Type | Question | Span Recall | Correctness | Faithfulness | Abstention |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| q1 | dev | definitional | What is the imitation game? | 25% | 4.3 | 4.3 | PASS |
| q2 | dev | factual | What does the interrogator do? | 50% | 4.0 | 4.0 | PASS |
| q3 | dev | why_purpose | Why does Turing replace 'Can machines think?' | 25% | 4.0 | 4.0 | PASS |
| q4 | dev | factual | What advantage does the imitation game have? | 100% | 5.0 | 5.0 | PASS |
| q5 | dev | factual | What happens when a machine takes the part of A? | 50% | 4.0 | 3.0 | PASS |
| q6 | dev | factual | What are the three parts of a digital computer? | 0% | 5.0 | 5.0 | PASS |
| q7 | dev | definitional | What is a universal machine according to Turing? | 50% | 4.0 | 4.0 | PASS |
| q8 | dev | factual | How does the human computer operate according to the text? | 0% | 5.0 | 5.0 | PASS |
| q9 | dev | why_purpose | Why is it unnecessary to design various new machines for different computing processes? | 50% | 5.0 | 5.0 | PASS |
| q10 | dev | factual | Can engineers or chemists make artificial human skin according to the author? | 0% | 5.0 | 5.0 | PASS |
| q11 | dev | multi_hop | How does the imitation game separate physical capacities from intellectual capacities? | 33% | 4.0 | 4.0 | PASS |
| q12 | dev | multi_hop | What connects the rules supplied in a book to the operations of a digital computer? | 33% | 5.0 | 5.0 | PASS |
| q13 | dev | unanswerable | What year was the Turing machine first built in hardware? | N/A | 5.0 | 5.0 | PASS |
| q14 | dev | unanswerable | What programming language was used to program the digital computer? | N/A | 5.0 | 5.0 | PASS |
| q15 | held_out | factual | Can digital computers mimic discrete state machines? | 100% | 5.0 | 5.0 | PASS |
| q16 | held_out | definitional | What role does the 'Store' play in a digital computer? | 0% | 5.0 | 5.0 | PASS |
| q17 | held_out | factual | What is the function of the executive unit in a digital computer? | 100% | 4.0 | 4.0 | PASS |
| q18 | held_out | factual | What does the control component do in a digital computer? | 0% | 5.0 | 5.0 | PASS |
| q19 | held_out | why_purpose | Why would dressing a thinking machine in artificial flesh be of little interest? | 0% | 5.0 | 5.0 | PASS |
| q20 | held_out | comparison | Compare the role of the human computer with the digital computer. | 33% | 4.0 | 4.0 | PASS |
| q21 | held_out | unanswerable | How many vacuum tubes or transistors did Turing's computer use? | N/A | 5.0 | 5.0 | PASS |
| q22 | held_out | unanswerable | Who was the first female programmer mentioned in the text? | N/A | 5.0 | 5.0 | PASS |