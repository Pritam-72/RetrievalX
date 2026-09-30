from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.grounding import REFUSAL_MESSAGE
from app.rag.llm_client import StubLLMClient
from app.rag.pipeline import answer_question
from app.rag.retriever import Retriever
from app.services.embedding_service import EmbeddingService, get_embedding_service
from tests.conftest import create_seed_document, delete_seed_user

pytestmark = pytest.mark.refusal
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


def real_embedder() -> EmbeddingService:
    return get_embedding_service(EMBEDDING_MODEL)


def embedding_for(embedder: EmbeddingService, content: str) -> list[float]:
    return embedder.embed_passages([content])[0].tolist()


@pytest.mark.asyncio
async def test_refusal_a_france_capital_is_grounded(db_session: AsyncSession) -> None:
    """Proves a paraphrased fact retrieves its source with the real BGE vector."""
    embedder = real_embedder()
    content = "Paris is the capital city of France."
    user_id, document_id = await create_seed_document(
        db_session,
        email=f"refusal-a-{uuid4()}@example.com",
        filename="france.txt",
        content=content,
        embedding=embedding_for(embedder, content),
    )
    try:
        result = await answer_question(
            db_session,
            user_id=user_id,
            document_ids=[document_id],
            question="Which city serves as France's capital?",
            retriever=Retriever(),
            embedder=embedder,
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
    """Proves an unrelated question remains refused with real retrieval vectors."""
    embedder = real_embedder()
    content = "Paris is the capital city of France."
    user_id, document_id = await create_seed_document(
        db_session,
        email=f"refusal-b-{uuid4()}@example.com",
        filename="france.txt",
        content=content,
        embedding=embedding_for(embedder, content),
    )
    try:
        result = await answer_question(
            db_session,
            user_id=user_id,
            document_ids=[document_id],
            question="What is the boiling point of water at sea level?",
            retriever=Retriever(),
            embedder=embedder,
            llm=StubLLMClient('{"answerable": false, "answer": "", "citations": []}'),
        )
        assert result.answer == REFUSAL_MESSAGE
        assert result.grounded is False
        assert result.sources == []
    finally:
        await delete_seed_user(db_session, user_id)


@pytest.mark.asyncio
async def test_refusal_c_python_creator_is_grounded(db_session: AsyncSession) -> None:
    """Proves a paraphrased fact in a second corpus document is grounded."""
    embedder = real_embedder()
    content = "Guido van Rossum created the Python programming language."
    user_id, document_id = await create_seed_document(
        db_session,
        email=f"refusal-c-{uuid4()}@example.com",
        filename="python_history.txt",
        content=content,
        embedding=embedding_for(embedder, content),
    )
    try:
        result = await answer_question(
            db_session,
            user_id=user_id,
            document_ids=[document_id],
            question="Who developed the Python programming language?",
            retriever=Retriever(),
            embedder=embedder,
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
@pytest.mark.xfail(
    strict=False,
    reason=(
        "D-type near-misses are expected to pass Phase 1 retrieval; "
        "T3.1 reranking and Gate 2 must decide refusal."
    ),
)
async def test_refusal_d_out_of_scope_python_question_refuses(
    db_session: AsyncSession,
) -> None:
    """Documents the near-miss that Phase 1 retrieval cannot safely refuse."""
    embedder = real_embedder()
    content = "Guido van Rossum created the Python programming language."
    user_id, document_id = await create_seed_document(
        db_session,
        email=f"refusal-d-{uuid4()}@example.com",
        filename="python_history.txt",
        content=content,
        embedding=embedding_for(embedder, content),
    )
    try:
        candidates = await Retriever().search(
            db_session,
            user_id=user_id,
            document_ids=[document_id],
            query_embedding=embedder.embed_query(
                "In what year was Python first released?"
            ),
        )
        assert candidates
    finally:
        await delete_seed_user(db_session, user_id)
