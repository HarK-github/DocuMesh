"""SQLAlchemy data models for documents, annotations, relations, and jobs."""

from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    LargeBinary,
    JSON,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


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


class Sentence(Base):
    """Segmented sentence with character offsets and optional embedding."""

    __tablename__ = "sentences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    idx = Column(Integer, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    page = Column(Integer, nullable=False)
    embedding = Column(LargeBinary, nullable=True)

    document = relationship("Document", back_populates="sentences")
    suggestions = relationship("Suggestion", back_populates="sentence", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("start < end", name="check_sentence_start_lt_end"),
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

    __mapper_args__ = {
        "version_id_col": version,
    }
    __table_args__ = (
        CheckConstraint("start < end", name="check_annotation_start_lt_end"),
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



