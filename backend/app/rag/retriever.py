from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Document, DocumentChunk


@dataclass(frozen=True, slots=True)
class Candidate:
    chunk_id: UUID
    document_id: UUID
    document_name: str
    content: str
    page_start: int | None
    page_end: int | None
    cosine_score: float


class Retriever:
    async def search(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        document_ids: Sequence[UUID],
        query_embedding: Sequence[float],
        top_n: int = 20,
        min_cosine: float = 0.0,
    ) -> list[Candidate]:
        distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        statement = (
            select(
                DocumentChunk, Document.filename, (1 - distance).label("cosine_score")
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.user_id == user_id,
                DocumentChunk.document_id.in_(document_ids),
                (1 - distance) >= min_cosine,
            )
            .order_by(distance)
            .limit(top_n)
        )
        result = await session.execute(statement)
        return [
            Candidate(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_name=filename,
                content=chunk.content,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                cosine_score=float(cosine_score),
            )
            for chunk, filename, cosine_score in result.all()
        ]
