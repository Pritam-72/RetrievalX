# DATABASE.md: Schema, Indexes, Migrations & Query Patterns

PostgreSQL 16 + `pgvector`. One database holds users, documents, chunks (with embeddings), conversations and messages.

---

## 1. Extensions

```sql
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
```

The first Alembic migration must create both.

---

## 2. Entity Relationship Overview

```
users 1───* documents 1───* document_chunks
  │
  └──1───* conversations 1───* messages
                 │
                 └── document_ids UUID[]   (documents selected for the chat)
```

---

## 3. Tables

### 3.1 `users`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | `gen_random_uuid()` |
| external_id | TEXT UNIQUE | ID from the auth provider (nullable in dev) |
| email | TEXT UNIQUE NOT NULL | |
| created_at | TIMESTAMPTZ | default `now()` |

### 3.2 `documents`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users ON DELETE CASCADE | indexed |
| filename | TEXT | original name (display only; never used as a path) |
| file_type | TEXT | `pdf` \| `docx` \| `txt` \| `md` |
| file_size | BIGINT | bytes |
| content_hash | TEXT | SHA-256 hex; `UNIQUE (user_id, content_hash)` |
| storage_path | TEXT | random-UUID-based path/key |
| page_count | INTEGER | null for txt/md |
| status | TEXT | `uploaded` \| `processing` \| `ready` \| `failed` (CHECK constraint) |
| error_message | TEXT | populated when `failed` |
| embedding_model | TEXT | e.g. `BAAI/bge-small-en-v1.5`, detects model mismatch |
| chunk_count | INTEGER | set when `ready` |
| created_at / updated_at | TIMESTAMPTZ | |

### 3.3 `document_chunks`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| document_id | UUID FK → documents ON DELETE CASCADE | |
| user_id | UUID NOT NULL | **denormalized**: mandatory isolation filter |
| chunk_index | INTEGER | order within the document |
| content | TEXT | raw chunk text (shown + sent to LLM) |
| page_start / page_end | INTEGER | inclusive page range |
| section_title | TEXT | nullable |
| token_count | INTEGER | |
| embedding | vector(384) | BGE-small, L2-normalized |
| tsv | tsvector | generated: `to_tsvector('english', content)` |
| metadata | JSONB | extra info (e.g. table flag) |
| created_at | TIMESTAMPTZ | |

Constraint: `UNIQUE (document_id, chunk_index)`.

### 3.4 `conversations`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users ON DELETE CASCADE | |
| title | TEXT | first question, truncated |
| document_ids | UUID[] | documents scoped to this chat |
| created_at / updated_at | TIMESTAMPTZ | |

### 3.5 `messages`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| conversation_id | UUID FK → conversations ON DELETE CASCADE | |
| user_id | UUID NOT NULL | denormalized for isolation |
| role | TEXT | `user` \| `assistant` (CHECK) |
| content | TEXT | |
| grounded | BOOLEAN | null for user messages |
| sources | JSONB | `[{index, document_id, document, page, chunk_id, snippet}]` |
| debug | JSONB | scores, refusal reason, timings; **never returned to clients in prod** |
| feedback | SMALLINT | -1, 0, 1 |
| created_at | TIMESTAMPTZ | |

---

## 4. Full SQL (reference for the first migration)

```sql
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id TEXT UNIQUE,
    email       TEXT UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    file_type       TEXT NOT NULL CHECK (file_type IN ('pdf','docx','txt','md')),
    file_size       BIGINT NOT NULL,
    content_hash    TEXT NOT NULL,
    storage_path    TEXT NOT NULL,
    page_count      INTEGER,
    status          TEXT NOT NULL DEFAULT 'uploaded'
                    CHECK (status IN ('uploaded','processing','ready','failed')),
    error_message   TEXT,
    embedding_model TEXT,
    chunk_count     INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, content_hash)
);
CREATE INDEX idx_documents_user ON documents(user_id);
CREATE INDEX idx_documents_user_status ON documents(user_id, status);

CREATE TABLE document_chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id       UUID NOT NULL,
    chunk_index   INTEGER NOT NULL,
    content       TEXT NOT NULL,
    page_start    INTEGER,
    page_end      INTEGER,
    section_title TEXT,
    token_count   INTEGER,
    embedding     vector(384) NOT NULL,
    tsv           tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);
CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_user     ON document_chunks(user_id);
CREATE INDEX idx_chunks_hnsw     ON document_chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_chunks_tsv      ON document_chunks USING gin (tsv);

CREATE TABLE conversations (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title        TEXT,
    document_ids UUID[] NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_conversations_user ON conversations(user_id, updated_at DESC);

CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content         TEXT NOT NULL,
    grounded        BOOLEAN,
    sources         JSONB,
    debug           JSONB,
    feedback        SMALLINT NOT NULL DEFAULT 0 CHECK (feedback IN (-1,0,1)),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);
```

