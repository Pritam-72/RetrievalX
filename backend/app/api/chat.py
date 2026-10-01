from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.api.errors import ApiError
from app.config import get_settings
from app.models.entities import (
    Conversation,
    Document,
    DocumentStatus,
    Message,
    MessageRole,
    User,
)
from app.rag.llm_client import create_llm_client
from app.rag.pipeline import answer_question
from app.rag.retriever import Retriever
from app.schemas import ChatRequest, ChatResponse, SourceOut
from app.services.embedding_service import get_embedding_service

router = APIRouter(tags=["chat"])


def _source_dict(source: Any) -> dict[str, Any]:
    return {
        "index": source.index,
        "document_id": str(source.document_id),
        "document": source.document,
        "page": source.page,
        "page_end": source.page_end,
        "chunk_id": str(source.chunk_id),
        "snippet": source.snippet,
    }


async def _ready_documents(
    session: AsyncSession, user_id: UUID, document_ids: list[UUID]
) -> list[Document]:
    documents = list(
        (
            await session.execute(
                select(Document).where(
                    Document.user_id == user_id, Document.id.in_(document_ids)
                )
            )
        ).scalars()
    )
    if len(documents) != len(set(document_ids)):
        raise ApiError(404, "NOT_FOUND", "One or more documents were not found")
    if any(document.status != DocumentStatus.READY for document in documents):
        raise ApiError(409, "DOCUMENT_NOT_READY", "All documents must be ready")
    return documents


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChatResponse:
    settings = get_settings()
    documents = await _ready_documents(session, user.id, request.document_ids)
    if request.conversation_id is None:
        conversation = Conversation(
            user_id=user.id,
            title=request.question[:120],
            document_ids=[document.id for document in documents],
        )
        session.add(conversation)
        await session.flush()
    else:
        conversation = (
            await session.execute(
                select(Conversation).where(
                    Conversation.id == request.conversation_id,
                    Conversation.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if conversation is None:
            raise ApiError(404, "NOT_FOUND", "Conversation not found")
        conversation.document_ids = [document.id for document in documents]

    user_message = Message(
        conversation_id=conversation.id,
        user_id=user.id,
        role=MessageRole.USER,
        content=request.question,
    )
    session.add(user_message)
    await session.flush()
    result = await answer_question(
        session,
        user_id=user.id,
        document_ids=[document.id for document in documents],
        question=request.question,
        retriever=Retriever(),
        embedder=get_embedding_service(settings.embedding_model),
        llm=create_llm_client(
            settings.llm_provider,
            settings.llm_model,
            settings.gemini_api_key,
            settings.ollama_base_url,
        ),
        min_cosine=settings.min_cosine,
    )
    sources = [_source_dict(source) for source in result.sources]
    assistant_message = Message(
        conversation_id=conversation.id,
        user_id=user.id,
        role=MessageRole.ASSISTANT,
        content=result.answer,
        grounded=result.grounded,
        sources=sources,
        debug=result.debug if settings.debug_enabled else None,
    )
    session.add(assistant_message)
    await session.commit()
    await session.refresh(assistant_message)
    debug = (
        result.debug if settings.debug_enabled and settings.app_env != "prod" else None
    )
    return ChatResponse(
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        answer=result.answer,
        grounded=result.grounded,
        sources=[SourceOut.model_validate(source) for source in sources],
        debug=debug,
    )
