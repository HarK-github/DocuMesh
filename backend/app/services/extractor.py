"""Structured chunk extraction service with local-ID mentions and relations."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ValidationError
from backend.app.services.llm import get_llm_client, BaseLLMClient

ALLOWED_NODE_TYPES = (
    "Method", "Dataset", "Metric", "Task", "System", "Problem", "Solution", "Claim", "Result"
)

ALLOWED_RELATION_TYPES = (
    "supports", "refutes", "defines", "elaborates", "causes",
    "solves", "contrasts_with", "conditional_on", "precedes", "evaluates_with"
)


class LocalMention(BaseModel):
    """Local mention anchored within a single chunk."""

    mention_id: str = Field(..., description="Local chunk-scoped ID, e.g. 'm1', 'm2'")
    surface_form: str = Field(..., description="Entity name or concise proposition title")
    node_type: Literal[
        "Method", "Dataset", "Metric", "Task", "System", "Problem", "Solution", "Claim", "Result"
    ] = Field(..., description="Canonical node ontology type")
    is_claim: bool = Field(default=False, description="True for document-local Claims/Results")
    evidence_quote: str = Field(..., description="Verbatim quote from the chunk as provenance")


class LocalRelation(BaseModel):
    """Typed relationship connecting two local mentions within a chunk."""

    source_mention_id: str = Field(..., description="References mention_id (e.g. 'm1')")
    target_mention_id: str = Field(..., description="References mention_id (e.g. 'm2')")
    relation_type: Literal[
        "supports", "refutes", "defines", "elaborates", "causes",
        "solves", "contrasts_with", "conditional_on", "precedes", "evaluates_with"
    ] = Field(..., description="Restricted relation ontology type")
    evidence_quote: str = Field(..., description="Verbatim quote containing or evidencing relation")
    reason: str = Field(..., description="Brief factual justification for this relationship")


class ChunkExtractionResult(BaseModel):
    """Extraction output schema containing local mentions and relations."""

    mentions: List[LocalMention] = Field(default_factory=list)
    relations: List[LocalRelation] = Field(default_factory=list)


EXTRACTION_SYSTEM_PROMPT = """You are an expert scientific knowledge graph extraction system.
Extract scientific entities (concepts), propositions (claims/results), and their typed relationships from the given academic paper chunk.

CRITICAL RULES:
1. Assign every mention a unique local ID (m1, m2, m3, ...).
2. Allowed node_type values:
   Method, Dataset, Metric, Task, System, Problem, Solution, Claim, Result.
3. Allowed relation_type values:
   supports, refutes, defines, elaborates, causes, solves, contrasts_with, conditional_on, precedes, evaluates_with.
   DO NOT use 'relates_to' or 'similar_to'.
4. EVERY evidence_quote MUST be an exact verbatim substring copied directly from the chunk text.
5. source_mention_id and target_mention_id MUST reference valid mention IDs defined in 'mentions'.
6. source_mention_id must NOT equal target_mention_id.

Respond ONLY with a JSON object matching this schema:
{
  "mentions": [
    {
      "mention_id": "m1",
      "surface_form": "FlashAttention",
      "node_type": "Method",
      "is_claim": false,
      "evidence_quote": "exact quote from text"
    }
  ],
  "relations": [
    {
      "source_mention_id": "m1",
      "target_mention_id": "m2",
      "relation_type": "solves",
      "evidence_quote": "exact quote from text connecting m1 and m2",
      "reason": "explanation of relation"
    }
  ]
}
"""


def build_extraction_prompt(chunk_text: str, chunk_index: int) -> str:
    """Build structured extraction prompt for a given chunk."""
    return f"""{EXTRACTION_SYSTEM_PROMPT}

Chunk Index: {chunk_index}
Chunk Text:
\"\"\"
{chunk_text}
\"\"\"
"""


def extract_chunk(
    chunk_text: str,
    chunk_index: int,
    llm_client: Optional[BaseLLMClient] = None,
) -> ChunkExtractionResult:
    """Extract entities and relationships from a single chunk using structured LLM inference."""
    client = llm_client or get_llm_client()
    prompt = build_extraction_prompt(chunk_text, chunk_index)

    raw_response = client.complete_json(prompt)
    if isinstance(raw_response, dict):
        try:
            return ChunkExtractionResult.model_validate(raw_response)
        except ValidationError:
            # Attempt best-effort recovery of valid mentions and relations
            valid_mentions: List[LocalMention] = []
            mention_ids = set()
            for m in raw_response.get("mentions", []):
                try:
                    mention = LocalMention.model_validate(m)
                    valid_mentions.append(mention)
                    mention_ids.add(mention.mention_id)
                except ValidationError:
                    continue

            valid_relations: List[LocalRelation] = []
            for r in raw_response.get("relations", []):
                try:
                    relation = LocalRelation.model_validate(r)
                    if (
                        relation.source_mention_id in mention_ids
                        and relation.target_mention_id in mention_ids
                        and relation.source_mention_id != relation.target_mention_id
                    ):
                        valid_relations.append(relation)
                except ValidationError:
                    continue

            return ChunkExtractionResult(mentions=valid_mentions, relations=valid_relations)

    return ChunkExtractionResult(mentions=[], relations=[])
