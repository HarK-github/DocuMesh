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


# Sentence Schemas
class SentenceResponse(BaseModel):
    """Sentence segment with page and offsets."""
    id: int
    document_id: int
    idx: int
    start: int
    end: int
    page: int

    model_config = {"from_attributes": True}


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
    x: float
    y: float
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


# Relation Schemas
class RelationCreate(BaseModel):
    """Payload to create a typed relation between two annotations."""
    source_id: int
    target_id: int
    type: str
    status: Optional[str] = "confirmed"
    reason: Optional[str] = None


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
    version: int

    model_config = {"from_attributes": True}


# Graph Schema
class GraphResponse(BaseModel):
    """Combined graph view of annotations (nodes) and relations (edges)."""
    document_id: int
    annotations: List[AnnotationResponse]
    relations: List[RelationResponse]


# Suggestion Schemas
class SuggestionResponse(BaseModel):
    """Smart highlight suggestion item."""
    id: int
    document_id: int
    sentence_id: int
    score: float
    status: str
    start: int
    end: int
    quote: str
    page: int


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


class ChatResponse(BaseModel):
    """Answer with citations and context flag returned by chat service."""
    answer: str
    citations: List[CitationItem]
    used_context: bool
