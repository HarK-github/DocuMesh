from typing import List, Optional
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db import get_db
from backend.app.models import Document, Sentence, Annotation, Suggestion, Label, Relation
from backend.app.schemas import SuggestionResponse, SuggestHighlightsRequest
from backend.app.services.embedder import get_embedder
from backend.app.services.clean import snap_to_word_boundaries
from backend.app.services.ranker import (
    retrieve_candidates,
    compute_candidate_score,
    select_diverse_candidates_mmr,
    intervals_overlap,
)
from backend.app.services.vector_store import rebuild_vector_store_if_needed
from backend.app.settings import get_settings

router = APIRouter(tags=["Suggestions"])


def _deserialize_embedding(blob: bytes) -> np.ndarray:
    """Convert stored BLOB into 1D float32 numpy array."""
    return np.frombuffer(blob, dtype=np.float32)


def _serialize_embedding(arr: np.ndarray) -> bytes:
    """Convert numpy array into raw byte string for BLOB storage."""
    return np.asarray(arr, dtype=np.float32).tobytes()


@router.get("/documents/{document_id}/suggestions", response_model=List[SuggestionResponse])
def list_suggestions(
    document_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[SuggestionResponse]:
    """Retrieve all highlight suggestions for a document, optionally filtered by status."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    query = db.query(Suggestion).filter(Suggestion.document_id == document_id)
    if status is not None:
        query = query.filter(Suggestion.status == status)

    suggestions = query.order_by(Suggestion.score.desc()).all()

    results = []
    for sug in suggestions:
        sent = sug.sentence
        if sent and doc.clean_text:
            s_start, s_end = snap_to_word_boundaries(doc.clean_text, sent.start, sent.end)
            quote = doc.clean_text[s_start:s_end]
        else:
            s_start, s_end = (sent.start, sent.end) if sent else (0, 0)
            quote = ""
        results.append(
            SuggestionResponse(
                id=sug.id,
                document_id=sug.document_id,
                sentence_id=sug.sentence_id,
                seed_annotation_id=sug.seed_annotation_id,
                label=sug.label,
                scope=sug.scope,
                score=sug.score,
                status=sug.status,
                start=s_start,
                end=s_end,
                quote=quote,
                page=sent.page if sent else 1,
            )
        )
    return results


@router.post("/documents/{document_id}/suggest-highlights", response_model=List[SuggestionResponse])
def generate_highlight_suggestions(
    document_id: int,
    payload: Optional[SuggestHighlightsRequest] = None,
    db: Session = Depends(get_db),
) -> List[SuggestionResponse]:
    """Rank sentences and generate pending smart highlight suggestions scoped to a seed annotation."""
    settings = get_settings()
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    seed_ann = None
    if payload is not None and payload.seed_annotation_id is not None:
        seed_ann = (
            db.query(Annotation)
            .filter(Annotation.id == payload.seed_annotation_id, Annotation.document_id == document_id)
            .first()
        )
        if not seed_ann:
            raise HTTPException(
                status_code=404,
                detail="Seed annotation not found. Only confirmed annotations can be used as seeds.",
            )
    else:
        seed_ann = db.query(Annotation).filter(Annotation.document_id == document_id).first()

    # Determine target label and seed ID
    if seed_ann:
        seed_id = seed_ann.id
        scope = payload.scope if payload else "passage"
        target_label = payload.target_label if (payload and payload.target_label) else seed_ann.label
    else:
        default_label = db.query(Label).first()
        target_label = (payload.target_label if payload and payload.target_label else (default_label.name if default_label else "Claim"))
        seed_id = None
        scope = "passage"

    # Pending Cap check
    remaining_slots = settings.suggestion_count
    if seed_id is not None:
        existing_pending = (
            db.query(Suggestion)
            .filter(
                Suggestion.document_id == document_id,
                Suggestion.seed_annotation_id == seed_id,
                Suggestion.status == "pending",
            )
            .all()
        )
        if len(existing_pending) >= settings.max_pending_per_seed:
            results = []
            for sug in existing_pending:
                sent = sug.sentence
                if sent and doc.clean_text:
                    s_start, s_end = snap_to_word_boundaries(doc.clean_text, sent.start, sent.end)
                    quote = doc.clean_text[s_start:s_end]
                else:
                    s_start, s_end = (sent.start, sent.end) if sent else (0, 0)
                    quote = ""
                results.append(
                    SuggestionResponse(
                        id=sug.id,
                        document_id=sug.document_id,
                        sentence_id=sug.sentence_id,
                        seed_annotation_id=sug.seed_annotation_id,
                        label=sug.label,
                        scope=sug.scope,
                        score=sug.score,
                        status=sug.status,
                        start=s_start,
                        end=s_end,
                        quote=quote,
                        page=sent.page if sent else 1,
                        message=f"Maximum pending suggestions reached for this seed ({settings.max_pending_per_seed}). Please accept or reject existing suggestions.",
                    )
                )
            return results
        remaining_slots = max(0, settings.max_pending_per_seed - len(existing_pending))

    sentences = (
        db.query(Sentence)
        .filter(Sentence.document_id == document_id)
        .order_by(Sentence.idx)
        .all()
    )
    if not sentences:
        return []

    embedder = get_embedder()

    # Ensure sentence embeddings exist
    missing_texts = []
    missing_indices = []
    for idx, s in enumerate(sentences):
        if s.embedding is None and doc.clean_text:
            text = doc.clean_text[s.start:s.end]
            missing_texts.append(text)
            missing_indices.append(idx)

    if missing_texts:
        computed = embedder.embed(missing_texts)
        for i, emb in zip(missing_indices, computed):
            sentences[i].embedding = _serialize_embedding(emb)
        db.commit()

    # Sync sentences into vector store if empty
    rebuild_vector_store_if_needed(db)

    # 1. Positives
    if scope == "category":
        cat_anns = (
            db.query(Annotation)
            .filter(Annotation.document_id == document_id, Annotation.label == target_label)
            .all()
        )
        quotes = [a.quote for a in cat_anns] if cat_anns else ([seed_ann.quote] if seed_ann else [])
        positive_embs = list(embedder.embed(quotes)) if quotes else []
    else:
        # Scope == "passage": positives are the seed annotation only
        if seed_ann:
            positive_embs = list(embedder.embed([seed_ann.quote]))
        else:
            first_sent = sentences[0]
            positive_embs = [_deserialize_embedding(first_sent.embedding)] if first_sent.embedding else []

    if not positive_embs:
        return []

    # 2. Negatives: rejected suggestions with the same label only
    rejected_sugs = (
        db.query(Suggestion)
        .filter(
            Suggestion.document_id == document_id,
            Suggestion.status == "rejected",
            Suggestion.label == target_label,
        )
        .all()
    )
    negative_embs = [
        _deserialize_embedding(s.sentence.embedding)
        for s in rejected_sugs
        if s.sentence and s.sentence.embedding is not None
    ]

    # 3. Retrieve candidates from vector store
    q_vec = np.mean(positive_embs, axis=0)
    raw_candidates = retrieve_candidates(
        query_vector=q_vec,
        document_id=document_id,
        pool_size=settings.candidate_pool_size,
    )

    if not raw_candidates:
        # Fallback to in-database sentence embeddings
        for s in sentences:
            if s.embedding is not None:
                raw_candidates.append({
                    "id": s.id,
                    "sentence_id": s.id,
                    "document_id": document_id,
                    "start": s.start,
                    "end": s.end,
                    "page": s.page,
                    "embedding": _deserialize_embedding(s.embedding),
                })

    # 4. Filters:
    # - drop overlapping any existing annotation
    # - drop already suggested (pending or rejected) for this label
    existing_anns = db.query(Annotation).filter(Annotation.document_id == document_id).all()
    prior_sugs = (
        db.query(Suggestion)
        .filter(
            Suggestion.document_id == document_id,
            Suggestion.label == target_label,
            Suggestion.status.in_(["pending", "rejected"]),
        )
        .all()
    )
    prior_sentence_ids = {s.sentence_id for s in prior_sugs}

    valid_sentence_ids = {s.id for s in sentences}
    scored_candidates = []
    for cand in raw_candidates:
        s_id = cand.get("sentence_id", cand.get("id"))
        if s_id not in valid_sentence_ids or s_id in prior_sentence_ids:
            continue

        c_start = int(cand["start"])
        c_end = int(cand["end"])
        if any(intervals_overlap(c_start, c_end, a.start, a.end) for a in existing_anns):
            continue

        c_vec = cand.get("embedding") if cand.get("embedding") is not None else cand.get("vector")
        if c_vec is None:
            # Look up sentence embedding
            sent_obj = db.query(Sentence).filter(Sentence.id == s_id).first()
            if sent_obj and sent_obj.embedding:
                c_vec = _deserialize_embedding(sent_obj.embedding)
            else:
                continue

        score = compute_candidate_score(
            candidate_vec=c_vec,
            positive_embeddings=positive_embs,
            negative_embeddings=negative_embs,
            neg_weight=settings.neg_weight,
        )

        if score >= settings.similarity_threshold:
            scored_candidates.append({
                "sentence_id": s_id,
                "start": c_start,
                "end": c_end,
                "page": cand.get("page", 1),
                "score": round(score, 4),
                "vector": c_vec,
            })

    scored_candidates.sort(key=lambda x: x["score"], reverse=True)

    # 5. Diversity loop with MMR
    # 5. Top candidates selection
    batch_limit = min(settings.suggestion_count, remaining_slots)
    if batch_limit <= 0:
        return []

    diverse_batch = select_diverse_candidates_mmr(
        candidates=scored_candidates,
        mmr_lambda=settings.mmr_lambda,
        limit=batch_limit,
    )

    if not diverse_batch:
    top_candidates = scored_candidates[:batch_limit]
    if not top_candidates:
        return []

    new_suggestions = []
    for cand in diverse_batch:
    for cand in top_candidates:
        sug = Suggestion(
            document_id=document_id,
            sentence_id=cand["sentence_id"],
            seed_annotation_id=seed_id,
            label=target_label,
            scope=scope,
            score=cand["score"],
            status="pending",
        )
        db.add(sug)
        new_suggestions.append(sug)

    db.commit()

    results = []
    for sug in new_suggestions:
        sent = sug.sentence
        if sent and doc.clean_text:
            s_start, s_end = snap_to_word_boundaries(doc.clean_text, sent.start, sent.end)
            quote = doc.clean_text[s_start:s_end]
        else:
            s_start, s_end = (sent.start, sent.end) if sent else (0, 0)
            quote = ""
        results.append(
            SuggestionResponse(
                id=sug.id,
                document_id=sug.document_id,
                sentence_id=sug.sentence_id,
                seed_annotation_id=sug.seed_annotation_id,
                label=sug.label,
                scope=sug.scope,
                score=sug.score,
                status=sug.status,
                start=s_start,
                end=s_end,
                quote=quote,
                page=sent.page if sent else 1,
            )
        )
    return results


def infer_dynamic_relation(
    seed_label: Optional[str],
    target_label: Optional[str],
    seed_id: int,
    target_id: int,
) -> tuple[int, int, str]:
    """Dynamically determine typed relationship and direction based on annotation labels."""
    s = (seed_label or "").lower()
    t = (target_label or "").lower()

    if (s == "problem" and t == "solution") or (s == "solution" and t == "problem"):
        src = target_id if s == "problem" else seed_id
        tgt = seed_id if s == "problem" else target_id
        return src, tgt, "solves"
    if (s == "claim" and t == "evidence") or (s == "evidence" and t == "claim"):
        src = target_id if s == "claim" else seed_id
        tgt = seed_id if s == "claim" else target_id
        return src, tgt, "supports"
    if s == "definition":
        return seed_id, target_id, "defines"
    if t == "definition":
        return target_id, seed_id, "defines"
    if s == "method" and t == "result":
        return seed_id, target_id, "causes"
    if s == "result" and t == "method":
        return target_id, seed_id, "causes"
    return seed_id, target_id, "similar_to"


@router.post("/suggestions/{suggestion_id}/accept", response_model=SuggestionResponse)
def accept_suggestion(suggestion_id: int, db: Session = Depends(get_db)) -> SuggestionResponse:
    """Accept a suggestion: create annotation and confirmed dynamic relation in one transaction (idempotent)."""
    sug = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
    if not sug:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    sent = sug.sentence
    doc = sug.document

    if sent and doc.clean_text:
        s_start, s_end = snap_to_word_boundaries(doc.clean_text, sent.start, sent.end)
        quote = doc.clean_text[s_start:s_end]
    else:
        s_start, s_end = (sent.start, sent.end) if sent else (0, 0)
        quote = ""

    if sug.status != "accepted":
        label = sug.label or "Claim"

        ann = (
            db.query(Annotation)
            .filter(
                Annotation.document_id == doc.id,
                Annotation.start == s_start,
                Annotation.end == s_end,
                Annotation.label == label,
            )
            .first()
        )
        if not ann:
            ann = Annotation(
                document_id=doc.id,
                start=s_start,
                end=s_end,
                quote=quote,
                label=label,
                note="Accepted from smart highlight suggestion",
                version=1,
            )
            db.add(ann)
            db.flush()

        if sug.seed_annotation_id and sug.seed_annotation_id != ann.id:
            seed_ann = (
                sug.seed_annotation
                or db.query(Annotation).filter(Annotation.id == sug.seed_annotation_id).first()
            )
            seed_label = seed_ann.label if seed_ann else None
            src_id, tgt_id, dynamic_type = infer_dynamic_relation(
                seed_label, ann.label, sug.seed_annotation_id, ann.id
            )

            rel = (
                db.query(Relation)
                .filter(
                    Relation.document_id == doc.id,
                    Relation.source_id == src_id,
                    Relation.target_id == tgt_id,
                    Relation.type == dynamic_type,
                )
                .first()
            )
            if not rel:
                rel = Relation(
                    document_id=doc.id,
                    source_id=src_id,
                    target_id=tgt_id,
                    type=dynamic_type,
                    status="confirmed",
                    reason=str(round(sug.score, 4)),
                    version=1,
                )
                db.add(rel)

        sug.status = "accepted"
        db.commit()

    return SuggestionResponse(
        id=sug.id,
        document_id=sug.document_id,
        sentence_id=sug.sentence_id,
        seed_annotation_id=sug.seed_annotation_id,
        label=sug.label,
        scope=sug.scope,
        score=sug.score,
        status=sug.status,
        start=s_start,
        end=s_end,
        quote=quote,
        page=sent.page if sent else 1,
    )


@router.post("/suggestions/{suggestion_id}/reject", response_model=SuggestionResponse)
def reject_suggestion(suggestion_id: int, db: Session = Depends(get_db)) -> SuggestionResponse:
    """Reject a suggestion idempotently."""
    sug = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
    if not sug:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    if sug.status != "rejected":
        sug.status = "rejected"
        db.commit()

    sent = sug.sentence
    doc = sug.document
    if sent and doc.clean_text:
        s_start, s_end = snap_to_word_boundaries(doc.clean_text, sent.start, sent.end)
        quote = doc.clean_text[s_start:s_end]
    else:
        s_start, s_end = (sent.start, sent.end) if sent else (0, 0)
        quote = ""

    return SuggestionResponse(
        id=sug.id,
        document_id=sug.document_id,
        sentence_id=sug.sentence_id,
        seed_annotation_id=sug.seed_annotation_id,
        label=sug.label,
        scope=sug.scope,
        score=sug.score,
        status=sug.status,
        start=s_start,
        end=s_end,
        quote=quote,
        page=sent.page if sent else 1,
    )

