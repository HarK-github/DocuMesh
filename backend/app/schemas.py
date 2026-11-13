"""Pydantic request and response schemas for all API endpoints."""

from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator


# Taxonomy Schemas
class TaxonomyResponse(BaseModel):
    """Available annotation labels and relation types."""
    labels: List[str]
    relation_types: List[str]


# Document Schemas
class DocumentResponse(BaseModel):
    """Document metadata details."""
    id: int
    filename: str
    file_hash: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    """Response returned upon document upload."""
    document_id: int
    job_id: Optional[str] = None
    status: str
    filename: str


class DocumentTextResponse(BaseModel):
    """Clean text payload for a document."""
    id: int
    filename: str
    clean_text: Optional[str] = None


# Annotation Schemas
class AnnotationCreate(BaseModel):
    """Payload to create an annotation."""
    start: int = Field(..., ge=0)
    end: int = Field(..., gt=0)
    quote: str
    label: str
    note: Optional[str] = None
    x: Optional[float] = 0.0
    y: Optional[float] = 0.0


class AnnotationUpdate(BaseModel):
    """Payload to update an annotation."""
    start: Optional[int] = None
    end: Optional[int] = None
    quote: Optional[str] = None
    label: Optional[str] = None
    note: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    version: int


class AnnotationResponse(BaseModel):
    """Annotation representation returned by API."""
    id: int
    document_id: int
    start: int
    end: int
    quote: str
    label: str
    note: Optional[str] = None
    x: float = 0.0
    y: float = 0.0
    version: int = 1
    created_at: Optional[datetime] = None
    status: Optional[str] = "confirmed"
    score: Optional[float] = None
    sentence_id: Optional[int] = None
    seed_annotation_id: Optional[int] = None

    model_config = {"from_attributes": True}


# Relation Schemas
class RelationCreate(BaseModel):
    """Payload to create a typed relation between two annotations."""
    source_id: int
    target_id: int
    type: str
    status: Optional[str] = "confirmed"
    reason: Optional[str] = None
    cos_score: Optional[float] = None
    score: Optional[float] = None


class RelationUpdate(BaseModel):
    """Payload to update a relation status or type."""
    type: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None
    version: int


class RelationResponse(BaseModel):
    """Relation representation returned by API."""
    id: int
    document_id: int
    source_id: int
    target_id: int
    type: str
    status: str
    reason: Optional[str] = None
    version: int = 1
    score: Optional[float] = None
    cos_score: Optional[float] = None

    model_config = {"from_attributes": True}


class SuggestRelationsRequest(BaseModel):
    """Optional payload to scope relation suggestions to a specific seed annotation."""
    seed_annotation_id: Optional[int] = None


# Graph Schema
class EdgeEvidenceResponse(BaseModel):
    id: int
    edge_id: int
    highlight_id: int
    evidence_quote: str

    model_config = {"from_attributes": True}


class GraphEdgeResponse(BaseModel):
    id: int
    run_id: int
    source_kind: str
    source_id: int
    target_kind: str
    target_id: int
    relation_type: str
    direction: str = "forward"
    confidence: float
    rationale: str
    review_status: str = "auto_candidate"
    extraction_method: str = "llm"
    evidence: List[EdgeEvidenceResponse] = []

    model_config = {"from_attributes": True}


class PropositionResponse(BaseModel):
    id: int
    document_id: int
    run_id: int
    canonical_statement: str
    statement_type: str
    summary: Optional[str] = None
    confidence: float
    review_status: str
    provenance_highlight_ids: List[int] = []

    model_config = {"from_attributes": True}


class ConceptResponse(BaseModel):
    id: int
    document_id: int
    run_id: int
    name: str
    canonical_name: str
    category: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class ExtractionRunResponse(BaseModel):
    id: int
    document_id: int
    graph_version: int
    model_name: str
    prompt_version: str
    status: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class GraphValidationResponse(BaseModel):
    is_valid: bool
    issues: List[str]
    metrics: Dict[str, Any]


class LegacyEdgeReviewRequest(BaseModel):
    run_id: int
    legacy_relation_id: int
    classification: str
    reviewer_reason: Optional[str] = None
    mapped_edge_id: Optional[int] = None
    reviewed_by: Optional[str] = "reviewer"


class LegacyEdgeReviewResponse(BaseModel):
    id: int
    run_id: int
    legacy_relation_id: int
    classification: str
    reviewer_reason: Optional[str] = None
    mapped_edge_id: Optional[int] = None
    reviewed_by: str
    reviewed_at: datetime

    model_config = {"from_attributes": True}


class EdgeMappingReportResponse(BaseModel):
    document_id: int
    run_id: int
    total_legacy_edges: int
    reviewed_edges_count: int
    unreviewed_edges_count: int
    review_coverage_pct: float
    classification_breakdown: Dict[str, int]
    items: List[Dict[str, Any]]


class GraphResponse(BaseModel):
    """Combined graph view of annotations (nodes) and relations (edges), supporting V1 and V2."""
    document_id: int
    annotations: List[AnnotationResponse]
    relations: List[RelationResponse]
    graph_version: int = 1
    run_id: Optional[int] = None
    is_active: bool = False
    propositions: Optional[List[PropositionResponse]] = None
    concepts: Optional[List[ConceptResponse]] = None
    edges: Optional[List[GraphEdgeResponse]] = None


class PathEdge(BaseModel):
    source_id: int
    target_id: int
    type: str


class PathItem(BaseModel):
    nodes: List[int]
    edges: List[PathEdge]
    length: int
    trace: str


class PathsResponse(BaseModel):
    document_id: int
    from_id: int
    to_id: int
    paths: List[PathItem]


# Suggestion Schemas
class AutoHighlightRequest(BaseModel):
    """Payload to request automated full-document highlight & relationship discovery."""
    mode: Optional[str] = "llm"  # 'llm' | 'embedding'


class SuggestHighlightsRequest(BaseModel):
    """Payload to request scoped highlight suggestions."""
    seed_annotation_id: Optional[int] = None
    scope: Optional[str] = "passage"  # 'passage' | 'category'
    target_label: Optional[str] = None


class SuggestionResponse(BaseModel):
    """Smart highlight suggestion item."""
    id: int
    document_id: int
    sentence_id: int
    seed_annotation_id: Optional[int] = None
    label: Optional[str] = None
    scope: Optional[str] = "passage"
    score: float
    status: str
    start: int
    end: int
    quote: str
    page: int
    message: Optional[str] = None



# Job Schemas
class JobResponse(BaseModel):
    """Background job execution status."""
    id: str
    type: str
    document_id: Optional[int] = None
    status: str
    progress: int
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# Chat Schemas
class ChatMessage(BaseModel):
    """Dialogue turn in chat conversation."""
    role: str
    content: str


class ChatRequest(BaseModel):
    """Payload for document chat query."""
    question: str = Field(..., min_length=1)
    history: List[ChatMessage] = Field(default_factory=list)
    mode: Optional[str] = Field(default="hybrid", description="Retrieval mode: 'vector' | 'graph' | 'hybrid'")

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Question cannot be empty or blank")
        return v.strip()


class CitationItem(BaseModel):
    """Validated citation referencing an entity in document or graph."""
    type: str  # "sentence" | "annotation" | "relation"
    id: int
    start: Optional[int] = None
    end: Optional[int] = None
    page: Optional[int] = None


class ChatResponse(BaseModel):
    """Answer with citations and context flag returned by chat service."""
    answer: str
    citations: List[CitationItem]
    used_context: bool
