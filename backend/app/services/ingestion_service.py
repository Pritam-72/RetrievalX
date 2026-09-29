import hashlib
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Document, DocumentChunk, DocumentStatus
from app.services.chunking_service import Chunk, chunk_pages
from app.services.cleaning_service import clean_pages
from app.services.embedding_service import EmbeddingService
from app.services.extraction_service import extract_pdf


async def ingest_pdf(
    session: AsyncSession,
    *,
    user_id: UUID,
    path: Path,
    embedder: EmbeddingService,
    filename: str | None = None,
) -> Document:
    document = Document(
        user_id=user_id,
        filename=filename or path.name,
        file_type="pdf",
        file_size=path.stat().st_size,
        content_hash=_content_hash(path),
        storage_path=str(path),
        status=DocumentStatus.PROCESSING,
        embedding_model=embedder.model_name,
    )
    session.add(document)
    await session.commit()

    try:
        pages = clean_pages(extract_pdf(path))
        chunks = chunk_pages(pages)
        rows = build_chunk_rows(document, chunks, embedder)
        async with session.begin():
            session.add_all(rows)
            document.status = DocumentStatus.READY
            document.chunk_count = len(rows)
        return document
    except Exception as error:
        await session.rollback()
        async with session.begin():
            document.status = DocumentStatus.FAILED
            document.error_message = str(error)
        raise


def build_chunk_rows(
    document: Document,
    chunks: list[Chunk],
    embedder: EmbeddingService,
) -> list[DocumentChunk]:
    embedded_texts = [_embedding_text(document.filename, chunk) for chunk in chunks]
    embeddings = embedder.embed_passages(embedded_texts)
    return [
        DocumentChunk(
            document_id=document.id,
            user_id=document.user_id,
            chunk_index=index,
            content=chunk.content,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            section_title=chunk.section_title,
            token_count=chunk.token_count,
            embedding=embedding.tolist(),
            chunk_metadata={},
        )
        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True))
    ]


def _embedding_text(filename: str, chunk: Chunk) -> str:
    section = chunk.section_title or ""
    return f"{filename} | {section} | Page {chunk.page_start}\n\n{chunk.content}"


def _content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
