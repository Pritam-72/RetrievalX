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
