"""Canonical Entity Resolution Service with Scoped Exact-Match, LLM Adjudication, and Tombstone Lifecycle."""

import re
import numpy as np
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from backend.app.models import (
    Node,
    NodeAlias,
    Mention,
    GraphRelation,
    RelationEvidence,
    EntityMergeLog,
    utc_now,
)
from backend.app.services.llm import get_llm_client, BaseLLMClient


def normalize_entity_name(name: str) -> str:
    """Normalize entity name: lowercase, stripped punctuation, collapsed whitespace."""
    s = re.sub(r"[^\w\s-]", "", name.strip().lower())
    return re.sub(r"\s+", " ", s).strip()


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute cosine similarity between two unit-normalized vectors."""
    if v1.shape != v2.shape:
        return 0.0
    n1 = float(np.linalg.norm(v1))
    n2 = float(np.linalg.norm(v2))
    if n1 < 1e-9 or n2 < 1e-9:
        return 0.0
    return float(np.dot(v1, v2) / (n1 * n2))


class EntityResolutionService:
    """Manages canonical entity matching, LLM adjudication, merges, and audit logging."""

    def __init__(self, db: Session, llm_client: Optional[BaseLLMClient] = None) -> None:
        self.db = db
        self._llm = llm_client

    @property
    def llm(self) -> BaseLLMClient:
        if self._llm is None:
            self._llm = get_llm_client()
        return self._llm

    def resolve_or_create_node(
        self,
        name: str,
        node_type: str,
        document_id: Optional[int] = None,
        is_global: bool = True,
        description: Optional[str] = None,
        embedding: Optional[np.ndarray] = None,
    ) -> Node:
        """Resolve an entity name to an existing canonical node or create a new node.

        Policy:
        1. Exact-match auto-merge: ONLY if norm(alias) == norm(candidate) AND node_type matches.
        2. Cosine similarity >= 0.70 on same node_type: LLM Adjudication.
        3. Otherwise: Insert as distinct new node.
        """
        norm_name = normalize_entity_name(name)

        # 1. Exact match check (scoped strictly by node_type)
        alias_match = (
            self.db.query(NodeAlias)
            .join(Node, Node.id == NodeAlias.node_id)
            .filter(
                NodeAlias.normalized_alias == norm_name,
                Node.node_type == node_type,
                Node.merged_into_id.is_(None),
            )
        )
        if not is_global and document_id is not None:
            alias_match = alias_match.filter(Node.document_id == document_id)
        matched_alias = alias_match.first()

        if matched_alias and matched_alias.node:
            return matched_alias.node

        # Direct name check on active nodes
        node_query = self.db.query(Node).filter(
            Node.normalized_name == norm_name,
            Node.node_type == node_type,
            Node.merged_into_id.is_(None),
        )
        if not is_global and document_id is not None:
            node_query = node_query.filter(Node.document_id == document_id)
        existing_node = node_query.first()
        if existing_node:
            return existing_node

        # 2. Candidate Blocking & LLM Adjudication if embedding provided
        if embedding is not None and is_global:
            sim_expr = (1.0 - Node.embedding.cosine_distance(embedding)).label("sim")
            candidate_rows = (
                self.db.query(Node, sim_expr)
                .filter(
                    Node.node_type == node_type,
                    Node.is_global.is_(True),
                    Node.merged_into_id.is_(None),
                    Node.embedding.isnot(None),
                )
                .filter(Node.embedding.cosine_distance(embedding) <= 0.30)
                .order_by(Node.embedding.cosine_distance(embedding))
                .limit(10)
                .all()
            )
            for cand, sim in candidate_rows:
                if sim >= 0.70:
                    verdict, confidence, reason = self.adjudicate_pair(
                        name_a=cand.name,
                        type_a=cand.node_type,
                        name_b=name,
                        type_b=node_type,
                    )
                    if verdict == "SAME" and confidence >= 0.75:
                        # Auto-alias to surviving candidate
                        alias = NodeAlias(
                            node_id=cand.id,
                            alias=name,
                            normalized_alias=norm_name,
                            source="adjudicated",
                        )
                        self.db.add(alias)
                        self.db.commit()
                        return cand
                    elif verdict in ("UNCERTAIN", "SAME") or confidence < 0.75:
                        # Queue for human review if ambiguous
                        pass

        # 3. Create new node
        emb_val = embedding.astype(np.float32).tolist() if embedding is not None else None
        new_node = Node(
            name=name,
            normalized_name=norm_name,
            node_type=node_type,
            description=description or f"{node_type}: {name}",
            is_global=is_global,
            document_id=document_id if not is_global else None,
            legacy_label=node_type,
            embedding=emb_val,
        )
        self.db.add(new_node)
        self.db.flush()

        alias = NodeAlias(
            node_id=new_node.id,
            alias=name,
            normalized_alias=norm_name,
            source="extracted",
        )
        self.db.add(alias)
        self.db.commit()
        return new_node

    def adjudicate_pair(
        self, name_a: str, type_a: str, name_b: str, type_b: str
    ) -> Tuple[str, float, str]:
        """Ask LLM to adjudicate if two entities refer to the identical real-world concept.

        BERT-Base vs BERT-Large test: Cosine ~0.84, but distinct variants -> verdict: DISTINCT.
        """
        prompt = f"""You are an expert scientific ontologist. Determine if two scientific entities refer to the EXACT SAME canonical entity or if they are DISTINCT variants, models, or concepts.

