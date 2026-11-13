"""Token-bounded contextual chunking service with sentence mean-pooling embeddings."""

import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np
from sqlalchemy.orm import Session

from backend.app.models import Chunk, Annotation, AnnotationChunk
from backend.app.services.ranker import intervals_overlap
from backend.app.settings import get_settings
from backend.app.services.embedder import get_embedder, BaseEmbedder


@dataclass
class ChunkRecord:
    """A token-bounded contextual chunk spanning one or more sentences."""

    document_id: int
    chunk_index: int
    start: int
    end: int
    first_sentence_idx: int
    last_sentence_idx: int
    token_count: int
    text: str
    page: int = 1
    embedding: Optional[Any] = None


def estimate_token_count(text: str) -> int:
    """Count or estimate BPE tokens for text using transformers or fast word fallback."""
    if not text.strip():
        return 0
    try:
        from backend.app.services.embedder import get_embedder, SentenceTransformerEmbedder
        embedder = get_embedder()
        if isinstance(embedder, SentenceTransformerEmbedder) and hasattr(embedder._model, "tokenizer"):
            tokens = embedder._model.tokenizer.encode(text, add_special_tokens=False)
            return len(tokens)
    except Exception:
        pass

    # Standard fallback: ~1.3 tokens per whitespace word
    words = re.findall(r"\S+", text)
    return max(1, int(len(words) * 1.3))


def mean_pool_chunk_embedding(
    sentence_vectors: List[np.ndarray],
) -> Optional[np.ndarray]:
    """Compute L2-normalized sentence mean-pooled embedding for a chunk.

    Resolution for SentenceTransformer 256-token truncation:
    v_chunk = sum(v_s) / ||sum(v_s)||_2
    """
    if not sentence_vectors:
        return None
    stacked = np.array(sentence_vectors, dtype=np.float32)
    v_sum = np.sum(stacked, axis=0)
    norm = float(np.linalg.norm(v_sum))
    if norm > 1e-12:
        return (v_sum / norm).astype(np.float32)
    return v_sum.astype(np.float32)


def create_chunks_from_sentences(
    document_id: int,
    clean_text: str,
    sentences: List[Dict[str, Any]],
    target_tokens: Optional[int] = None,
    overlap_tokens: Optional[int] = None,
    sentence_embeddings: Optional[List[Optional[np.ndarray]]] = None,
) -> List[ChunkRecord]:
    """Segment a list of sentences into token-bounded chunks aligned to sentence boundaries.

    Chunking algorithm:
    - Target: target_tokens (defaults to settings.chunk_target_tokens, 250)
    - Overlap: overlap_tokens (defaults to settings.chunk_overlap_tokens, 50)
    - Never splits mid-sentence.
    - Zero extra compute embedding via mean-pooling sentence embeddings.
    """
    if not sentences:
        return []

    settings = get_settings()
    eff_target = target_tokens or getattr(settings, "chunk_target_tokens", 250)
    eff_overlap = overlap_tokens or getattr(settings, "chunk_overlap_tokens", 50)

    # Precompute sentence token counts
    sentence_tokens = []
    for s in sentences:
        s_text = s.get("text")
        if s_text is None:
            s_text = clean_text[s["start"]:s["end"]]
        sentence_tokens.append(estimate_token_count(s_text))

    chunks: List[ChunkRecord] = []
    n = len(sentences)
    i = 0
    chunk_idx = 0

    while i < n:
        curr_tokens = 0
        j = i
        while j < n:
            s_tok = sentence_tokens[j]
            # Accumulate up to target_tokens (always accept at least one sentence)
            if curr_tokens > 0 and (curr_tokens + s_tok > eff_target):
                break
            curr_tokens += s_tok
            j += 1

        last = j - 1
        c_start = sentences[i]["start"]
        c_end = sentences[last]["end"]
        c_text = clean_text[c_start:c_end]
        c_page = int(sentences[i].get("page", 1))

        # Calculate mean-pooled embedding if embeddings provided
        chunk_emb = None
        if sentence_embeddings is not None and len(sentence_embeddings) >= n:
            sub_vectors = [
                sentence_embeddings[k]
                for k in range(i, j)
                if sentence_embeddings[k] is not None
            ]
            if sub_vectors:
                pooled = mean_pool_chunk_embedding(sub_vectors)
                if pooled is not None:
                    chunk_emb = pooled.tolist()

        chunks.append(
            ChunkRecord(
                document_id=document_id,
                chunk_index=chunk_idx,
                start=c_start,
                end=c_end,
                first_sentence_idx=int(sentences[i]["idx"]),
                last_sentence_idx=int(sentences[last]["idx"]),
                token_count=curr_tokens,
                text=c_text,
                page=c_page,
                embedding=chunk_emb,
            )
        )
        chunk_idx += 1

        if j >= n:
            break

        # Compute next starting sentence index with overlap
        back = last
        overlap_accum = 0
        while back > i:
            if overlap_accum + sentence_tokens[back] > eff_overlap and overlap_accum > 0:
                break
            overlap_accum += sentence_tokens[back]
            back -= 1

        next_i = max(i + 1, back + 1)
        i = next_i

    return chunks


