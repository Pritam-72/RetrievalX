from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import ChatRequest, DocumentOut, FeedbackRequest, SourceOut


def test_chat_request_trims_question_and_limits_documents() -> None:
    request = ChatRequest(document_ids=[uuid4()], question="  What is a process?  ")

    assert request.question == "What is a process?"


def test_chat_request_rejects_blank_question() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(document_ids=[uuid4()], question="   ")


def test_phase2_response_schemas_accept_contract_shapes() -> None:
    document_id = uuid4()
    source = SourceOut(
        index=1,
        document_id=document_id,
        document="notes.txt",
        page=1,
        page_end=1,
        chunk_id=uuid4(),
        snippet="A grounded sentence.",
    )
    document = DocumentOut(
        id=document_id,
        filename="notes.txt",
        file_type="txt",
        file_size=10,
        page_count=None,
        status="ready",
        error_message=None,
        chunk_count=1,
        created_at=datetime.now(UTC),
    )

    assert source.index == 1
    assert document.status == "ready"
    assert FeedbackRequest(value=1).value == 1
