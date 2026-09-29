# API.md: REST & SSE Specification

Base URL: `/api` · Format: JSON (UTF-8) · Auth: `Authorization: Bearer <JWT>` (Phase 2 uses a fixed dev user; Phase 3 enforces JWT).

---

## 1. Conventions

### 1.1 Error format
All errors use:
```json
{ "error": { "code": "DOCUMENT_NOT_READY", "message": "Human-readable message", "details": {} } }
```

| HTTP | code | When |
|---|---|---|
| 400 | `INVALID_FILE_TYPE` | Extension/MIME not allowed |
| 400 | `VALIDATION_ERROR` | Bad request body |
| 401 | `UNAUTHENTICATED` | Missing/invalid token |
| 404 | `NOT_FOUND` | Resource missing **or owned by someone else** |
| 409 | `DUPLICATE_DOCUMENT` | Same content hash already uploaded |
| 409 | `DOCUMENT_NOT_READY` | Chat against a doc not `ready` |
| 413 | `FILE_TOO_LARGE` | Over `MAX_UPLOAD_MB` |
| 422 | `NO_EXTRACTABLE_TEXT` | Scanned or empty document (reported on the document as `failed`) |
| 429 | `RATE_LIMITED` | Includes `Retry-After` header |
| 500 | `INTERNAL_ERROR` | Unexpected; log with `request_id` |

Every response includes header `X-Request-ID`.

### 1.2 IDs and timestamps
UUID v4 strings; ISO-8601 UTC timestamps (`2026-09-29T10:15:30Z`).

### 1.3 Pagination
List endpoints accept `?limit=` (default 50, max 100) and `?cursor=`; respond with `{ "items": [...], "next_cursor": "..."|null }`.

---

## 2. Documents

### 2.1 `POST /documents/upload`
`multipart/form-data`, field `file`.

**202 Accepted**
```json
{
  "document_id": "3f0c...",
  "filename": "operating_systems.pdf",
  "status": "processing"
}
```
**Behavior:** validates → stores → creates row (`uploaded`) → background ingestion (`processing` → `ready`/`failed`).
**Errors:** 400, 409, 413, 429.

### 2.2 `GET /documents`
```json
{
  "items": [
    {
      "id": "3f0c...",
      "filename": "operating_systems.pdf",
      "file_type": "pdf",
      "file_size": 4821930,
      "page_count": 320,
      "status": "ready",
      "error_message": null,
      "chunk_count": 812,
      "created_at": "2026-09-29T10:15:30Z"
    }
  ],
  "next_cursor": null
}
```

### 2.3 `GET /documents/{id}`
Same object as the list item. 404 if not owned.

### 2.4 `GET /documents/{id}/file`
Streams the original file (`Content-Disposition: inline`). Auth + ownership required. Never expose storage paths.

### 2.5 `DELETE /documents/{id}`
**204 No Content.** Removes chunks and the stored file; idempotent (second call → 404).

---

## 3. Chat

### 3.1 `POST /chat`
**Request**
```json
{
  "conversation_id": "uuid | null",
  "document_ids": ["uuid", "uuid"],
  "question": "What is a process?"
}
```
Rules:
- `document_ids`: 1–20 ids; all must belong to the user and be `ready` (else 404 / 409).
- `question`: 1–2000 chars, trimmed.
- If `conversation_id` is null, a new conversation is created with these `document_ids`.

**200 Response (grounded)**
```json
{
  "conversation_id": "uuid",
  "message_id": "uuid",
  "answer": "A process is a program in execution. [1]",
  "grounded": true,
  "sources": [
    {
      "index": 1,
      "document_id": "uuid",
      "document": "operating_systems.pdf",
      "page": 12,
      "page_end": 12,
      "chunk_id": "uuid",
      "snippet": "A process is a program in execution. It includes..."
    }
  ]
}
```