def link_annotations_to_chunks(session: Session, document_id: int) -> int:
    """Link each document annotation to the chunk(s) containing or overlapping it."""
    # Clear existing links for document annotations
    ann_ids = [a.id for a in session.query(Annotation.id).filter(Annotation.document_id == document_id).all()]
    if ann_ids:
        session.query(AnnotationChunk).filter(AnnotationChunk.annotation_id.in_(ann_ids)).delete(synchronize_session=False)

    annotations = session.query(Annotation).filter(Annotation.document_id == document_id).all()
    chunks = session.query(Chunk).filter(Chunk.document_id == document_id).all()

    links_created = 0
    for ann in annotations:
        for chk in chunks:
            if intervals_overlap(ann.start, ann.end, chk.start, chk.end):
                link = AnnotationChunk(annotation_id=ann.id, chunk_id=chk.id)
                session.add(link)
                links_created += 1

    session.commit()
    return links_created


def store_chunks_for_document(
    session: Session,
    document_id: int,
    clean_text: str,
    sentences_data: List[Dict[str, Any]],
    embedder: Optional[BaseEmbedder] = None,
    sentence_embeddings: Optional[List[Optional[np.ndarray]]] = None,
) -> List[Chunk]:
    """Segment, embed, and store lexical chunks for a document, then link annotations."""
    # Delete old chunks for document (safe re-indexing)
    session.query(Chunk).filter(Chunk.document_id == document_id).delete()
    session.commit()

    chunk_records = create_chunks_from_sentences(
        document_id=document_id,
        clean_text=clean_text,
        sentences=sentences_data,
        sentence_embeddings=sentence_embeddings,
    )

    if not chunk_records:
        return []

    # If embeddings missing, compute them using embedder
    texts_to_embed = []
    indices_needing_emb = []
    for idx, cr in enumerate(chunk_records):
        if cr.embedding is None:
            texts_to_embed.append(cr.text)
            indices_needing_emb.append(idx)

    if texts_to_embed:
        embedder_inst = embedder or get_embedder()
        embs = embedder_inst.embed(texts_to_embed)
        for i, emb in enumerate(embs):
            chunk_records[indices_needing_emb[i]].embedding = np.asarray(emb, dtype=np.float32).tolist()

    db_chunks = []
    for cr in chunk_records:
        chk_obj = Chunk(
            document_id=document_id,
            chunk_index=cr.chunk_index,
            start=cr.start,
            end=cr.end,
            page=cr.page,
            first_sentence_idx=cr.first_sentence_idx,
            last_sentence_idx=cr.last_sentence_idx,
            token_count=cr.token_count,
            text=cr.text,
            embedding=cr.embedding,
        )
        session.add(chk_obj)
        db_chunks.append(chk_obj)

    session.commit()

    # Link annotations to chunks
    link_annotations_to_chunks(session, document_id)

    return db_chunks
