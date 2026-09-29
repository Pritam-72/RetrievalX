import argparse
import asyncio
from uuid import UUID

from sqlalchemy import select

from app.config import get_settings
from app.db.database import session_factory
from app.models.entities import Document, DocumentStatus, User
from app.rag.llm_client import create_llm_client
from app.rag.pipeline import answer_question
from app.rag.retriever import Retriever
from app.services.embedding_service import get_embedding_service


async def _run(question: str, user: str) -> None:
    settings = get_settings()
    async with session_factory() as session:
        user_id = UUID(user) if _is_uuid(user) else await _get_user_id(session, user)
        document_ids = list(
            (
                await session.execute(
                    select(Document.id).where(
                        Document.user_id == user_id,
                        Document.status == DocumentStatus.READY,
                    )
                )
            ).scalars()
        )
        result = await answer_question(
            session,
            user_id=user_id,
            document_ids=document_ids,
            question=question,
            retriever=Retriever(),
            embedder=get_embedding_service(settings.embedding_model),
            llm=create_llm_client(
                settings.llm_provider,
                settings.llm_model,
                settings.gemini_api_key,
                settings.ollama_base_url,
            ),
        )
        print(result.answer)
        for source in result.sources:
            source_text = (
                f"[{source.index}] {source.document} page {source.page}: "
                f"{source.snippet}"
            )
            print(source_text)


async def _get_user_id(session, email: str) -> UUID:
    result = await session.execute(select(User.id).where(User.email == email))
    user_id = result.scalar_one_or_none()
    if user_id is None:
        raise ValueError(f"User not found: {email}")
    return user_id


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ask a question about ingested documents."
    )
    parser.add_argument("question")
    parser.add_argument("--user", default="dev@example.com")
    args = parser.parse_args()
    asyncio.run(_run(args.question, args.user))


if __name__ == "__main__":
    main()
