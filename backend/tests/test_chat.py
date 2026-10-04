"""Tests for graph-aware document chat: retrieval, graph expansion, truncation, citations, and error cases."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import create_app
from backend.app.db import get_db, init_db, reset_engine
from backend.app.models import Document, Sentence, Annotation, Relation
from backend.app.services.chat_context import (
    retrieve_chat_context,
    build_chat_context,
    validate_citations,
    ChatContextResult,
)
from backend.app.services.embedder import FakeEmbedder, set_shared_embedder
from backend.app.services.llm import FakeLLMClient, set_shared_llm_client, OpenAILLMClient
from backend.app.settings import get_settings


@pytest.fixture
def chat_test_setup(tmp_path, monkeypatch):
    """Set up temporary database with document, sentences, annotations, and relations."""
    db_file = tmp_path / "test_chat.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "fake")
    monkeypatch.setenv("CHAT_TOP_K_SENTENCES", "3")
    monkeypatch.setenv("CHAT_TOP_K_ANNOTATIONS", "2")
    monkeypatch.setenv("CHAT_NEIGHBOR_HOPS", "2")
    monkeypatch.setenv("CHAT_MAX_HISTORY", "3")
    monkeypatch.setenv("CHAT_MAX_CONTEXT_CHARS", "2000")

    get_settings.cache_clear()
    reset_engine()

    engine = create_engine(f"sqlite:///{db_file}")
    init_db(engine_override=engine)
    TestingSession = sessionmaker(bind=engine)

    fake_embedder = FakeEmbedder(dim=16)
    set_shared_embedder(fake_embedder)

    clean_text = (
        "Can machines think? The imitation game is played with three people. "
        "Digital computers can simulate discrete state machines. "
        "The Turing test is a test of a machine's ability to exhibit intelligent behaviour. "
        "Lady Lovelace objected that computers have no pretensions to originate anything."
    )

    with TestingSession() as session:
        doc = Document(
            filename="turing1950.pdf",
            file_hash="hashturingchat1",
            status="ready",
            clean_text=clean_text,
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id

        # Add sentences
        sent_spans = [
            (0, 19),    # Can machines think?
            (20, 68),   # The imitation game is played with three people.
            (69, 126),  # Digital computers can simulate discrete state machines.
            (127, 210), # The Turing test is a test of a machine's ability...
            (211, 292), # Lady Lovelace objected that computers have no pretensions...
        ]
        s_objects = []
        for idx, (st, en) in enumerate(sent_spans):
            text = clean_text[st:en]
            emb = fake_embedder.embed([text])[0].tobytes()
            s_objects.append(
                Sentence(
                    document_id=doc_id,
                    idx=idx,
                    start=st,
                    end=en,
                    page=1,
                    embedding=emb,
                )
            )
        session.add_all(s_objects)
        session.commit()

        # Add annotations: a1 -> a2 -> a3 -> a4
        a1 = Annotation(
            document_id=doc_id,
            start=0,
            end=19,
            quote="Can machines think?",
            label="Problem",
            note="Core philosophical question",
            version=1,
        )
        a2 = Annotation(
            document_id=doc_id,
            start=20,
            end=68,
            quote="The imitation game is played with three people.",
            label="Method",
            note="Proposed imitation test",
            version=1,
        )
        a3 = Annotation(
            document_id=doc_id,
            start=69,
            end=126,
            quote="Digital computers can simulate discrete state machines.",
            label="Claim",
            note="Computational universality",
            version=1,
        )
        a4 = Annotation(
            document_id=doc_id,
            start=211,
            end=292,
            quote="Lady Lovelace objected that computers have no pretensions to originate anything.",
            label="Evidence",
            note="Lovelace objection",
            version=1,
        )
        session.add_all([a1, a2, a3, a4])
        session.commit()

        # Relations: a1 -(defines)-> a2 -(supports)-> a3 -(refutes)-> a4
        r1 = Relation(
            document_id=doc_id,
            source_id=a1.id,
            target_id=a2.id,
            type="defines",
            status="confirmed",
            reason="Defines the question via the imitation game",
            version=1,
        )
        r2 = Relation(
            document_id=doc_id,
            source_id=a2.id,
            target_id=a3.id,
            type="supports",
            status="confirmed",
            reason="Simulated machine plays the game",
            version=1,
        )
        r3 = Relation(
            document_id=doc_id,
            source_id=a3.id,
            target_id=a4.id,
            type="refutes",
            status="suggested",
            reason="Lovelace claims lack of originality",
            version=1,
        )
        session.add_all([r1, r2, r3])
        session.commit()

        yield {
            "db_file": db_file,
            "engine": engine,
            "TestingSession": TestingSession,
            "doc_id": doc_id,
            "ann_ids": [a1.id, a2.id, a3.id, a4.id],
            "rel_ids": [r1.id, r2.id, r3.id],
        }

    set_shared_embedder(None)
    set_shared_llm_client(None)


def test_retrieval_returns_expected_items_and_neighbors(chat_test_setup):
    """Verify retrieval finds relevant sentences, seed annotations, and expands graph neighbors."""
    TestingSession = chat_test_setup["TestingSession"]
    doc_id = chat_test_setup["doc_id"]
    fake_embedder = FakeEmbedder(dim=16)

    with TestingSession() as session:
        # Ask question directly matching a1's quote
        res = retrieve_chat_context(
            session,
            doc_id,
            question="Can machines think?",
            embedder=fake_embedder,
        )

        assert isinstance(res, ChatContextResult)
        assert len(res.sentences) > 0
        assert len(res.annotations) > 0
        # Seed annotation is a1
        retrieved_ann_ids = [a["id"] for a in res.annotations]
        assert chat_test_setup["ann_ids"][0] in retrieved_ann_ids

        # Graph neighbors expanded (a1 is connected to a2, which is connected to a3)
        assert chat_test_setup["ann_ids"][1] in retrieved_ann_ids
        assert len(res.relations) >= 1
        assert res.has_context is True


def test_neighbor_expansion_respects_hops(chat_test_setup):
    """Verify BFS traversal terminates at CHAT_NEIGHBOR_HOPS."""
    TestingSession = chat_test_setup["TestingSession"]
    doc_id = chat_test_setup["doc_id"]
    fake_embedder = FakeEmbedder(dim=16)
    ann_ids = chat_test_setup["ann_ids"]  # a1 -> a2 -> a3 -> a4

    with TestingSession() as session:
        # Test 1 hop: starting from a1 should only reach a2 (distance 1), not a3 (distance 2)
        settings_1hop = get_settings()
        settings_1hop.chat_neighbor_hops = 1
        settings_1hop.chat_top_k_annotations = 1

        res_1hop = retrieve_chat_context(
            session,
            doc_id,
            question="Can machines think? Core philosophical question",
            embedder=fake_embedder,
            settings=settings_1hop,
        )
        hop1_ann_ids = [a["id"] for a in res_1hop.annotations]
        assert ann_ids[0] in hop1_ann_ids
        assert ann_ids[1] in hop1_ann_ids
        assert ann_ids[2] not in hop1_ann_ids
        assert ann_ids[3] not in hop1_ann_ids

        # Test 2 hops: starting from a1 should reach a2 (hop 1) and a3 (hop 2), but not a4 (hop 3)
        settings_2hop = get_settings()
        settings_2hop.chat_neighbor_hops = 2
        settings_2hop.chat_top_k_annotations = 1

        res_2hop = retrieve_chat_context(
            session,
            doc_id,
            question="Can machines think? Core philosophical question",
            embedder=fake_embedder,
            settings=settings_2hop,
        )
        hop2_ann_ids = [a["id"] for a in res_2hop.annotations]
        assert ann_ids[0] in hop2_ann_ids
        assert ann_ids[1] in hop2_ann_ids
        assert ann_ids[2] in hop2_ann_ids
        assert ann_ids[3] not in hop2_ann_ids


def test_context_truncation_keeps_highest_ranked():
    """Verify context compacting drops lowest-ranked items when exceeding character budget."""
    result = ChatContextResult(
        sentences=[
            {"id": 1, "start": 0, "end": 20, "text": "High relevance sentence text.", "score": 0.95},
            {"id": 2, "start": 21, "end": 60, "text": "Medium relevance sentence text.", "score": 0.70},
            {"id": 3, "start": 61, "end": 100, "text": "Low relevance sentence text that is quite long.", "score": 0.20},
        ],
        annotations=[
            {"id": 1, "start": 0, "end": 15, "quote": "High quote", "label": "Claim", "note": "Important", "score": 0.90},
            {"id": 2, "start": 30, "end": 50, "quote": "Low quote", "label": "Method", "note": "Minor", "score": 0.25},
        ],
        relations=[],
    )

    # Budget allowing top 2 items (s1 and a1, ~126 chars) while dropping lower-ranked s2, a2, s3
    formatted = build_chat_context(result, max_chars=140)
    assert len(formatted.context_text) <= 140
    # s1 and a1 (highest ranked) must be in context
    assert "s1" in formatted.active_ids
    assert "a1" in formatted.active_ids
    # Lower-ranked items must have been dropped first
    assert "s2" not in formatted.active_ids
    assert "a2" not in formatted.active_ids
    assert "s3" not in formatted.active_ids


def test_citation_validation_drops_unknown_ids():
    """Verify citations not present in context are removed while answer remains intact."""
    active_ids = {"s1", "a2"}
    items_by_id = {
        "s1": {"type": "sentence", "id": 1, "start": 0, "end": 20},
        "a2": {"type": "annotation", "id": 2, "start": 30, "end": 50},
    }

    answer_text = (
        "Computers think [s1] and are tested via the game [a2]. "
        "Also citing fake IDs [s999] and [a88] and [r44]."
    )

    citations = validate_citations(answer_text, active_ids, items_by_id)
    assert len(citations) == 2
    assert citations[0] == {"type": "sentence", "id": 1, "start": 0, "end": 20}
    assert citations[1] == {"type": "annotation", "id": 2, "start": 30, "end": 50}


def test_no_context_shortcut_does_not_call_llm(chat_test_setup):
    """Verify questions with no relevant context return shortcut answer without calling LLM."""
    TestingSession = chat_test_setup["TestingSession"]
    doc_id = chat_test_setup["doc_id"]

    # Configure FakeLLMClient to fail if called
    failing_llm = FakeLLMClient(fail=True)
    set_shared_llm_client(failing_llm)

    app = create_app()
    app.dependency_overrides[get_db] = lambda: TestingSession()
    client = TestClient(app)

    # Use a question that has 0 relevance in min_relevance check
    # We test retrieve_chat_context returning has_context=False directly or empty doc
    with TestingSession() as session:
        empty_doc = Document(filename="empty.pdf", file_hash="hashempty1", status="ready", clean_text="")
        session.add(empty_doc)
        session.commit()
        empty_doc_id = empty_doc.id

    res = client.post(
        f"/documents/{empty_doc_id}/chat",
        json={"question": "What is the meaning of life?", "history": []},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["used_context"] is False
    assert "couldn't find" in data["answer"].lower()
    assert data["citations"] == []


def test_chat_error_status_codes(chat_test_setup, monkeypatch):
    """Verify 404 for unknown document, 422 for empty question, 503 for unconfigured LLM."""
    TestingSession = chat_test_setup["TestingSession"]
    doc_id = chat_test_setup["doc_id"]

    app = create_app()
    app.dependency_overrides[get_db] = lambda: TestingSession()
    client = TestClient(app)

    # 1. 404: Unknown document
    res_404 = client.post("/documents/99999/chat", json={"question": "Valid question?"})
    assert res_404.status_code == 404

    # 2. 422: Empty or whitespace-only question
    res_422_empty = client.post(f"/documents/{doc_id}/chat", json={"question": ""})
    assert res_422_empty.status_code == 422

    res_422_spaces = client.post(f"/documents/{doc_id}/chat", json={"question": "   \n\t  "})
    assert res_422_spaces.status_code == 422

    # 3. 503: Unconfigured LLM provider requiring API key
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()
    set_shared_llm_client(None)

    res_503 = client.post(f"/documents/{doc_id}/chat", json={"question": "Can machines think?"})
    assert res_503.status_code == 503
    assert "not configured" in res_503.json()["detail"].lower()


def test_chat_history_trimmed_to_max(chat_test_setup, monkeypatch):
    """Verify dialogue history is trimmed to CHAT_MAX_HISTORY."""
    TestingSession = chat_test_setup["TestingSession"]
    doc_id = chat_test_setup["doc_id"]

    captured_messages = []

    class CapturingFakeLLM(FakeLLMClient):
        def complete(self, messages):
            captured_messages.extend(messages)
            return super().complete(messages)

    capturing_llm = CapturingFakeLLM()
    set_shared_llm_client(capturing_llm)

    app = create_app()
    app.dependency_overrides[get_db] = lambda: TestingSession()
    client = TestClient(app)

    # Send 8 turns (16 messages) when CHAT_MAX_HISTORY is 3
    long_history = []
    for i in range(8):
        long_history.append({"role": "user", "content": f"Turn {i} question"})
        long_history.append({"role": "assistant", "content": f"Turn {i} answer"})

    res = client.post(
        f"/documents/{doc_id}/chat",
        json={"question": "Can machines think?", "history": long_history},
    )
    assert res.status_code == 200
    # Expected captured messages: 1 system + (3 turns * 2 = 6 history msgs) + 1 current question = 8 msgs
    assert len(captured_messages) == 8
    assert captured_messages[0]["role"] == "system"
    assert captured_messages[1]["content"] == "Turn 5 question"
    assert captured_messages[-1]["content"] == "Can machines think?"


def test_end_to_end_chat_with_deterministic_citations(chat_test_setup):
    """Verify end-to-end chat returns answer with validated citations to sentences and annotations."""
    TestingSession = chat_test_setup["TestingSession"]
    doc_id = chat_test_setup["doc_id"]

    fake_llm = FakeLLMClient()
    set_shared_llm_client(fake_llm)

    app = create_app()
    app.dependency_overrides[get_db] = lambda: TestingSession()
    client = TestClient(app)

    res = client.post(
        f"/documents/{doc_id}/chat",
        json={"question": "Can machines think?", "history": []},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["used_context"] is True
    assert "confirmed by" in data["answer"]
    assert len(data["citations"]) > 0

    for cit in data["citations"]:
        assert cit["type"] in ("sentence", "annotation", "relation")
        assert isinstance(cit["id"], int)
        if cit["type"] in ("sentence", "annotation"):
            assert cit["start"] is not None
            assert cit["end"] is not None
