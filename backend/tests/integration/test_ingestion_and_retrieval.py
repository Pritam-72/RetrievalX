from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Document, DocumentChunk, DocumentStatus, User
from app.rag.retriever import Retriever
from app.services.ingestion_service import ingest_pdf
from tests.conftest import FailingEmbedder, FixedEmbedder, delete_seed_user

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_ingestion_commits_ready_document_and_chunks(
    db_session: AsyncSession, pdf_path: Path
) -> None:
    user_id = uuid4()
    db_session.add(User(id=user_id, email=f"ingest-{user_id}@example.com"))
    await db_session.commit()
    document = await ingest_pdf(
        db_session,
        user_id=user_id,
        path=pdf_path,
        embedder=FixedEmbedder(),
        filename="process.pdf",
    )

    try:
        chunks = list(
            (
                await db_session.execute(
                    select(DocumentChunk).where(
                        DocumentChunk.document_id == document.id
                    )
                )
            ).scalars()
        )
        assert document.status == DocumentStatus.READY
        assert document.chunk_count == len(chunks)
        assert chunks
        assert all(len(chunk.embedding) == 384 for chunk in chunks)
    finally:
        await db_session.execute(delete(Document).where(Document.id == document.id))
        await db_session.execute(delete(User).where(User.id == user_id))
        await db_session.commit()


@pytest.mark.asyncio
async def test_ingestion_failure_leaves_no_partial_chunks(
    db_session: AsyncSession, pdf_path: Path
) -> None:
    user_id = uuid4()
    db_session.add(User(id=user_id, email=f"failed-{user_id}@example.com"))
    await db_session.commit()

    with pytest.raises(RuntimeError, match="embedding failed"):
        await ingest_pdf(
            db_session,
            user_id=user_id,
            path=pdf_path,
            embedder=FailingEmbedder(),
            filename="failed.pdf",
        )

    document = (
        await db_session.execute(
            select(Document).where(
                Document.user_id == user_id,
                Document.filename == "failed.pdf",
            )
        )
    ).scalar_one()
    chunks = list(
        (
            await db_session.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == document.id)
            )
        ).scalars()
    )
    assert document.status == DocumentStatus.FAILED
    assert chunks == []

    await db_session.execute(delete(Document).where(Document.id == document.id))
    await db_session.execute(delete(User).where(User.id == user_id))
    await db_session.commit()


@pytest.mark.asyncio
async def test_retriever_returns_expected_chunk_and_enforces_user_scope(
    db_session: AsyncSession,
) -> None:
    from tests.conftest import create_seed_document

    user_id, document_id = await create_seed_document(
        db_session,
        email=f"retriever-{uuid4()}@example.com",
        filename="france.txt",
        content="The capital of France is Paris.",
    )
    try:
        retriever = Retriever()
        query = [1 / (384**0.5)] * 384
        results = await retriever.search(
            db_session,
            user_id=user_id,
            document_ids=[document_id],
            query_embedding=query,
            min_cosine=0.99,
        )
        assert len(results) == 1
        assert results[0].content == "The capital of France is Paris."

        assert (
            await retriever.search(
                db_session,
                user_id=uuid4(),
                document_ids=[document_id],
                query_embedding=query,
            )
            == []
        )
    finally:
        await delete_seed_user(db_session, user_id)