---

## 5. Migration Plan (Alembic)

| # | Migration | Contents |
|---|---|---|
| 0001 | `init_extensions` | `vector`, `pgcrypto` |
| 0002 | `users_documents` | users, documents + indexes |
| 0003 | `document_chunks` | chunks, HNSW, GIN(tsv) |
| 0004 | `conversations_messages` | conversations, messages |
| 0005+ | future | e.g. `feedback_reasons`, `api_keys` |

Rules:
- Every migration must have a working `downgrade()`.
- Never edit an applied migration; add a new one.
- Changing the embedding dimension = new column + full re-embed + swap (never `ALTER TYPE` in place).

---

## 6. Query Patterns

### 6.1 Vector search (mandatory scoping)
```sql
SELECT id, document_id, content, page_start, page_end, section_title,
       1 - (embedding <=> :query_embedding) AS cosine_score
FROM document_chunks
WHERE user_id = :user_id
  AND document_id = ANY(:document_ids)
ORDER BY embedding <=> :query_embedding
LIMIT :top_n;
```

### 6.2 Keyword search (hybrid)
```sql
SELECT id, document_id, content, page_start, page_end,
       ts_rank_cd(tsv, websearch_to_tsquery('english', :q)) AS kw_score
FROM document_chunks
WHERE user_id = :user_id
  AND document_id = ANY(:document_ids)
  AND tsv @@ websearch_to_tsquery('english', :q)
ORDER BY kw_score DESC
LIMIT :top_n;
```

### 6.3 Ownership checks
Every route loading a document/conversation must use a helper that includes the user filter:
```python
async def get_document_for_user(session, user_id: UUID, document_id: UUID) -> Document | None:
    stmt = select(Document).where(Document.id == document_id, Document.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()
```
Return **404** (not 403) for others' resources so existence isn't leaked.

### 6.4 Ingestion transaction
```python
async with session.begin():
    session.add_all(chunk_rows)                     # all chunks
    doc.status = "ready"; doc.chunk_count = len(chunk_rows)
# on any exception: rollback, then in a NEW transaction set status='failed' + error_message
```

---

## 7. Index & Performance Notes

- **HNSW** is preferred over IVFFlat (no training step, better recall). Tune at query time: `SET LOCAL hnsw.ef_search = 100;` for higher recall.
- With a `WHERE` filter, HNSW may return fewer than `LIMIT` rows (post-filtering). For very selective filters:
  - raise `hnsw.ef_search` (e.g. 100–200), or
  - use pgvector's iterative index scans if available in your version (`SET hnsw.iterative_scan = relaxed_order`), or
  - fall back to an exact scan when the user has few chunks (< ~50k): `SET LOCAL enable_indexscan = off`.
- Batch-insert chunks (`executemany` / COPY) in groups of 500.
- Run `VACUUM ANALYZE document_chunks` after big ingestions.
- Vector size: 384 floats × 4 B ≈ 1.5 KB/chunk; 100k chunks ≈ 150 MB plus index overhead.

---

## 8. Data Lifecycle

| Event | Effect |
|---|---|
| Delete document | Cascade removes chunks; app deletes the stored file; conversations remain, but their `document_ids` are pruned |
| Delete conversation | Cascades to messages |
| Delete user | Cascades to everything; stored files removed by a cleanup job |
| Re-ingest | Delete old chunks first (same transaction), then insert new ones |
| Stuck `processing` docs | Startup/cron job marks docs `processing` for > 15 min as `failed` |

---

## 9. Seed / Dev Data

`scripts/seed_dev.py` creates: a dev user (`dev@example.com`), and optionally ingests `tests/fixtures/*.pdf`. Used by local runs and integration tests.
