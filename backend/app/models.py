"""SQLAlchemy data models for documents, annotations, relations, and jobs."""

from datetime import datetime, timezone
from typing import Any
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
    Index,
    text,
    CheckConstraint,
    UniqueConstraint,
    Numeric,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()

EMBEDDING_DIM: int = 384


def utc_now() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


class Document(Base):
    """Uploaded PDF document record."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(String(32), default="processing", nullable=False)
    clean_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    sentences = relationship("Sentence", back_populates="document", cascade="all, delete-orphan")
    annotations = relationship("Annotation", back_populates="document", cascade="all, delete-orphan")
    relations = relationship("Relation", back_populates="document", cascade="all, delete-orphan")
    suggestions = relationship("Suggestion", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    mentions = relationship("Mention", back_populates="document", cascade="all, delete-orphan")
    graph_relations = relationship("GraphRelation", back_populates="document", cascade="all, delete-orphan")
    extraction_runs = relationship("ExtractionRun", back_populates="document", cascade="all, delete-orphan")
    propositions = relationship("Proposition", back_populates="document", cascade="all, delete-orphan")
    concepts = relationship("Concept", back_populates="document", cascade="all, delete-orphan")
    graph_edges = relationship("GraphEdge", back_populates="document", cascade="all, delete-orphan")


class Sentence(Base):
    """Segmented sentence with character offsets and optional embedding."""

    __tablename__ = "sentences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    idx = Column(Integer, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    page = Column(Integer, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)

    document = relationship("Document", back_populates="sentences")
    suggestions = relationship("Suggestion", back_populates="sentence", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint('start < "end"', name="check_sentence_start_lt_end"),
        Index(
            "ix_sentences_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class Annotation(Base):
    """User or system created passage annotation."""

    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    quote = Column(Text, nullable=False)
    label = Column(String(64), nullable=False)
    note = Column(Text, nullable=True)
    x = Column(Float, default=0.0, nullable=False)
    y = Column(Float, default=0.0, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    document = relationship("Document", back_populates="annotations")
    chunks = relationship("Chunk", secondary="annotation_chunks", back_populates="annotations")

    __mapper_args__ = {
        "version_id_col": version,
    }
    __table_args__ = (
        CheckConstraint('start < "end"', name="check_annotation_start_lt_end"),
        UniqueConstraint("document_id", "start", "end", "label", name="uq_annotations_doc_start_end_label"),
    )


class Relation(Base):
    """Typed connection between two annotations."""

    __tablename__ = "relations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("annotations.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("annotations.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(64), nullable=False)
    status = Column(String(32), default="confirmed", nullable=False)
    cos_score = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)

    document = relationship("Document", back_populates="relations")
    source = relationship("Annotation", foreign_keys=[source_id])
    target = relationship("Annotation", foreign_keys=[target_id])

    @property
    def score(self) -> Any:
        return self.cos_score

    __mapper_args__ = {
        "version_id_col": version,
    }
    __table_args__ = (
        CheckConstraint("source_id != target_id", name="check_no_self_link"),
    )


class RelationCache(Base):
    """Cached relation inference result for an annotation text pair."""

    __tablename__ = "relation_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(64), unique=True, index=True, nullable=False)
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class RejectedPair(Base):
    """User-rejected or deleted candidate annotation pair to prevent re-suggesting."""

    __tablename__ = "rejected_pairs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    ann_id_min = Column(Integer, nullable=False)
    ann_id_max = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "ann_id_min", "ann_id_max", name="uq_rejected_pairs_doc_ann_pair"),
    )


class Suggestion(Base):
    """Suggested highlight for a sentence based on embedding rank."""

    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    sentence_id = Column(Integer, ForeignKey("sentences.id", ondelete="CASCADE"), nullable=False, index=True)
    seed_annotation_id = Column(Integer, ForeignKey("annotations.id", ondelete="SET NULL"), nullable=True, index=True)
    label = Column(String(64), nullable=True)
    scope = Column(String(32), default="passage", nullable=True)
    score = Column(Float, nullable=False)
    status = Column(String(32), default="pending", nullable=False)

    document = relationship("Document", back_populates="suggestions")
    sentence = relationship("Sentence", back_populates="suggestions")
    seed_annotation = relationship("Annotation", foreign_keys=[seed_annotation_id])



class Job(Base):
    """Asynchronous background job execution log."""

    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True)
    type = Column(String(64), nullable=False)
    document_id = Column(Integer, nullable=True, index=True)
    status = Column(String(32), default="queued", nullable=False)
    progress = Column(Integer, default=0, nullable=False)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


# --- Unified Node Epistemology & GraphRAG Layer (Phase 2) ---


class Chunk(Base):
    """Token-bounded contextual chunk spanning one or more sentences."""

    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    page = Column(Integer, default=1, nullable=False)
    first_sentence_idx = Column(Integer, nullable=False)
    last_sentence_idx = Column(Integer, nullable=False)
    token_count = Column(Integer, nullable=False)
    text = Column(Text, nullable=True)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    document = relationship("Document", back_populates="chunks")
    mentions = relationship("Mention", back_populates="chunk")
    annotations = relationship("Annotation", secondary="annotation_chunks", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_doc_idx"),
        CheckConstraint('start < "end"', name="check_chunk_start_lt_end"),
        Index("idx_chunks_doc_offsets", "document_id", "start", "end"),
    )


class AnnotationChunk(Base):
    """Many-to-many link between annotations and overlapping lexical chunks."""

    __tablename__ = "annotation_chunks"

    annotation_id = Column(Integer, ForeignKey("annotations.id", ondelete="CASCADE"), primary_key=True, index=True)
    chunk_id = Column(Integer, ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True, index=True)



class Node(Base):
    """Unified polymorphic node representing Global Concepts or Document-Local Claims."""

    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    normalized_name = Column(String(255), nullable=False, index=True)
    node_type = Column(String(64), nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_global = Column(Boolean, default=True, nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    legacy_label = Column(String(64), nullable=True)
    merged_into_id = Column(Integer, ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True, index=True)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    aliases = relationship("NodeAlias", back_populates="node", cascade="all, delete-orphan")
    mentions = relationship("Mention", back_populates="node", cascade="all, delete-orphan")
    merged_into = relationship("Node", remote_side=[id], foreign_keys=[merged_into_id])

    __table_args__ = (
        Index(
            "uq_global_nodes",
            "normalized_name",
            "node_type",
            unique=True,
            postgresql_where=text("is_global = true AND merged_into_id IS NULL"),
        ),
        Index(
            "uq_doc_claim_nodes",
            "document_id",
            "normalized_name",
            "node_type",
            unique=True,
            postgresql_where=text("is_global = false AND document_id IS NOT NULL AND merged_into_id IS NULL"),
        ),
    )


class NodeAlias(Base):
    """Surface forms, abbreviations, and synonyms mapped to a canonical node."""

    __tablename__ = "node_aliases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    alias = Column(String(255), nullable=False)
    normalized_alias = Column(String(255), nullable=False, index=True)
    source = Column(String(32), default="extracted", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    node = relationship("Node", back_populates="aliases")

    __table_args__ = (
        UniqueConstraint("node_id", "normalized_alias", name="uq_node_alias"),
        Index("idx_aliases_norm", "normalized_alias"),
    )


class EntityMergeLog(Base):
    """Audit trail of entity merges enabling inspection and reversibility."""

    __tablename__ = "entity_merge_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    surviving_node_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    absorbed_node_id = Column(Integer, nullable=False)
    absorbed_name = Column(String(255), nullable=False)
    absorbed_type = Column(String(64), nullable=False)
    adjudication_reason = Column(Text, nullable=False)
    adjudicated_by = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    reverted_at = Column(DateTime, nullable=True)


class EntityMergePending(Base):
    """Queue for ambiguous entity pairs requiring review or LLM confirmation."""

    __tablename__ = "entity_merge_pending"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_a_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_b_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    similarity = Column(Float, nullable=False)
    llm_adjudication_verdict = Column(String(32), nullable=True)
    llm_reason = Column(Text, nullable=True)
    status = Column(String(32), default="pending", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    candidate_a = relationship("Node", foreign_keys=[candidate_a_id])
    candidate_b = relationship("Node", foreign_keys=[candidate_b_id])

    __table_args__ = (
        UniqueConstraint("candidate_a_id", "candidate_b_id", name="uq_merge_pending_pair"),
    )


class Mention(Base):
    """Concrete textual occurrence of a node anchored in clean_text."""

    __tablename__ = "mentions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(Integer, ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True, index=True)
    node_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    quote = Column(Text, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    page = Column(Integer, nullable=False)
    note = Column(Text, nullable=True)
    x = Column(Float, default=0.0, nullable=False)
    y = Column(Float, default=0.0, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    status = Column(String(32), default="confirmed", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    document = relationship("Document", back_populates="mentions")
    chunk = relationship("Chunk", back_populates="mentions")
    node = relationship("Node", back_populates="mentions")

    __table_args__ = (
        CheckConstraint('start < "end"', name="check_mention_start_lt_end"),
        UniqueConstraint("document_id", "start", "end", "node_id", name="uq_mentions_doc_span_node"),
        Index("idx_mentions_doc_offsets", "document_id", "start", "end"),
    )


class GraphRelation(Base):
    """Typed semantic directional relationship connecting two canonical nodes."""

    __tablename__ = "graph_relations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    source_node_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_node_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type = Column(String(64), nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    status = Column(String(32), default="confirmed", nullable=False)
    is_legacy = Column(Boolean, default=False, nullable=False)
    reason = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    document = relationship("Document", back_populates="graph_relations")
    source_node = relationship("Node", foreign_keys=[source_node_id])
    target_node = relationship("Node", foreign_keys=[target_node_id])
    evidence_items = relationship("RelationEvidence", back_populates="relation", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("source_node_id != target_node_id", name="check_graph_rel_no_self_link"),
        Index(
            "uq_doc_graph_relations",
            "document_id",
            "source_node_id",
            "target_node_id",
            "relation_type",
            unique=True,
            postgresql_where=text("document_id IS NOT NULL"),
        ),
        Index(
            "uq_cross_doc_graph_relations",
            "source_node_id",
            "target_node_id",
            "relation_type",
            unique=True,
            postgresql_where=text("document_id IS NULL"),
        ),
        Index("idx_rel_src_tgt", "source_node_id", "target_node_id"),
    )


class RelationEvidence(Base):
    """Verbatim text span grounding a relationship back to source document clean_text."""

    __tablename__ = "relation_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    relation_id = Column(Integer, ForeignKey("graph_relations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    sentence_id = Column(Integer, ForeignKey("sentences.id", ondelete="CASCADE"), nullable=True, index=True)
    verbatim_quote = Column(Text, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    relation = relationship("GraphRelation", back_populates="evidence_items")
    document = relationship("Document")
    sentence = relationship("Sentence")

    __table_args__ = (
        UniqueConstraint("relation_id", "start", "end", name="uq_evidence_relation_span"),
        CheckConstraint('start < "end"', name="check_evidence_start_lt_end"),
    )


# --- Epistemic Knowledge Graph V2 Models ---


class ExtractionRun(Base):
    """Container for a specific extraction version and parameter configuration."""

    __tablename__ = "extraction_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    graph_version = Column(Integer, default=2, nullable=False)
    model_name = Column(String(128), nullable=False)
    prompt_version = Column(String(64), nullable=False)
    config = Column(JSONB, default=dict, nullable=False)
    status = Column(String(32), default="draft", nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    document = relationship("Document", back_populates="extraction_runs")
    propositions = relationship("Proposition", back_populates="run", cascade="all, delete-orphan")
    concepts = relationship("Concept", back_populates="run", cascade="all, delete-orphan")
    edges = relationship("GraphEdge", back_populates="run", cascade="all, delete-orphan")
    activation_history = relationship("ExtractionRunActivationHistory", foreign_keys="ExtractionRunActivationHistory.run_id", cascade="all, delete-orphan")
    legacy_reviews = relationship("LegacyEdgeReview", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index(
            "uq_active_run_per_doc",
            "document_id",
            unique=True,
            postgresql_where=text("is_active = true"),
            sqlite_where=text("is_active = 1"),
        ),
    )


class Proposition(Base):
    """Normalized, self-contained semantic assertion extracted from one or more highlights."""

    __tablename__ = "propositions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id = Column(Integer, ForeignKey("extraction_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_statement = Column(Text, nullable=False)
    statement_type = Column(String(32), nullable=False)
    summary = Column(Text, nullable=True)
    confidence = Column(Numeric(4, 3), nullable=False)
    review_status = Column(String(32), default="auto_candidate", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    document = relationship("Document", back_populates="propositions")
    run = relationship("ExtractionRun", back_populates="propositions")
    highlights = relationship("Annotation", secondary="proposition_highlights")
    concepts = relationship("Concept", secondary="proposition_concept_links", back_populates="propositions")

    __table_args__ = (
        Index("idx_props_run_type", "run_id", "statement_type"),
    )


class Concept(Base):
    """Canonical domain concept or entity."""

    __tablename__ = "concepts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id = Column(Integer, ForeignKey("extraction_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    canonical_name = Column(String(255), nullable=False)
    category = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    document = relationship("Document", back_populates="concepts")
    run = relationship("ExtractionRun", back_populates="concepts")
    propositions = relationship("Proposition", secondary="proposition_concept_links", back_populates="concepts")

    __table_args__ = (
        UniqueConstraint("run_id", "canonical_name", name="uq_run_canonical_concept"),
    )


class PropositionHighlight(Base):
    """Junction table connecting propositions to their supporting raw highlight spans."""

    __tablename__ = "proposition_highlights"

    proposition_id = Column(Integer, ForeignKey("propositions.id", ondelete="CASCADE"), primary_key=True)
    highlight_id = Column(Integer, ForeignKey("annotations.id", ondelete="CASCADE"), primary_key=True)


class PropositionConceptLink(Base):
    """Junction table grounding concepts mentioned in propositions."""

    __tablename__ = "proposition_concept_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    proposition_id = Column(Integer, ForeignKey("propositions.id", ondelete="CASCADE"), nullable=False, index=True)
    concept_id = Column(Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    mention_type = Column(String(64), default="mentions", nullable=False)

    __table_args__ = (
        UniqueConstraint("proposition_id", "concept_id", name="uq_prop_concept_link"),
    )


class GraphEdge(Base):
    """High-precision typed argument edge between propositions and/or concepts."""

    __tablename__ = "graph_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id = Column(Integer, ForeignKey("extraction_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_kind = Column(String(32), nullable=False)
    source_id = Column(Integer, nullable=False)
    target_kind = Column(String(32), nullable=False)
    target_id = Column(Integer, nullable=False)
    relation_type = Column(String(64), nullable=False)
    direction = Column(String(16), default="forward", nullable=False)
    confidence = Column(Numeric(4, 3), nullable=False)
    rationale = Column(Text, nullable=False)
    review_status = Column(String(32), default="auto_candidate", nullable=False)
    extraction_method = Column(String(32), default="llm", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    document = relationship("Document", back_populates="graph_edges")
    run = relationship("ExtractionRun", back_populates="edges")
    evidence_items = relationship("EdgeEvidence", back_populates="edge", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="chk_edge_confidence_bounds"),
        CheckConstraint("NOT (source_kind = target_kind AND source_id = target_id)", name="chk_edge_no_self_loops"),
        Index("idx_graph_edges_run_conf", "run_id", "confidence", "review_status"),
        Index("idx_graph_edges_run_src", "run_id", "source_kind", "source_id"),
        Index("idx_graph_edges_run_tgt", "run_id", "target_kind", "target_id"),
    )


class EdgeEvidence(Base):
    """Exact verbatim source quote provenance grounding a graph edge."""

    __tablename__ = "edge_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    edge_id = Column(Integer, ForeignKey("graph_edges.id", ondelete="CASCADE"), nullable=False, index=True)
    highlight_id = Column(Integer, ForeignKey("annotations.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_quote = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    edge = relationship("GraphEdge", back_populates="evidence_items")
    highlight = relationship("Annotation")


class ExtractionRunActivationHistory(Base):
    """Audit log tracking all run activations and rollbacks."""

    __tablename__ = "extraction_run_activation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id = Column(Integer, ForeignKey("extraction_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_run_id = Column(Integer, ForeignKey("extraction_runs.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(32), nullable=False)
    activated_by = Column(String(128), default="admin", nullable=False)
    reason = Column(Text, nullable=True)
    activated_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_activation_doc_time", "document_id", "activated_at"),
    )


class LegacyEdgeReview(Base):
    """Review decisions mapping legacy V1 relations to V2 graph structures."""

    __tablename__ = "legacy_edge_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("extraction_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    legacy_relation_id = Column(Integer, ForeignKey("relations.id", ondelete="CASCADE"), nullable=False, index=True)
    classification = Column(String(64), nullable=False)
    reviewer_reason = Column(Text, nullable=True)
    mapped_edge_id = Column(Integer, ForeignKey("graph_edges.id", ondelete="SET NULL"), nullable=True)
    reviewed_by = Column(String(128), default="reviewer", nullable=False)
    reviewed_at = Column(DateTime, default=utc_now, nullable=False)

    run = relationship("ExtractionRun", back_populates="legacy_reviews")
    legacy_relation = relationship("Relation")
    mapped_edge = relationship("GraphEdge")

    __table_args__ = (
        CheckConstraint(
            "classification IN ('retained', 'merged', 'demoted_to_review', 'rejected', 'replaced_by_new_edge')",
            name="chk_legacy_review_classification",
        ),
        UniqueConstraint("run_id", "legacy_relation_id", name="uq_run_legacy_rel_review"),
    )




