"""Test taxonomy, annotations CRUD, relations CRUD, and graph view endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.main import create_app
from backend.app.db import get_db, init_db
from backend.app.models import Document


@pytest.fixture
def test_setup(tmp_path, monkeypatch):
    """Provide TestClient with temporary DB, seeded taxonomy, and a sample document."""
    db_file = tmp_path / "test_crud.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("DB_PATH", str(db_file))

    engine = create_engine(f"sqlite:///{db_file}")
    init_db(engine_override=engine)
    TestingSession = sessionmaker(bind=engine)

    # Insert a document with known clean_text
    sample_text = "Can machines think? This should begin with definitions. Digital computers are universal."
    with TestingSession() as session:
        doc = Document(
            filename="turing.pdf",
            file_hash="testhash12345",
            status="ready",
            clean_text=sample_text,
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, doc_id, sample_text


def test_get_taxonomy(test_setup) -> None:
    """Verify taxonomy endpoint returns seeded labels and relation types."""
    client, _, _ = test_setup
    res = client.get("/taxonomy")
    assert res.status_code == 200
    data = res.json()
    assert "Claim" in data["labels"]
    assert "Evidence" in data["labels"]
    assert "supports" in data["relation_types"]
    assert "refutes" in data["relation_types"]


def test_create_and_get_annotation(test_setup) -> None:
    """Verify successful annotation creation and list retrieval."""
    client, doc_id, text = test_setup
    quote = "Can machines think?"
    start = text.index(quote)
    end = start + len(quote)

    res = client.post(
        f"/documents/{doc_id}/annotations",
        json={
            "start": start,
            "end": end,
            "quote": quote,
            "label": "Problem",
            "note": "Turing's primary question",
            "x": 100.0,
            "y": 150.0,
        },
    )
    assert res.status_code == 201
    ann = res.json()
    assert ann["id"] > 0
    assert ann["quote"] == quote
    assert ann["label"] == "Problem"
    assert ann["version"] == 1

    list_res = client.get(f"/documents/{doc_id}/annotations")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1


def test_annotation_bad_offsets_and_mismatched_quote(test_setup) -> None:
    """Verify validation errors for inverted offsets, out of bounds, and quote mismatch."""
    client, doc_id, text = test_setup

    # 1. Inverted offsets (start >= end)
    res = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": 10, "end": 5, "quote": "test", "label": "Claim"},
    )
    assert res.status_code == 422

    # 2. Out of bounds offset
    res = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": 0, "end": 9999, "quote": "too long", "label": "Claim"},
    )
    assert res.status_code == 422

    # 3. Mismatched quote
    res = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": 0, "end": 18, "quote": "Wrong quote text!!", "label": "Claim"},
    )
    assert res.status_code == 422
    assert "Quote mismatch" in res.json()["detail"]

    # 4. Unknown label
    quote = "Can machines think?"
    res = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": 0, "end": len(quote), "quote": quote, "label": "NonExistentLabel"},
    )
    assert res.status_code == 422
    assert "not in the taxonomy" in res.json()["detail"]


def test_annotation_resilient_offset_fallback(test_setup) -> None:
    """Verify that when start/end offsets are offset or zero, the backend finds the quote in clean_text."""
    client, doc_id, text = test_setup
    quote = "Digital computers are universal."
    # Pass offsets at 0..len(quote) which is wrong (actual quote is at index 55)
    res = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": 0, "end": len(quote), "quote": quote, "label": "Claim"},
    )
    assert res.status_code == 201
    ann = res.json()
    assert ann["quote"] == quote
    assert ann["start"] == text.index(quote)
    assert ann["end"] == text.index(quote) + len(quote)


def test_annotation_whitespace_normalization(test_setup) -> None:
    """Verify quote matching with newlines/irregular whitespace matches cleanly."""
    client, doc_id, text = test_setup
    quote_with_newline = "Digital\ncomputers  are   universal."
    res = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": 0, "end": len(quote_with_newline), "quote": quote_with_newline, "label": "Claim"},
    )
    assert res.status_code == 201
    ann = res.json()
    assert ann["quote"] == "Digital computers are universal."


def test_annotation_patch_stale_edit_and_delete(test_setup) -> None:
    """Verify annotation update with versioning, 409 conflict on stale version, and delete."""
    client, doc_id, text = test_setup
    quote = "Can machines think?"
    ann = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": 0, "end": len(quote), "quote": quote, "label": "Problem"},
    ).json()

    # Valid patch with version 1
    patch_res = client.patch(
        f"/annotations/{ann['id']}",
        json={"note": "Updated note", "version": 1},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["note"] == "Updated note"
    assert patch_res.json()["version"] == 2

    # Stale patch using old version 1 must return 409
    stale_res = client.patch(
        f"/annotations/{ann['id']}",
        json={"note": "Stale update", "version": 1},
    )
    assert stale_res.status_code == 409

    # Delete annotation
    del_res = client.delete(f"/annotations/{ann['id']}")
    assert del_res.status_code == 204
    assert client.get(f"/documents/{doc_id}/annotations").json() == []


def test_relations_crud_and_validation(test_setup) -> None:
    """Verify relations creation, taxonomy check, self-link rejection, stale edit, and graph view."""
    client, doc_id, text = test_setup
    q1 = "Can machines think?"
    q2 = "Digital computers are universal."
    s1, e1 = text.index(q1), text.index(q1) + len(q1)
    s2, e2 = text.index(q2), text.index(q2) + len(q2)

    ann1 = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": s1, "end": e1, "quote": q1, "label": "Problem"},
    ).json()
    ann2 = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": s2, "end": e2, "quote": q2, "label": "Solution"},
    ).json()

    # 1. Self-link rejection
    self_res = client.post(
        f"/documents/{doc_id}/relations",
        json={"source_id": ann1["id"], "target_id": ann1["id"], "type": "supports"},
    )
    assert self_res.status_code == 422
    assert "self-link forbidden" in self_res.json()["detail"]

    # 2. Invalid relation type
    invalid_type = client.post(
        f"/documents/{doc_id}/relations",
        json={"source_id": ann1["id"], "target_id": ann2["id"], "type": "magic_link"},
    )
    assert invalid_type.status_code == 422
    assert "not in the taxonomy" in invalid_type.json()["detail"]

    # 3. Successful relation creation
    rel = client.post(
        f"/documents/{doc_id}/relations",
        json={
            "source_id": ann1["id"],
            "target_id": ann2["id"],
            "type": "relates_to",
            "reason": "Direct relationship between problem and computer solution",
        },
    ).json()
    assert rel["id"] > 0
    assert rel["type"] == "relates_to"
    assert rel["version"] == 1

    # 4. Graph endpoint
    graph_res = client.get(f"/documents/{doc_id}/graph")
    assert graph_res.status_code == 200
    graph = graph_res.json()
    assert len(graph["annotations"]) == 2
    assert len(graph["relations"]) == 1

    # 5. Stale patch on relation
    stale_rel = client.patch(f"/relations/{rel['id']}", json={"version": 99, "type": "supports"})
    assert stale_rel.status_code == 409

    # 6. Cascade delete: deleting ann1 must delete rel
    client.delete(f"/annotations/{ann1['id']}")
    remaining_rels = client.get(f"/documents/{doc_id}/relations").json()
    assert len(remaining_rels) == 0


def test_graph_transitive_implied_relations(test_setup) -> None:
    """Verify Phase D: transitive closure generates implied relations for causes/precedes."""
    client, doc_id, text = test_setup

    q1 = "Can machines think?"
    q2 = "This should begin with definitions."
    q3 = "Digital computers are universal."

    a1 = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": text.index(q1), "end": text.index(q1) + len(q1), "quote": q1, "label": "Problem"},
    ).json()
    a2 = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": text.index(q2), "end": text.index(q2) + len(q2), "quote": q2, "label": "Method"},
    ).json()
    a3 = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": text.index(q3), "end": text.index(q3) + len(q3), "quote": q3, "label": "Solution"},
    ).json()

    # a1 -> a2 (causes), a2 -> a3 (causes)
    client.post(
        f"/documents/{doc_id}/relations",
        json={"source_id": a1["id"], "target_id": a2["id"], "type": "causes", "status": "confirmed"},
    )
    client.post(
        f"/documents/{doc_id}/relations",
        json={"source_id": a2["id"], "target_id": a3["id"], "type": "causes", "status": "confirmed"},
    )

    graph = client.get(f"/documents/{doc_id}/graph").json()
    implied = [r for r in graph["relations"] if r["status"] == "implied"]
    assert len(implied) == 1
    assert implied[0]["source_id"] == a1["id"]
    assert implied[0]["target_id"] == a3["id"]
    assert implied[0]["type"] == "causes"


def test_get_document_paths(test_setup) -> None:
    """Verify Phase C: BFS traversal finds multi-hop reasoning paths."""
    client, doc_id, text = test_setup

    q1 = "Can machines think?"
    q2 = "This should begin with definitions."
    q3 = "Digital computers are universal."

    a1 = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": text.index(q1), "end": text.index(q1) + len(q1), "quote": q1, "label": "Problem"},
    ).json()
    a2 = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": text.index(q2), "end": text.index(q2) + len(q2), "quote": q2, "label": "Method"},
    ).json()
    a3 = client.post(
        f"/documents/{doc_id}/annotations",
        json={"start": text.index(q3), "end": text.index(q3) + len(q3), "quote": q3, "label": "Solution"},
    ).json()

    client.post(
        f"/documents/{doc_id}/relations",
        json={"source_id": a1["id"], "target_id": a2["id"], "type": "causes"},
    )
    client.post(
        f"/documents/{doc_id}/relations",
        json={"source_id": a2["id"], "target_id": a3["id"], "type": "solves"},
    )

    # Path from a1 to a3
    res = client.get(f"/documents/{doc_id}/paths?from={a1['id']}&to={a3['id']}")
    assert res.status_code == 200
    data = res.json()
    assert len(data["paths"]) == 1
    p = data["paths"][0]
    assert p["length"] == 2
    assert p["nodes"] == [a1["id"], a2["id"], a3["id"]]
    assert f"[{a1['id']}] --[causes]--> [{a2['id']}] --[solves]--> [{a3['id']}]" in p["trace"]

