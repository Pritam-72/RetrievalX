from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import Settings, to_asyncpg_url
from app.models.entities import Document, DocumentChunk, DocumentStatus, User


def _test_database_url() -> str:
    settings = Settings()
    test_url = settings.database_url_test.strip()
    if not test_url:
        pytest.skip(
            "DATABASE_URL_TEST is not set; database integration/refusal tests skipped."
        )
    if to_asyncpg_url(test_url) == to_asyncpg_url(settings.database_url):
        pytest.fail("DATABASE_URL_TEST must not equal DATABASE_URL")
    return test_url


@pytest.fixture(scope="session")
def database_url_test() -> str:
    return _test_database_url()


@pytest_asyncio.fixture(scope="session")
async def test_engine(database_url_test: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(
        to_asyncpg_url(database_url_test), poolclass=NullPool, pool_pre_ping=True
    )
    try:
        async with engine.connect() as connection:
            await connection.exec_driver_sql("SELECT 1")
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def pdf_path(tmp_path: Path) -> Path:
    fitz = pytest.importorskip("fitz")
    path = tmp_path / "source.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "A process is a program in execution. "
        "The scheduler selects a process and assigns it CPU time. "
        "This document also records enough text to exercise extraction and chunking "
        "without relying on an external fixture file.",
    )
    document.save(path)
    document.close()
    return path


async def create_seed_document(
    session: AsyncSession,
    *,
    email: str,
    filename: str,
    content: str,
    embedding: list[float] | None = None,
) -> tuple[UUID, UUID]:
    user_id = uuid4()
    document_id = uuid4()
    session.add(User(id=user_id, email=email))
    session.add(
        Document(
            id=document_id,
            user_id=user_id,
            filename=filename,
            file_type="txt",
            file_size=len(content),
            content_hash=str(uuid4()),
            storage_path=filename,
            status=DocumentStatus.READY,
            embedding_model="test-model",
            chunk_count=1,
        )
    )
    session.add(
        DocumentChunk(
            id=uuid4(),
            document_id=document_id,
            user_id=user_id,
            chunk_index=0,
            content=content,
            page_start=1,
            page_end=1,
            token_count=len(content.split()),
            embedding=embedding or [1 / (384**0.5)] * 384,
            chunk_metadata={},
        )
    )
    await session.commit()
    return user_id, document_id


async def delete_seed_user(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(delete(Document).where(Document.user_id == user_id))
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()


class FixedEmbedder:
    model_name = "test-model"

    def embed_passages(self, passages: list[str]) -> Any:
        import numpy as np

        return np.full((len(passages), 384), 1 / (384**0.5), dtype=np.float32)

    def embed_query(self, question: str) -> Any:
        import numpy as np

        return np.full(384, 1 / (384**0.5), dtype=np.float32)


class FailingEmbedder(FixedEmbedder):
    def embed_passages(self, passages: list[str]) -> Any:
        raise RuntimeError("embedding failed")