**200 Response (refusal)** (still 200; it's a valid outcome)
```json
{
  "conversation_id": "uuid",
  "message_id": "uuid",
  "answer": "I couldn't find the answer in the uploaded documents.",
  "grounded": false,
  "sources": []
}
```
In development (`APP_ENV=dev`) an extra `"debug": { "reason": "below_threshold", "top_score": 0.12, "timings_ms": {...} }` field is included; **never in production**.

### 3.2 `POST /chat/stream` (SSE, Phase 4)
Same request body. `Content-Type: text/event-stream`.

| Event | Data | Notes |
|---|---|---|
| `meta` | `{"conversation_id","message_id"}` | first event |
| `token` | `{"text": "..."}` | emitted only **after** all gates pass |
| `done` | `{"grounded": true, "sources": [...]}` | final |
| `refusal` | `{"answer": "...", "grounded": false}` | replaces token/done |
| `error` | `{"code","message"}` | terminal |

Heartbeat comment `: ping` every 15 s. Clients must tolerate reconnect by re-querying the message via `GET /conversations/{id}/messages`.

---

## 4. Conversations

### 4.1 `GET /conversations`
```json
{ "items": [ { "id":"uuid","title":"What is a process?","document_ids":["uuid"],"updated_at":"..." } ], "next_cursor": null }
```

### 4.2 `GET /conversations/{id}/messages`
```json
{
  "items": [
    { "id":"uuid","role":"user","content":"What is a process?","created_at":"..." },
    { "id":"uuid","role":"assistant","content":"A process is ... [1]","grounded":true,
      "sources":[...], "feedback":0, "created_at":"..." }
  ]
}
```

### 4.3 `DELETE /conversations/{id}`: 204.

---

## 5. Feedback

### `POST /messages/{id}/feedback`
```json
{ "value": 1 }      // 1 | -1 | 0 (clear)
```
**200** `{ "message_id": "uuid", "feedback": 1 }`. Only assistant messages, only own conversations.

---

## 6. Health

### `GET /health`
```json
{ "status": "ok", "db": "ok", "embedding_model": "loaded", "reranker": "loaded", "llm": "reachable" }
```
`503` if the DB is unreachable. `llm` check is cached (60 s) to avoid cost.

---

## 7. Pydantic Schemas (backend/app/schemas)

```python
class SourceOut(BaseModel):
    index: int
    document_id: UUID
    document: str
    page: int | None
    page_end: int | None
    chunk_id: UUID
    snippet: str

class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    document_ids: list[UUID] = Field(min_length=1, max_length=20)
    question: str = Field(min_length=1, max_length=2000)

class ChatResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    answer: str
    grounded: bool
    sources: list[SourceOut]
    debug: dict | None = None      # dev only

class LLMAnswer(BaseModel):        # internal: parsed LLM JSON
    answerable: bool
    answer: str = ""
    citations: list[int] = []

class DocumentOut(BaseModel):
    id: UUID
    filename: str
    file_type: Literal["pdf", "docx", "txt", "md"]
    file_size: int
    page_count: int | None
    status: Literal["uploaded", "processing", "ready", "failed"]
    error_message: str | None
    chunk_count: int | None
    created_at: datetime
```

---

## 8. Middleware & Cross-Cutting

- **Request ID:** generated per request, returned as `X-Request-ID`, attached to logs.
- **CORS:** allow only configured origins (`FRONTEND_ORIGIN`).
- **Rate limits (Phase 3):** upload 10/hour/user; chat 30/min/user (configurable). 429 with `Retry-After`.
- **Body size:** reject > `MAX_UPLOAD_MB` early (stream check), not after buffering.
- **Timeouts:** chat endpoint 60 s hard timeout; LLM call 30 s; on timeout return 504-style `INTERNAL_ERROR` (never a made-up answer).
- **Idempotency:** upload dedupe by content hash; delete idempotent.

---

## 9. OpenAPI
FastAPI auto-generates `/docs` and `/openapi.json`. Keep response models on every route so the frontend types can be generated (`openapi-typescript`) into `frontend/lib/api-types.ts`.
