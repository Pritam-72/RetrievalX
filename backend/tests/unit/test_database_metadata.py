from app.config import to_asyncpg_url
from app.db.base import Base
from app.models.entities import DocumentChunk


def test_initial_metadata_contains_all_required_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "documents",
        "document_chunks",
        "conversations",
        "messages",
    }


def test_document_chunks_require_tenant_scope_and_384_dimensions() -> None:
    table = Base.metadata.tables["document_chunks"]

    assert table.c.user_id.nullable is False
    assert table.c.document_id.nullable is False
    assert isinstance(
        DocumentChunk.__table__.c.embedding.type, type(table.c.embedding.type)
    )
    assert table.c.embedding.type.dim == 384


def test_to_asyncpg_url_uses_required_ssl_and_preserves_other_parameters() -> None:
    url = (
        "postgres://user:p%40ss@example.neon.tech/db"
        "?sslmode=require&channel_binding=require"
    )

    assert to_asyncpg_url(url) == (
        "postgresql+asyncpg://user:p%40ss@example.neon.tech/db"
        "?channel_binding=require&ssl=require"
    )


def test_to_asyncpg_url_replaces_existing_asyncpg_ssl_setting() -> None:
    url = "postgresql+asyncpg://user:pass@localhost/db?ssl=disable"

    assert to_asyncpg_url(url) == (
        "postgresql+asyncpg://user:pass@localhost/db?ssl=require"
    )
