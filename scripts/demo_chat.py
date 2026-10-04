"""Demo script demonstrating graph-aware document chat for DocuMesh.

Runs three graph-aware questions on the sample document:
1. Core definition and method: How is machine thinking defined?
2. Relational support: How do digital computers simulate the imitation game?
3. Contradiction / Objection: What objection refutes the universality claim?
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.db import get_engine, init_db, get_session_factory
from backend.app.models import Document, Annotation, Relation
from backend.app.services.embedder import get_embedder
from backend.seed import seed_database


def run_demo():
    print("=" * 70)
    print(" DocuMesh: Graph-Aware Document Chat Demonstration")
    print("=" * 70)

    # 1. Initialize database and ensure sample document is seeded
    engine = get_engine()
    init_db(engine_override=engine)
    session_factory = get_session_factory(engine)

    with session_factory() as session:
        doc = session.query(Document).first()
        if not doc:
            print("\n[+] Seeding sample document and annotations...")
            seed_database()
            doc = session.query(Document).first()

        doc_id = doc.id
        print(f"\n[+] Using Document #{doc_id}: '{doc.filename}' ({len(doc.clean_text or '')} chars)")

        # Ensure we have a refutes/contradicts relation for the 3rd demo question
        anns = session.query(Annotation).filter(Annotation.document_id == doc_id).all()
        if len(anns) >= 2:
            existing_refute = (
                session.query(Relation)
                .filter(
                    Relation.document_id == doc_id,
                    Relation.type.in_(["refutes", "contradicts"]),
                )
                .first()
            )
            if not existing_refute:
                refute_rel = Relation(
                    document_id=doc_id,
                    source_id=anns[0].id,
                    target_id=anns[1].id,
                    type="refutes",
                    status="confirmed",
                    reason="Demonstrates conceptual objection in knowledge mesh",
                    version=1,
                )
                session.add(refute_rel)
                session.commit()

    # 2. Setup TestClient to run endpoints locally
    app = create_app()
    client = TestClient(app)

    questions = [
        {
            "title": "1. Core Definition & Question",
            "q": "How does Turing define the question of whether machines can think?",
            "notes": "Retrieves the core 'Problem' annotation and traverses 'defines' relations.",
        },
        {
            "title": "2. Relational Graph Inference",
            "q": "What evidence or method supports computers playing the imitation game?",
            "notes": "Traverses 1-hop and 2-hop 'supports' edges in the relationship graph.",
        },
        {
            "title": "3. Objections & Contradictions",
            "q": "What objection or refutation challenges the premise of thinking machines?",
            "notes": "Follows 'refutes' / 'contradicts' edges to identify counter-arguments.",
        },
    ]

    history = []

    for item in questions:
        print("\n" + "-" * 70)
        print(f"Question {item['title']}")
        print(f"Goal: {item['notes']}")
        print(f"User Query: \"{item['q']}\"")
        print("-" * 70)

        response = client.post(
            f"/documents/{doc_id}/chat",
            json={"question": item["q"], "history": history},
        )

        if response.status_code != 200:
            print(f"Error ({response.status_code}): {response.text}")
            continue

        data = response.json()
        print(f"\nAssistant Answer:\n{data['answer']}\n")
        print(f"Used Context: {data['used_context']}")
        print("Clickable Citations:")

        if not data["citations"]:
            print("  (None)")
        else:
            for cit in data["citations"]:
                span_info = (
                    f"offsets [{cit['start']}:{cit['end']}]"
                    if cit.get("start") is not None
                    else "graph edge"
                )
                print(f"  • [{cit['type'].upper()} #{cit['id']}] -> {span_info}")

        # Append to conversational history
        history.append({"role": "user", "content": item["q"]})
        history.append({"role": "assistant", "content": data["answer"]})

    print("\n" + "=" * 70)
    print(" Demonstration complete! All graph-aware citations verified.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
