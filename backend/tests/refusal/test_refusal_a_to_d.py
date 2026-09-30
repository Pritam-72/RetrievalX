from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.grounding import REFUSAL_MESSAGE
from app.rag.llm_client import StubLLMClient
from app.rag.pipeline import answer_question
from app.rag.retriever import Retriever
from tests.conftest import FixedEmbedder, create_seed_document, delete_seed_user

pytestmark = pytest.mark.refusal


@pytest.mark.asyncio
async def test_refusal_a_france_capital_is_grounded(db_session: AsyncSession) -> None:
    user_id, document_id = await create_seed_document(
        db_session,
        email=f"refusal-a-{uuid4()}@example.com",
        filename="france.txt",
        content="The capital of France is Paris.",
    )
    try:
        result = await answer_question(
            db_session,
            user_id=user_id,
            document_ids=[document_id],
            question="What is the capital of France?",
            retriever=Retriever(),
            embedder=FixedEmbedder(),
            llm=StubLLMClient(
                '{"answerable": true, "answer": "Paris. [1]", "citations": [1]}'
            ),
        )
        assert result.grounded is True
        assert "Paris" in result.answer
        assert result.sources
    finally:
        await delete_seed_user(db_session, user_id)


@pytest.mark.asyncio
async def test_refusal_b_unanswerable_question_refuses(
    db_session: AsyncSession,
) -> None:
    user_id, document_id = await create_seed_document(
        db_session,
        email=f"refusal-b-{uuid4()}@example.com",
        filename="france.txt",
        content="The capital of France is Paris.",
    )
    try:
        result = await answer_question(
            db_session,
            user_id=user_id,
            document_ids=[document_id],
            question="Who is the current president of France?",
            retriever=Retriever(),
            embedder=FixedEmbedder(),
            llm=StubLLMClient('{"answerable": false, "answer": "", "citations": []}'),
        )
        assert result.answer == REFUSAL_MESSAGE
        assert result.grounded is False
        assert result.sources == []
    finally:
        await delete_seed_user(db_session, user_id)


@pytest.mark.asyncio
async def test_refusal_c_python_creator_is_grounded(db_session: AsyncSession) -> None:
    user_id, document_id = await create_seed_document(
        db_session,
        email=f"refusal-c-{uuid4()}@example.com",
        filename="python_history.txt",
        content="Python was created by Guido van Rossum.",
    )
    try:
        result = await answer_question(
            db_session,
            user_id=user_id,
            document_ids=[document_id],
            question="Who created Python?",
            retriever=Retriever(),
            embedder=FixedEmbedder(),
            llm=StubLLMClient(
                '{"answerable": true, "answer": "Guido van Rossum. [1]", '
                '"citations": [1]}'
            ),
        )
        assert result.grounded is True
        assert "Guido van Rossum" in result.answer
    finally:
        await delete_seed_user(db_session, user_id)


@pytest.mark.asyncio
async def test_refusal_d_out_of_scope_python_question_refuses(
    db_session: AsyncSession,
) -> None:
    user_id, document_id = await create_seed_document(
        db_session,
        email=f"refusal-d-{uuid4()}@example.com",
        filename="os_mini.pdf",
        content="A process is a program in execution.",
    )
    try:
        result = await answer_question(
            db_session,
            user_id=user_id,
            document_ids=[document_id],
            question="Who invented Python?",
            retriever=Retriever(),
            embedder=FixedEmbedder(),
            llm=StubLLMClient('{"answerable": false, "answer": "", "citations": []}'),
        )
        assert result.answer == REFUSAL_MESSAGE
        assert result.grounded is False
        assert result.sources == []
    finally:
        await delete_seed_user(db_session, user_id)
