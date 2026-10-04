"""Router for document-scoped graph-aware chat completions."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import Document
from backend.app.schemas import ChatRequest, ChatResponse
from backend.app.services.chat_context import (
    CHAT_SYSTEM_PROMPT,
    retrieve_chat_context,
    build_chat_context,
    validate_citations,
)
from backend.app.services.llm import get_llm_client, LLMNotConfiguredError
from backend.app.settings import get_settings

router = APIRouter(tags=["chat"])


@router.post("/documents/{document_id}/chat", response_model=ChatResponse)
def chat_with_document(
    document_id: int,
    payload: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Answer questions about document and its annotation graph with clickable citations."""
    settings = get_settings()

    # 1. Document existence check
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 2. LLM configuration check
    try:
        llm = get_llm_client()
    except LLMNotConfiguredError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"LLM service is not configured: {str(exc)}",
        )

    # 3. Graph-aware retrieval
    retrieval = retrieve_chat_context(db, document_id, payload.question, settings=settings)

    # 4. No-context shortcut
    if not retrieval.has_context or (not retrieval.sentences and not retrieval.annotations):
        return ChatResponse(
            answer="I couldn't find this in the document.",
            citations=[],
            used_context=False,
        )

    # 5. Build compact context with stable IDs
    formatted = build_chat_context(retrieval, max_chars=settings.chat_max_context_chars)
    if not formatted.active_ids:
        return ChatResponse(
            answer="I couldn't find this in the document.",
            citations=[],
            used_context=False,
        )

    # 6. Trim history to configured maximum turns
    max_turns = settings.chat_max_history
    trimmed_history = payload.history[-(max_turns * 2) :] if payload.history else []

    # 7. Construct messages
    system_content = f"{CHAT_SYSTEM_PROMPT}\n\n=== Document Context ===\n{formatted.context_text}"
    messages = [{"role": "system", "content": system_content}]

    for msg in trimmed_history:
        messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": payload.question})

    # 8. Call LLM
    answer = llm.complete(messages)

    # 9. Validate citations
    citations = validate_citations(answer, formatted.active_ids, formatted.items_by_id)

    return ChatResponse(
        answer=answer,
        citations=citations,
        used_context=True,
    )
