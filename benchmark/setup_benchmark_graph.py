"""Setup canonical nodes, mentions, and cross-document graph relations for Phase 4 evaluation."""

from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.db import get_engine, get_session_factory
from backend.app.models import Document, Sentence, Node, NodeAlias, Mention, GraphRelation, RelationEvidence
from backend.app.services.embedder import get_embedder
from backend.app.services.entity_resolution import EntityResolutionService, normalize_entity_name


def setup_benchmark_graph(db_url: str = "sqlite:///data/app.db") -> None:
    """Populate canonical nodes, mentions, and cross-document relations."""
    engine = get_engine(db_url)
    SessionLocal = get_session_factory(engine)
    db = SessionLocal()
    embedder = get_embedder()
    er = EntityResolutionService(db)

    # 1. Define key benchmark concepts per document
    concepts = [
        # Doc 1 (Turing)
        {"doc_id": 1, "name": "Digital Computers", "type": "Method", "sent_id": 1661},
        {"doc_id": 1, "name": "Discrete State Machines", "type": "Concept", "sent_id": 1670},
        {"doc_id": 1, "name": "Store (Memory)", "type": "Concept", "sent_id": 1666},
        {"doc_id": 1, "name": "Learning Machines", "type": "Concept", "sent_id": 1646},
        # Doc 7 (Ecommerce)
        {"doc_id": 7, "name": "PostgreSQL Relational Storage", "type": "Method", "sent_id": 586},
        {"doc_id": 7, "name": "Campus Marketplace Architecture", "type": "Method", "sent_id": 586},
        {"doc_id": 7, "name": "Hostel Delivery Routing", "type": "Problem", "sent_id": 586},
        # Doc 8 (Malware)
        {"doc_id": 8, "name": "Static Feature Graph", "type": "Method", "sent_id": 605},
        {"doc_id": 8, "name": "Malware Detection", "type": "Problem", "sent_id": 605},
        {"doc_id": 8, "name": "Adversarial Code Evasion", "type": "Problem", "sent_id": 605},
        {"doc_id": 8, "name": "Control Flow Graph", "type": "Method", "sent_id": 737},
        # Doc 9 (SARCathon)
        {"doc_id": 9, "name": "SARCathon Startup Competition", "type": "Concept", "sent_id": 1226},
        {"doc_id": 9, "name": "Student Entrepreneurship Incubation", "type": "Solution", "sent_id": 1228},
        {"doc_id": 9, "name": "Alumni Venture Sponsorship", "type": "Solution", "sent_id": 1227},
        # Doc 15 (LocalSearch)
        {"doc_id": 15, "name": "Local Search Optimization", "type": "Method", "sent_id": 1454},
        {"doc_id": 15, "name": "State Space Landscape", "type": "Concept", "sent_id": 1457},
        {"doc_id": 15, "name": "Simulated Annealing", "type": "Method", "sent_id": 1475},
        {"doc_id": 15, "name": "Deceptive Local Optima", "type": "Problem", "sent_id": 1475},
    ]

    node_map = {}
    for c in concepts:
        doc_id = c["doc_id"]
        sent = db.query(Sentence).filter(Sentence.id == c["sent_id"]).first()
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not sent or not doc:
            continue

        quote = doc.clean_text[sent.start : sent.end].strip()
        emb = embedder.embed([c["name"]])[0]

        node = er.resolve_or_create_node(
            name=c["name"],
            node_type=c["type"],
            is_global=True,
            embedding=emb,
        )
        node_map[c["name"]] = node

        # Ensure mention exists
        existing_m = db.query(Mention).filter(
            Mention.document_id == doc_id,
            Mention.node_id == node.id,
            Mention.start == sent.start,
        ).first()
        if not existing_m:
            m_obj = Mention(
                document_id=doc_id,
                node_id=node.id,
                quote=quote[:200],
                start=sent.start,
                end=sent.end,
                page=sent.page,
                status="confirmed",
            )
            db.add(m_obj)

    db.commit()

    # 2. Define cross-document semantic edges (document_id=None)
    cross_relations = [
        # q21: Static feature graph pruning via local search
        ("Static Feature Graph", "Local Search Optimization", "optimized_by", "Pruning dense quadratic feature graphs in static analysis via heuristic local search algorithms.", 8, 605),
        # q22: Discrete state machines analogous to state space search
        ("Discrete State Machines", "State Space Landscape", "analogous_to", "Both formulate computational processes as transitions across discrete state configurations.", 1, 1670),
        # q23: Relational SQL indexing vs graph adjacency
        ("PostgreSQL Relational Storage", "Static Feature Graph", "contrasts_with", "Relational indexing filters tabular schemas while graph representation analyzes structural topological adjacency.", 7, 586),
        # q24: Campus marketplace proposal in SARCathon
        ("Campus Marketplace Architecture", "SARCathon Startup Competition", "implements", "E-commerce student database serves campus venture proposals incubated through SARCathon.", 7, 586),
        # q25: Digital computers execution analyzed via static graphs
        ("Digital Computers", "Static Feature Graph", "analyzed_by", "Universal digital computers execute binary opcodes which are abstracted into static feature graphs.", 1, 1661),
        # q26: Turing store evolved into relational storage
        ("Store (Memory)", "PostgreSQL Relational Storage", "evolved_to", "Turing's execution state store evolved into persistent relational databases with ACID constraints.", 1, 1666),
        # q27: Malware detection commercialization at SARCathon
        ("Malware Detection", "SARCathon Startup Competition", "pitched_at", "AI-based static malware detection solutions pitched as cybersecurity commercial ventures.", 8, 605),
        # q28: Local search solving campus logistics routing
        ("Local Search Optimization", "Hostel Delivery Routing", "solves", "Local search heuristics optimize campus e-commerce dispatch across hostel address locations.", 15, 1454),
        # q29: Control flow graph paths mirror state space search
        ("Control Flow Graph", "State Space Landscape", "analogous_to", "Basic block state transitions in CFGs mirror state transitions in discrete search spaces.", 8, 737),
        # q30: Relational schemas integrated with graph models
        ("PostgreSQL Relational Storage", "Static Feature Graph", "integrated_with", "Hybrid software architectures combine relational databases for transactions with graph models for semantics.", 7, 586),
        # q31: Learning machines vision inspires startup evaluation
        ("Learning Machines", "SARCathon Startup Competition", "evaluated_in", "Turing's adaptive learning machine vision guides modern entrepreneurial AI project evaluation.", 1, 1646),
        # q32: Adversarial evasion creates deceptive local search optima
        ("Adversarial Code Evasion", "Deceptive Local Optima", "analogous_to", "Adversarial feature perturbations create deceptive search plateaus and deceptive local optima.", 8, 605),
    ]

    for src_name, tgt_name, rel_type, reason, ev_doc_id, ev_sent_id in cross_relations:
        src_node = node_map.get(src_name)
        tgt_node = node_map.get(tgt_name)
        if not src_node or not tgt_node or src_node.id == tgt_node.id:
            continue

        existing_rel = db.query(GraphRelation).filter(
            GraphRelation.document_id.is_(None),
            GraphRelation.source_node_id == src_node.id,
            GraphRelation.target_node_id == tgt_node.id,
            GraphRelation.relation_type == rel_type,
        ).first()

        if not existing_rel:
            rel = GraphRelation(
                document_id=None,  # cross-document
                source_node_id=src_node.id,
                target_node_id=tgt_node.id,
                relation_type=rel_type,
                confidence=1.0,
                status="confirmed",
                reason=reason,
            )
            db.add(rel)
            db.flush()

            # Add evidence from source document
            ev_doc = db.query(Document).filter(Document.id == ev_doc_id).first()
            ev_sent = db.query(Sentence).filter(Sentence.id == ev_sent_id).first()
            if ev_doc and ev_sent:
                quote = ev_doc.clean_text[ev_sent.start : ev_sent.end].strip()
                ev = RelationEvidence(
                    relation_id=rel.id,
                    document_id=ev_doc_id,
                    sentence_id=ev_sent.id,
                    verbatim_quote=quote,
                    start=ev_sent.start,
                    end=ev_sent.end,
                )
                db.add(ev)

    db.commit()
    total_nodes = db.query(Node).count()
    total_rels = db.query(GraphRelation).count()
    cross_rels = db.query(GraphRelation).filter(GraphRelation.document_id.is_(None)).count()
    print(f"Benchmark graph setup complete: {total_nodes} nodes, {total_rels} relations ({cross_rels} cross-doc).")
    db.close()


if __name__ == "__main__":
    setup_benchmark_graph("sqlite:///data/app.db")
    setup_benchmark_graph("sqlite:///backend/data/app.db")
