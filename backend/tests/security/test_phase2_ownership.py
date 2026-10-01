from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.main import app
from app.models.entities import Conversation, Message, MessageRole, User
from tests.conftest import create_seed_document, delete_seed_user

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_user_cannot_access_another_users_phase2_resources(
    db_session: AsyncSession,
) -> None:
    owner_id, document_id = await create_seed_document(
        db_session,
        email=f"owner-{uuid4()}@example.com",
        filename="private.txt",
        content="Private owner content.",
    )
    other_user = User(email=f"other-{uuid4()}@example.com")
    db_session.add(other_user)
    await db_session.flush()
    conversation = Conversation(
        user_id=owner_id,
        title="Private conversation",
        document_ids=[document_id],
    )
    db_session.add(conversation)
    await db_session.flush()
    message = Message(
        conversation_id=conversation.id,
        user_id=owner_id,
        role=MessageRole.ASSISTANT,
        content="Private answer",
        grounded=False,
        sources=[],
    )
    db_session.add(message)
    await db_session.commit()

    async def current_user() -> User:
        return other_user

    async def database_session():
        yield db_session

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_db_session] = database_session
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            assert (await client.get("/api/documents")).json()["items"] == []
            assert (await client.get("/api/conversations")).json()["items"] == []
            assert (
                await client.get(f"/api/documents/{document_id}")
            ).status_code == 404
            assert (
                await client.get(f"/api/documents/{document_id}/file")
            ).status_code == 404
            assert (
                await client.delete(f"/api/documents/{document_id}")
            ).status_code == 404
            assert (
                await client.post(
                    "/api/chat",
                    json={"document_ids": [str(document_id)], "question": "Private?"},
                )
            ).status_code == 404
            assert (
                await client.get(f"/api/conversations/{conversation.id}/messages")
            ).status_code == 404
            assert (
                await client.delete(f"/api/conversations/{conversation.id}")
            ).status_code == 404
            assert (
                await client.post(
                    f"/api/messages/{message.id}/feedback", json={"value": 1}
                )
            ).status_code == 404
    finally:
        app.dependency_overrides.clear()
        await delete_seed_user(db_session, owner_id)
        await db_session.delete(other_user)
        await db_session.commit()
