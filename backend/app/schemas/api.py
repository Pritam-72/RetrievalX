from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    index: int
    document_id: UUID
    document: str
    page: int | None
    page_end: int | None
    chunk_id: UUID
    snippet: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    file_type: Literal["pdf", "docx", "txt", "md"]
    file_size: int
    page_count: int | None
    status: Literal["uploaded", "processing", "ready", "failed"]
    error_message: str | None
    chunk_count: int | None
    created_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentOut]
    next_cursor: str | None = None


class UploadResponse(BaseModel):
    document_id: UUID
    filename: str
    status: Literal["uploaded", "processing", "ready", "failed"]


class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    document_ids: list[UUID] = Field(min_length=1, max_length=20)
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def trim_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("question must not be blank")
        return cleaned


class ChatResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    answer: str
    grounded: bool
    sources: list[SourceOut]
    debug: dict[str, Any] | None = None


class ConversationOut(BaseModel):
    id: UUID
    title: str | None
    document_ids: list[UUID]
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: list[ConversationOut]
    next_cursor: str | None = None


class MessageOut(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    grounded: bool | None
    sources: list[SourceOut] = Field(default_factory=list)
    feedback: int
    created_at: datetime


class MessageListResponse(BaseModel):
    items: list[MessageOut]


class FeedbackRequest(BaseModel):
    value: Literal[-1, 0, 1]


class FeedbackResponse(BaseModel):
    message_id: UUID
    feedback: Literal[-1, 0, 1]
