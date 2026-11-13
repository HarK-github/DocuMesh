"""Unit tests for chunks, grounding, and extractor services."""

import numpy as np
from backend.app.services.chunks import (
    estimate_token_count,
    mean_pool_chunk_embedding,
    create_chunks_from_sentences,
)
from backend.app.services.grounding import (
    is_quote_grounded,
    map_quote_to_offsets,
    verify_endpoint_proximity,
)
from backend.app.services.extractor import (
    ChunkExtractionResult,
    extract_chunk,
)
from backend.app.services.llm import FakeLLMClient


def test_token_estimation_and_mean_pooling():
    """Verify token counting and mean-pooling vector normalization."""
    tokens = estimate_token_count("Transformers provide state of the art results.")
    assert tokens >= 5

    v1 = np.ones(384, dtype=np.float32) / np.sqrt(384)
    v2 = np.ones(384, dtype=np.float32) / np.sqrt(384)
    pooled = mean_pool_chunk_embedding([v1, v2])
    assert pooled is not None
    assert pooled.shape == (384,)
    assert np.isclose(np.linalg.norm(pooled), 1.0, atol=1e-5)


def test_chunking_with_overlap():
    """Verify chunking generates valid chunks with overlap from sentences."""
    clean_text = "Sentence one is here. Sentence two is longer and provides more context. Sentence three concludes."
    sentences = [
        {"idx": 0, "start": 0, "end": 21, "text": "Sentence one is here."},
        {"idx": 1, "start": 22, "end": 71, "text": "Sentence two is longer and provides more context."},
        {"idx": 2, "start": 72, "end": 97, "text": "Sentence three concludes."},
    ]
    # Small target tokens so each sentence forms or splits into chunks
    chunks = create_chunks_from_sentences(
        document_id=1,
        clean_text=clean_text,
        sentences=sentences,
        target_tokens=10,
        overlap_tokens=5,
    )
    assert len(chunks) >= 2
    for c in chunks:
        assert c.document_id == 1
        assert c.start < c.end
        assert c.first_sentence_idx <= c.last_sentence_idx
        assert c.text == clean_text[c.start:c.end]


def test_grounding_exact_and_whitespace_mapping():
    """Verify exact-match quote grounding and offset mapping."""
    clean_text = (
        "FlashAttention is a fast attention algorithm. "
        "It achieves significant memory savings on GPUs."
    )
    quote = "FlashAttention  is\n a fast attention   algorithm."
    assert is_quote_grounded(quote, clean_text)

    offsets = map_quote_to_offsets(clean_text, 0, len(clean_text), quote)
    assert offsets is not None
    start, end = offsets
    assert clean_text[start:end] == "FlashAttention is a fast attention algorithm."


def test_grounding_rejects_hallucinations():
    """Verify grounding rejects quotes that do not appear in the chunk text."""
    clean_text = "The quick brown fox jumps over the lazy dog."
    hallucinated_quote = "The slow green turtle walks under the fence."
    assert not is_quote_grounded(hallucinated_quote, clean_text)
    assert map_quote_to_offsets(clean_text, 0, len(clean_text), hallucinated_quote) is None


def test_endpoint_proximity():
    """Verify proximity rules for concepts and claims."""
    sentences = [
        {"idx": 0, "start": 0, "end": 30, "text": "MethodA is introduced here."},
        {"idx": 1, "start": 31, "end": 70, "text": "It solves ProblemB with high accuracy."},
        {"idx": 2, "start": 71, "end": 100, "text": "Further experiments follow."},
    ]
    # Concept to Concept in adjacent sentences
    assert verify_endpoint_proximity("Method", "MethodA", "Problem", "ProblemB", 1, sentences)

    # Claim endpoints waive proximity check
    assert verify_endpoint_proximity("Claim", "Any claim text", "Result", "Any result text", 1, sentences)


def test_structured_extractor_with_fake_client():
    """Verify structured extractor validates schema and outputs valid mentions and relations."""
    chunk_text = (
        "FlashAttention is a fast attention algorithm.\n"
        "It solves the quadratic memory bottleneck."
    )
    fake_client = FakeLLMClient()
    result = extract_chunk(chunk_text, chunk_index=0, llm_client=fake_client)
    assert isinstance(result, ChunkExtractionResult)
    assert len(result.mentions) >= 2
    assert len(result.relations) >= 1

    # Check that mentions have required fields and quotes ground
    for m in result.mentions:
        assert m.mention_id.startswith("m")
        assert is_quote_grounded(m.evidence_quote, chunk_text)

    for r in result.relations:
        assert r.source_mention_id != r.target_mention_id
        assert is_quote_grounded(r.evidence_quote, chunk_text)


def test_chunk_storage_and_annotation_linking(db_session):
    """Verify storing chunks saves page numbers and links overlapping annotations."""
    from backend.app.models import Document, Annotation, Chunk, AnnotationChunk
    from backend.app.services.chunks import store_chunks_for_document

    import uuid
    doc = Document(
        filename="lexical_test.pdf",
        file_hash=f"hash_{uuid.uuid4().hex}",
        status="ready",
        clean_text="Sentence one is introductory. Sentence two defines the method. Sentence three concludes.",
    )
    db_session.add(doc)
    db_session.commit()

    sentences_data = [
        {"idx": 0, "start": 0, "end": 29, "page": 1, "text": "Sentence one is introductory."},
        {"idx": 1, "start": 30, "end": 62, "page": 1, "text": "Sentence two defines the method."},
        {"idx": 2, "start": 63, "end": 88, "page": 2, "text": "Sentence three concludes."},
    ]

    # Pre-existing annotation overlapping sentence 2
    ann = Annotation(
        document_id=doc.id,
        start=30,
        end=62,
        quote="Sentence two defines the method.",
        label="Definition",
    )
    db_session.add(ann)
    db_session.commit()

    chunks = store_chunks_for_document(
        session=db_session,
        document_id=doc.id,
        clean_text=doc.clean_text,
        sentences_data=sentences_data,
    )

    assert len(chunks) >= 1
    assert all(c.page in (1, 2) for c in chunks)
    assert all(c.text is not None for c in chunks)

    # Check annotation link was established
    links = db_session.query(AnnotationChunk).filter(AnnotationChunk.annotation_id == ann.id).all()
    assert len(links) >= 1

