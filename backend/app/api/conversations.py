from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.api.errors import ApiError
from app.models.entities import Conversation, Message, MessageRole, User
from app.schemas import (
    ConversationListResponse,
    ConversationOut,
    FeedbackRequest,
    FeedbackResponse,
    MessageListResponse,
    MessageOut,
    SourceOut,
)

router = APIRouter(tags=["conversations"])


def _message_out(message: Message) -> MessageOut:
    source_values = message.sources if isinstance(message.sources, list) else []
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        grounded=message.grounded,
        sources=[SourceOut.model_validate(source) for source in source_values],
        feedback=message.feedback,
        created_at=message.created_at,
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationListResponse:
    conversations = list(
        (
            await session.execute(
                select(Conversation)
                .where(Conversation.user_id == user.id)
                .order_by(Conversation.updated_at.desc())
            )
        ).scalars()
    )
    return ConversationListResponse(
        items=[
            ConversationOut(
                id=conversation.id,
                title=conversation.title,
                document_ids=conversation.document_ids,
                updated_at=conversation.updated_at,
            )
            for conversation in conversations
        ]
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
)
async def list_messages(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> MessageListResponse:
    conversation = (
        await session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise ApiError(404, "NOT_FOUND", "Conversation not found")
    messages = list(
        (
            await session.execute(
                select(Message)
                .where(
                    Message.conversation_id == conversation_id,
                    Message.user_id == user.id,
                )
                .order_by(Message.created_at)
            )
        ).scalars()
    )
    return MessageListResponse(items=[_message_out(message) for message in messages])


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    conversation = (
        await session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise ApiError(404, "NOT_FOUND", "Conversation not found")
    await session.delete(conversation)
    await session.commit()


@router.post("/messages/{message_id}/feedback", response_model=FeedbackResponse)
async def set_feedback(
    message_id: UUID,
    request: FeedbackRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FeedbackResponse:
    message = (
        await session.execute(
            select(Message).where(
                Message.id == message_id,
                Message.user_id == user.id,
                Message.role == MessageRole.ASSISTANT,
            )
        )
    ).scalar_one_or_none()
    if message is None:
        raise ApiError(404, "NOT_FOUND", "Assistant message not found")
    message.feedback = request.value
    await session.commit()
    return FeedbackResponse(message_id=message.id, feedback=request.value)
