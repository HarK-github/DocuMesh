import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_session_factory, get_engine
from backend.app.models import Document, Annotation, Relation, Suggestion

def run_walkthrough():
    client = TestClient(app)

    print("=== DOCUMESH SMART HIGHLIGHT & GHOST NODE WALKTHROUGH ===")

    # Reset any prior walkthrough suggestions or dynamic annotations
    with get_session_factory(get_engine())() as session:
        session.query(Suggestion).filter(Suggestion.document_id == 1).delete()
        session.query(Annotation).filter(Annotation.document_id == 1, Annotation.id > 7).delete()
        session.commit()

    # 1. Fetch document 1
    doc_res = client.get("/documents/1")
    if doc_res.status_code != 200:
        print(f"Error fetching doc 1: {doc_res.text}")
        return False
    doc_data = doc_res.json()
    print(f"[Step 1] Document 1 loaded: '{doc_data['filename']}' (status: {doc_data['status']})")

    # 2. Highlight a passage and create annotation
    # Find a clean quote from clean_text
    text_res = client.get("/documents/1/text")
    clean_text = text_res.json()["clean_text"]

    sample_quote = "The new form of the problem can be described in terms of a game"
    start = clean_text.find(sample_quote)
    if start == -1:
        start = 100
        end = 150
        quote = clean_text[start:end]
    else:
        end = start + len(sample_quote)
        quote = sample_quote

    ann_payload = {
        "start": start,
        "end": end,
        "quote": quote,
        "label": "Claim",
        "note": "Highlighted during walkthrough",
        "x": 250.0,
        "y": 180.0,
    }
    ann_res = client.post("/documents/1/annotations", json=ann_payload)
    assert ann_res.status_code in [200, 201], f"Failed to create annotation: {ann_res.text}"
    seed_ann = ann_res.json()
    seed_id = seed_ann["id"]
    print(f"[Step 2] Seed Annotation created: ID={seed_id}, label='{seed_ann['label']}', quote='{seed_ann['quote'][:45]}...'")

    # 3. 'Save + find more like this' -> trigger scoped suggestions
    sug_res = client.post(
        "/documents/1/suggest-highlights",
        json={"seed_annotation_id": seed_id, "scope": "category"},
    )
    assert sug_res.status_code == 200, f"Failed suggest-highlights: {sug_res.text}"
    sug_batch_1 = sug_res.json()
    print(f"[Step 3] Smart highlights generated: {len(sug_batch_1)} suggestions returned.")
    for s in sug_batch_1:
        print(f"   - Sug #{s['id']}: score={s['score']:.3f}, quote='{s['quote'][:50]}...'")

    assert len(sug_batch_1) >= 3, f"Expected at least 3 suggestions, got {len(sug_batch_1)}"

    # 4. Check graph endpoint for ghost nodes and ghost similar_to edges
    graph_res = client.get("/documents/1/graph")
    assert graph_res.status_code == 200
    graph_data = graph_res.json()

    ghost_nodes = [n for n in graph_data["annotations"] if n.get("status") == "suggested"]
    ghost_edges = [e for e in graph_data["relations"] if e.get("status") == "suggested" and e.get("type") == "similar_to"]

    print(f"[Step 4] Graph response verification:")
    print(f"   - Ghost nodes in graph: {len(ghost_nodes)}")
    print(f"   - Ghost similar_to edges in graph: {len(ghost_edges)}")
    assert len(ghost_nodes) > 0, "No ghost nodes found in graph"
    assert len(ghost_edges) > 0, "No ghost similar_to edges found in graph"

    # 5. Accept two and reject one
    sug1, sug2, sug3 = sug_batch_1[0], sug_batch_1[1], sug_batch_1[2]

    # Accept 1
    acc1_res = client.post(f"/suggestions/{sug1['id']}/accept")
    assert acc1_res.status_code == 200
    print(f"[Step 5a] Accepted Sug #{sug1['id']} -> Annotation ID={acc1_res.json()['id']}")

    # Accept 2
    acc2_res = client.post(f"/suggestions/{sug2['id']}/accept")
    assert acc2_res.status_code == 200
    print(f"[Step 5b] Accepted Sug #{sug2['id']} -> Annotation ID={acc2_res.json()['id']}")

    # Reject 3
    rej_res = client.post(f"/suggestions/{sug3['id']}/reject")
    assert rej_res.status_code == 200
    print(f"[Step 5c] Rejected Sug #{sug3['id']}")

    # 6. Verify graph after accept/reject:
    # Accepted should be confirmed nodes with confirmed similar_to edges. Rejected should be absent.
    graph_res_2 = client.get("/documents/1/graph")
    graph_data_2 = graph_res_2.json()

    ghost_ids = [n["id"] for n in graph_data_2["annotations"] if n.get("status") == "suggested"]
    confirmed_quotes = [n["quote"] for n in graph_data_2["annotations"] if n.get("status") == "confirmed"]

    assert sug3["id"] not in ghost_ids, "Rejected suggestion still in graph ghost nodes"
    assert sug1["quote"] in confirmed_quotes, "Accepted annotation 1 quote not in confirmed nodes"
    assert sug2["quote"] in confirmed_quotes, "Accepted annotation 2 quote not in confirmed nodes"

    confirmed_similar_edges = [
        e for e in graph_data_2["relations"]
        if e.get("type") == "similar_to" and e.get("status") == "confirmed"
    ]
    print(f"[Step 6] Graph state updated:")
    print(f"   - Confirmed similar_to relations created: {len(confirmed_similar_edges)}")
    print(f"   - Rejected suggestion #{sug3['id']} successfully removed from graph")

    # 7. Generate next batch of suggestions and verify that it changes
    sug_res_batch_2 = client.post(
        "/documents/1/suggest-highlights",
        json={"seed_annotation_id": seed_id, "scope": "category"},
    )
    assert sug_res_batch_2.status_code == 200
    sug_batch_2 = sug_res_batch_2.json()
    batch_2_sentence_ids = {s["sentence_id"] for s in sug_batch_2}

    # Verify that accepted sentences and rejected sentence are not suggested again
    assert sug1["sentence_id"] not in batch_2_sentence_ids, "Accepted sentence 1 was suggested again"
    assert sug2["sentence_id"] not in batch_2_sentence_ids, "Accepted sentence 2 was suggested again"
    assert sug3["sentence_id"] not in batch_2_sentence_ids, "Rejected sentence 3 was suggested again"

    print(f"[Step 7] Next batch generated successfully: {len(sug_batch_2)} new suggestions.")
    print("   - Verified that previously accepted and rejected passages are excluded from new suggestions.")
    print("=== WALKTHROUGH COMPLETE: ALL CRITERIA VERIFIED SUCCESSFULLY! ===")
    return True

if __name__ == "__main__":
    success = run_walkthrough()
    if not success:
        sys.exit(1)
