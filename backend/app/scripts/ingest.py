import argparse
import asyncio
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.db.database import session_factory
from app.models.entities import User
from app.services.embedding_service import get_embedding_service
from app.services.ingestion_service import ingest_pdf


async def _run(path: Path, user: str) -> None:
    async with session_factory() as session:
        user_id = UUID(user) if _is_uuid(user) else await _get_dev_user(session, user)
        document = await ingest_pdf(
            session,
            user_id=user_id,
            path=path,
            embedder=get_embedding_service("BAAI/bge-small-en-v1.5"),
        )
        print(f"{document.id} {document.status}")


async def _get_dev_user(session, identifier: str) -> UUID:
    result = await session.execute(select(User).where(User.email == identifier))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=identifier)
        session.add(user)
        await session.commit()
    return user.id


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--user", default="dev@example.com")
    args = parser.parse_args()
    asyncio.run(_run(args.path, args.user))


if __name__ == "__main__":
    main()
