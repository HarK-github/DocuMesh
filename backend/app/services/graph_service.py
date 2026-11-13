"""In-memory NetworkX MultiDiGraph projection service with multi-hop BFS and RRF retrieval."""

import re
from typing import Dict, Any, List, Optional, Set, Tuple
import networkx as nx
import numpy as np
from sqlalchemy.orm import Session

from backend.app.models import (
    Node,
    NodeAlias,
    Mention,
    GraphRelation,
    RelationEvidence,
    Sentence,
)
from backend.app.services.embedder import BaseEmbedder, get_embedder
from backend.app.services.ranker import cosine_similarity


class GraphProjectionService:
    """Maintains an in-memory NetworkX MultiDiGraph projection of the knowledge graph."""

    def __init__(self, db: Session, embedder: Optional[BaseEmbedder] = None) -> None:
        self.db = db
        self.embedder = embedder or get_embedder()
        self.graph = nx.MultiDiGraph()
        self._load_projection()

    def _load_projection(self) -> None:
        """Load active nodes, aliases, graph relations, and relation evidence into NetworkX."""
        self.graph.clear()

        # Load active nodes
        nodes = self.db.query(Node).filter(Node.merged_into_id.is_(None)).all()
        for n in nodes:
            emb_vec = None
            if n.embedding is not None:
                emb_vec = np.asarray(n.embedding, dtype=np.float32)
            self.graph.add_node(
                n.id,
                name=n.name,
                normalized_name=n.normalized_name,
                node_type=n.node_type,
                description=n.description,
                is_global=n.is_global,
                document_id=n.document_id,
                embedding=emb_vec,
            )

        # Load active relations
        relations = (
            self.db.query(GraphRelation)
            .filter(
                GraphRelation.source_node_id.in_(self.graph.nodes),
                GraphRelation.target_node_id.in_(self.graph.nodes),
            )
            .all()
        )

        # Pre-fetch evidence items grouped by relation_id
        all_evidence = self.db.query(RelationEvidence).all()
        ev_by_rel: Dict[int, List[Dict[str, Any]]] = {}
        for ev in all_evidence:
            ev_by_rel.setdefault(ev.relation_id, []).append({
                "id": ev.id,
                "document_id": ev.document_id,
                "sentence_id": ev.sentence_id,
                "verbatim_quote": ev.verbatim_quote,
                "start": ev.start,
                "end": ev.end,
            })

        for r in relations:
            self.graph.add_edge(
                r.source_node_id,
                r.target_node_id,
                key=r.id,
                id=r.id,
                relation_type=r.relation_type,
                confidence=r.confidence,
                status=r.status,
                is_legacy=r.is_legacy,
                reason=r.reason,
                document_id=r.document_id,
                evidence=ev_by_rel.get(r.id, []),
            )

    def find_seed_nodes(
        self,
        question: str,
        q_emb: np.ndarray,
        document_id: Optional[int] = None,
        top_k_vector_sentences: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[int, float]:
        """Find seed nodes combining lexical query matches, dense concept matches, and vector-linked entities."""
        seed_scores: Dict[int, float] = {}
        norm_q = re.sub(r"[^\w\s-]", "", question.lower()).strip()
        q_tokens = set(norm_q.split())

        # 1. Lexical Query Matching against node names and aliases
        aliases = (
            self.db.query(NodeAlias)
            .join(Node, Node.id == NodeAlias.node_id)
            .filter(Node.merged_into_id.is_(None))
            .all()
        )
        for a in aliases:
            if a.node_id in self.graph.nodes:
                if a.normalized_alias in norm_q or any(tok in a.normalized_alias.split() for tok in q_tokens if len(tok) >= 4):
                    seed_scores[a.node_id] = max(seed_scores.get(a.node_id, 0.0), 1.0)

        # 2. Dense Concept Node Matches (Sim >= 0.75)
        for node_id, data in self.graph.nodes(data=True):
            if document_id is not None and not data.get("is_global") and data.get("document_id") != document_id:
                continue
            emb = data.get("embedding")
            if emb is not None:
                sim = cosine_similarity(q_emb, emb)
                if sim >= 0.75:
                    seed_scores[node_id] = max(seed_scores.get(node_id, 0.0), float(sim))

        # 3. Vector-Linked Entities (Mentions connected to top-k vector sentence hits)
        if top_k_vector_sentences:
            for s in top_k_vector_sentences:
                s_score = float(s.get("score", 0.5))
                # Find mentions covering or matching sentence span
                mentions = (
                    self.db.query(Mention)
                    .filter(
                        Mention.document_id == s.get("document_id", document_id),
                        Mention.start >= s.get("start", 0),
                        Mention.end <= s.get("end", 0) + 50,
                    )
                    .all()
                )
                for m in mentions:
                    if m.node_id in self.graph.nodes:
                        seed_scores[m.node_id] = max(seed_scores.get(m.node_id, 0.0), s_score)

        return seed_scores

    def expand_graph_context(
        self,
        seed_scores: Dict[int, float],
        max_hops: int = 2,
        document_id: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Perform 1-2 hop bidirectional BFS traversal from seed nodes, scoring edges and harvesting evidence."""
        if not seed_scores:
            return [], []

        traversed_edges: Dict[int, Dict[str, Any]] = {}
        evidence_sentences: Dict[int, Dict[str, Any]] = {}

        # BFS queue: (node_id, hop_level, accumulated_node_score)
        queue = [(nid, 0, score) for nid, score in seed_scores.items()]
        visited_nodes: Set[Tuple[int, int]] = set()

        while queue:
            curr_node, hop, curr_score = queue.pop(0)
            if (curr_node, hop) in visited_nodes or hop >= max_hops:
                continue
            visited_nodes.add((curr_node, hop))

            # Outgoing and incoming edges (bidirectional traversal)
            all_incident_edges = list(self.graph.out_edges(curr_node, data=True, keys=True)) + [
                (u, v, k, d) for u, v, k, d in self.graph.in_edges(curr_node, data=True, keys=True)
            ]

            # Super-node dampening: penalize nodes with degree > 50 unless in seed set
            node_degree = self.graph.degree(curr_node)
            degree_penalty = 0.5 if (node_degree > 50 and curr_node not in seed_scores) else 1.0

            for u, v, key, edge_data in all_incident_edges:
                e_doc_id = edge_data.get("document_id")
                if document_id is not None and e_doc_id is not None and e_doc_id != document_id:
                    continue

                rel_id = edge_data["id"]
                neighbor = v if u == curr_node else u

                conf = edge_data.get("confidence", 1.0)
                legacy_mult = 0.50 if edge_data.get("is_legacy") else 1.0
                hop_decay = 0.80 ** (hop + 1)

                edge_score = max(curr_score, seed_scores.get(neighbor, 0.0)) * conf * hop_decay * legacy_mult * degree_penalty

                if rel_id not in traversed_edges or edge_score > traversed_edges[rel_id]["score"]:
                    traversed_edges[rel_id] = {
                        "id": rel_id,
                        "source_node_id": u,
                        "target_node_id": v,
                        "relation_type": edge_data["relation_type"],
                        "confidence": conf,
                        "is_legacy": edge_data["is_legacy"],
                        "reason": edge_data.get("reason"),
                        "score": float(edge_score),
                        "hop": hop + 1,
                    }

                # Harvest evidence sentences
                for ev in edge_data.get("evidence", []):
                    s_id = ev.get("sentence_id")
                    if s_id and s_id not in evidence_sentences:
                        sent = self.db.query(Sentence).filter(Sentence.id == s_id).first()
                        if sent and sent.document:
                            text_slice = sent.document.clean_text[sent.start:sent.end] if sent.document.clean_text else ev["verbatim_quote"]
                            evidence_sentences[s_id] = {
                                "id": s_id,
                                "document_id": sent.document_id,
                                "start": sent.start,
                                "end": sent.end,
                                "text": text_slice,
                                "score": float(edge_score),
                                "source": "graph",
                            }

                if hop + 1 < max_hops:
                    queue.append((neighbor, hop + 1, edge_score))

        sorted_edges = sorted(traversed_edges.values(), key=lambda x: x["score"], reverse=True)
        sorted_evidence = sorted(evidence_sentences.values(), key=lambda x: x["score"], reverse=True)
        return sorted_edges, sorted_evidence


def reciprocal_rank_fusion(
    vector_sentences: List[Dict[str, Any]],
    graph_sentences: List[Dict[str, Any]],
    k: int = 60,
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """Combine vector search hits and graph traversal evidence using Reciprocal Rank Fusion."""
    rrf_scores: Dict[int, float] = {}
    sentence_map: Dict[int, Dict[str, Any]] = {}

    for rank, s in enumerate(vector_sentences):
        sid = s["id"]
        sentence_map[sid] = s
        rrf_scores[sid] = rrf_scores.get(sid, 0.0) + (1.0 / (k + rank + 1))

    for rank, s in enumerate(graph_sentences):
        sid = s["id"]
        if sid not in sentence_map:
            sentence_map[sid] = s
        rrf_scores[sid] = rrf_scores.get(sid, 0.0) + (1.0 / (k + rank + 1))

    sorted_sids = sorted(rrf_scores.keys(), key=lambda sid: rrf_scores[sid], reverse=True)

    fused_results = []
    for sid in sorted_sids[:top_n]:
        item = dict(sentence_map[sid])
        item["rrf_score"] = float(rrf_scores[sid])
        fused_results.append(item)

    return fused_results