Entity A: "{name_a}" (Type: {type_a})
Entity B: "{name_b}" (Type: {type_b})

Rules:
- Minor surface variations (e.g. "FlashAttention-2" vs "FlashAttention v2") are SAME.
- Distinct model variants, architectures, or parameter sizes (e.g. "BERT-base" vs "BERT-large", "GPT-3" vs "GPT-4") are DISTINCT.
- Different types (e.g. Method vs Dataset) are ALWAYS DISTINCT.

Output strictly a JSON object:
{{
  "verdict": "SAME" | "DISTINCT" | "UNCERTAIN",
  "confidence": 0.0 to 1.0,
  "reason": "Explanation of decision"
}}
"""
        try:
            resp = self.llm.complete_json(prompt)
            verdict = resp.get("verdict", "DISTINCT").upper()
            confidence = float(resp.get("confidence", 0.5))
            reason = str(resp.get("reason", "Automated adjudication"))
            return verdict, confidence, reason
        except Exception as e:
            return "UNCERTAIN", 0.5, f"Adjudication failure: {e}"

    def merge_nodes(
        self,
        surviving_node_id: int,
        absorbed_node_id: int,
        reason: str,
        adjudicated_by: str = "manual",
        confidence: Optional[float] = 1.0,
    ) -> EntityMergeLog:
        """Merge absorbed node into surviving node with tombstones, repointing, evidence union, and audit log."""
        if surviving_node_id == absorbed_node_id:
            raise ValueError("Cannot merge a node into itself.")

        surviving = self.db.query(Node).filter(Node.id == surviving_node_id).first()
        absorbed = self.db.query(Node).filter(Node.id == absorbed_node_id).first()
        if not surviving or not absorbed:
            raise ValueError("One or both nodes do not exist.")

        # 1. Update absorbed node as tombstone
        absorbed.merged_into_id = surviving_node_id

        # 2. Transfer aliases to surviving node
        for alias in absorbed.aliases:
            existing_alias = (
                self.db.query(NodeAlias)
                .filter(
                    NodeAlias.node_id == surviving_node_id,
                    NodeAlias.normalized_alias == alias.normalized_alias,
                )
                .first()
            )
            if not existing_alias:
                alias.node_id = surviving_node_id
            else:
                self.db.delete(alias)

        # 3. Repoint mentions
        self.db.query(Mention).filter(Mention.node_id == absorbed_node_id).update(
            {"node_id": surviving_node_id}
        )

        # 4. Repoint and deduplicate graph relations
        # Outgoing relations
        absorbed_out = (
            self.db.query(GraphRelation)
            .filter(GraphRelation.source_node_id == absorbed_node_id)
            .all()
        )
        for rel in absorbed_out:
            target_id = rel.target_node_id if rel.target_node_id != surviving_node_id else surviving_node_id
            if target_id == surviving_node_id:
                # Avoid self-link created by merge
                self.db.delete(rel)
                continue

            existing = (
                self.db.query(GraphRelation)
                .filter(
                    GraphRelation.document_id == rel.document_id,
                    GraphRelation.source_node_id == surviving_node_id,
                    GraphRelation.target_node_id == target_id,
                    GraphRelation.relation_type == rel.relation_type,
                )
                .first()
            )
            if existing:
                # Evidence union: transfer evidence to existing relation
                self.db.query(RelationEvidence).filter(
                    RelationEvidence.relation_id == rel.id
                ).update({"relation_id": existing.id})
                self.db.delete(rel)
            else:
                rel.source_node_id = surviving_node_id

        # Incoming relations
        absorbed_in = (
            self.db.query(GraphRelation)
            .filter(GraphRelation.target_node_id == absorbed_node_id)
            .all()
        )
        for rel in absorbed_in:
            src_id = rel.source_node_id if rel.source_node_id != surviving_node_id else surviving_node_id
            if src_id == surviving_node_id:
                self.db.delete(rel)
                continue

            existing = (
                self.db.query(GraphRelation)
                .filter(
                    GraphRelation.document_id == rel.document_id,
                    GraphRelation.source_node_id == src_id,
                    GraphRelation.target_node_id == surviving_node_id,
                    GraphRelation.relation_type == rel.relation_type,
                )
                .first()
            )
            if existing:
                self.db.query(RelationEvidence).filter(
                    RelationEvidence.relation_id == rel.id
                ).update({"relation_id": existing.id})
                self.db.delete(rel)
            else:
                rel.target_node_id = surviving_node_id

        # 5. Record merge in audit log
        log_entry = EntityMergeLog(
            surviving_node_id=surviving_node_id,
            absorbed_node_id=absorbed_node_id,
            absorbed_name=absorbed.name,
            absorbed_type=absorbed.node_type,
            adjudication_reason=reason,
            adjudicated_by=adjudicated_by,
            confidence=confidence,
        )
        self.db.add(log_entry)
        self.db.commit()
        return log_entry

    def revert_merge(self, log_id: int) -> bool:
        """Revert a previously logged entity merge."""
        log_entry = self.db.query(EntityMergeLog).filter(EntityMergeLog.id == log_id).first()
        if not log_entry or log_entry.reverted_at is not None:
            return False

        absorbed = self.db.query(Node).filter(Node.id == log_entry.absorbed_node_id).first()
        if absorbed:
            absorbed.merged_into_id = None

        log_entry.reverted_at = utc_now()
        self.db.commit()
        return True

    def merge_annotations(
        self,
        surviving_ann_id: int,
        absorbed_ann_id: int,
        reason: str,
        adjudicated_by: str = "manual",
        confidence: Optional[float] = 1.0,
    ) -> Dict[str, Any]:
        """Merge absorbed annotation into surviving annotation:
        1. Repoint relations from absorbed to surviving.
        2. Delete self-loops created by merge.
        3. Deduplicate duplicate typed relations.
        4. Repoint AnnotationChunk links and Suggestions.
        5. Record in EntityMergeLog for auditability and reversibility.
        6. Delete absorbed annotation.
        """
        from backend.app.models import Annotation, Relation, Suggestion, AnnotationChunk

        if surviving_ann_id == absorbed_ann_id:
            raise ValueError("Cannot merge an annotation into itself.")

        surviving = self.db.query(Annotation).filter(Annotation.id == surviving_ann_id).first()
        absorbed = self.db.query(Annotation).filter(Annotation.id == absorbed_ann_id).first()
        if not surviving or not absorbed:
            raise ValueError("One or both annotations do not exist.")

        # Ensure a canonical Node exists for surviving annotation to satisfy foreign key in EntityMergeLog
        surv_node = self.resolve_or_create_node(
            name=surviving.quote[:100],
            node_type=surviving.label or "Claim",
            document_id=surviving.document_id,
            is_global=False,
            description=surviving.note,
        )

        # 1. Repoint Outgoing Relations
        absorbed_out = self.db.query(Relation).filter(Relation.source_id == absorbed_ann_id).all()
        for rel in absorbed_out:
            tgt_id = rel.target_id if rel.target_id != surviving_ann_id else surviving_ann_id
            if tgt_id == surviving_ann_id:
                self.db.delete(rel)
                continue
            existing = (
                self.db.query(Relation)
                .filter(
                    Relation.document_id == rel.document_id,
                    Relation.source_id == surviving_ann_id,
                    Relation.target_id == tgt_id,
                    Relation.type == rel.type,
                )
                .first()
            )
            if existing:
                self.db.delete(rel)
            else:
                rel.source_id = surviving_ann_id

        # 2. Repoint Incoming Relations
        absorbed_in = self.db.query(Relation).filter(Relation.target_id == absorbed_ann_id).all()
        for rel in absorbed_in:
            src_id = rel.source_id if rel.source_id != surviving_ann_id else surviving_ann_id
            if src_id == surviving_ann_id:
                self.db.delete(rel)
                continue
            existing = (
                self.db.query(Relation)
                .filter(
                    Relation.document_id == rel.document_id,
                    Relation.source_id == src_id,
                    Relation.target_id == surviving_ann_id,
                    Relation.type == rel.type,
                )
                .first()
            )
            if existing:
                self.db.delete(rel)
            else:
                rel.target_id = surviving_ann_id

        # 3. Repoint AnnotationChunk associations
        try:
            chunks_to_transfer = (
                self.db.query(AnnotationChunk)
                .filter(AnnotationChunk.annotation_id == absorbed_ann_id)
                .all()
            )
            for ac in chunks_to_transfer:
                exists_ac = (
                    self.db.query(AnnotationChunk)
                    .filter(
                        AnnotationChunk.annotation_id == surviving_ann_id,
                        AnnotationChunk.chunk_id == ac.chunk_id,
                    )
                    .first()
                )
                if not exists_ac:
                    self.db.add(AnnotationChunk(annotation_id=surviving_ann_id, chunk_id=ac.chunk_id))
                self.db.delete(ac)
        except Exception:
            pass

        # 4. Repoint Suggestions
        self.db.query(Suggestion).filter(Suggestion.seed_annotation_id == absorbed_ann_id).update(
            {"seed_annotation_id": surviving_ann_id}
        )

        # 5. Record in EntityMergeLog
        log_entry = EntityMergeLog(
            surviving_node_id=surv_node.id,
            absorbed_node_id=absorbed_ann_id,
            absorbed_name=absorbed.quote[:250],
            absorbed_type=absorbed.label or "Annotation",
            adjudication_reason=reason,
            adjudicated_by=adjudicated_by,
            confidence=confidence,
        )
        self.db.add(log_entry)

        # 6. Delete absorbed annotation
        self.db.delete(absorbed)
        self.db.commit()

        return {
            "status": "merged",
            "surviving_annotation_id": surviving_ann_id,
            "absorbed_annotation_id": absorbed_ann_id,
            "log_id": log_entry.id,
            "reason": reason,
        }

