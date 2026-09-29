"""Create the initial document Q&A schema."""

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            external_id TEXT UNIQUE,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL CHECK (file_type IN ('pdf','docx','txt','md')),
            file_size BIGINT NOT NULL,
            content_hash TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            page_count INTEGER,
            status TEXT NOT NULL DEFAULT 'uploaded'
                CHECK (status IN ('uploaded','processing','ready','failed')),
            error_message TEXT,
            embedding_model TEXT,
            chunk_count INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (user_id, content_hash)
        )
        """
    )
    op.execute("CREATE INDEX idx_documents_user ON documents(user_id)")
    op.execute("CREATE INDEX idx_documents_user_status ON documents(user_id, status)")
    op.execute(
        """
        CREATE TABLE document_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            user_id UUID NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            page_start INTEGER,
            page_end INTEGER,
            section_title TEXT,
            token_count INTEGER,
            embedding vector(384) NOT NULL,
            tsv tsvector GENERATED ALWAYS AS
                (to_tsvector('english', content)) STORED,
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (document_id, chunk_index)
        )
        """
    )
    op.execute("CREATE INDEX idx_chunks_document ON document_chunks(document_id)")
    op.execute("CREATE INDEX idx_chunks_user ON document_chunks(user_id)")
    op.execute(
        """
        CREATE INDEX idx_chunks_hnsw ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )
    op.execute("CREATE INDEX idx_chunks_tsv ON document_chunks USING gin (tsv)")
    op.execute(
        """
        CREATE TABLE conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT,
            document_ids UUID[] NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_conversations_user ON conversations(user_id, updated_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id)
                ON DELETE CASCADE,
            user_id UUID NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user','assistant')),
            content TEXT NOT NULL,
            grounded BOOLEAN,
            sources JSONB,
            debug JSONB,
            feedback SMALLINT NOT NULL DEFAULT 0 CHECK (feedback IN (-1,0,1)),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_messages_conversation "
        "ON messages(conversation_id, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS conversations")
    op.execute("DROP TABLE IF EXISTS document_chunks")
    op.execute("DROP TABLE IF EXISTS documents")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
