from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session
from app.models.entities import User

DEV_USER_EMAIL = "dev@example.com"


async def get_current_user(
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Return the fixed Phase 2 user and create it on first use."""
    user = (
        await session.execute(select(User).where(User.email == DEV_USER_EMAIL))
    ).scalar_one_or_none()
    if user is None:
        user = User(email=DEV_USER_EMAIL)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def get_user_id(user: User = Depends(get_current_user)) -> UUID:
    return user.id


__all__ = ["DEV_USER_EMAIL", "get_current_user", "get_db_session", "get_user_id"]
