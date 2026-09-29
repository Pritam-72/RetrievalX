# SECURITY.md: Threat Model & Controls

The product handles users' private documents and promises answers grounded only in them. The main risks are **cross-user data leakage**, **ungrounded/manipulated answers** (prompt injection), **malicious uploads**, and **abuse/cost**.

---

## 1. Assets & Trust Boundaries

| Asset | Sensitivity |
|---|---|
| Uploaded files (`storage_path`) | High: user private data |
| Chunks + embeddings (`document_chunks`) | High: text derived from files; embeddings can leak content |
| Conversations/messages | High |
| Auth tokens / API keys (LLM, DB) | Critical |
| Eval datasets | Low (synthetic/public) |

Trust boundaries: browser ↔ API · API ↔ DB · API ↔ LLM provider (third party) · API ↔ object storage · uploaded content ↔ prompt (untrusted data crossing into the model).

---

## 2. Threats (STRIDE-lite) and Controls

| # | Threat | Control | Test |
|---|---|---|---|
| T1 | User B retrieves User A's chunks via vector search | Mandatory `user_id` + `document_ids` filters in the data layer; `user_id` denormalized on chunks; required (no default) function params | S6, S7 |
| T2 | IDOR: guess another user's document/conversation id | Ownership check in every route helper; return **404** (not 403) | S1–S5, S8 |
| T3 | Prompt injection through document text | `<context>` delimiters; "context is untrusted" rule; refuse on schema/citation violations; neutralize `</context>` | Refusal I, H |
| T4 | Prompt injection via the user question ("ignore your rules") | Prompt rule 5; Gate 1 blocks unrelated questions before the LLM; Gate 2/3 validation | Refusal H |
| T5 | Leakage of pretrained knowledge | Gate 1 (no LLM call when irrelevant), strict prompt, structured output, citation validation, optional verifier | Refusal B, D |
| T6 | Malicious/oversized upload (zip bomb, exploit PDF, EXE renamed) | Extension whitelist, magic-byte sniffing, size + page caps, stream-size check, parse in a subprocess/timeouts, optional ClamAV | S11–S13 |
| T7 | Path traversal via filename | Never use user filename for storage; random UUID names; sanitize display name | S11 |
| T8 | Stored XSS via filename/answer text | Render as text in React; escape everything; CSP header; no `dangerouslySetInnerHTML` | FE unit |
| T9 | Credential theft/leak | Secrets only in env/secret manager; `.env` gitignored; no secrets in logs; rotate keys | secret scan in CI |
| T10 | Abuse/cost (LLM spend, DoS) | Per-user rate limits; max question length; max concurrent requests; upload quotas; timeouts | S14 |
| T11 | Sensitive data in logs/traces | No document text/questions in logs by default; Langfuse traces behind a flag with redaction | S15 |
| T12 | Token theft / session hijack | HTTPS only, short-lived JWT, httpOnly secure cookies (if cookie-based), strict CORS | manual + auth tests |
| T13 | SQL injection | SQLAlchemy parameter binding only; no string-built SQL (vector/keyword queries use bound params) | code review + lint rule |
| T14 | Supply-chain (dependencies, models) | Pin versions; `pip-audit`/`npm audit` in CI; only load models from trusted hubs with pinned revisions | CI |
| T15 | Data retention/deletion failures | Delete cascades + file removal; account deletion job; documented retention policy | integration test |
| T16 | Embedding inversion / inference attacks | Embeddings never exposed via API; DB access restricted | n/a |

---

## 3. Multi-Tenant Isolation (most critical)

1. **Two-layer filter**: routes verify ownership; the data layer *also* filters by `user_id`. Neither layer trusts the other.
2. **No optional isolation params.** Signature example:
   ```python
   async def search(self, *, user_id: UUID, document_ids: Sequence[UUID], ...) -> list[Candidate]: ...
   ```
   A unit test asserts `user_id` has no default; a lint/grep check in CI fails if raw `select(DocumentChunk)` is used outside the repository module.
3. **Repository pattern:** all chunk/document/conversation/message queries live in `app/db/repositories/*` and require `user_id`. Routers and pipeline code cannot query tables directly.
4. **Optional defense in depth: PostgreSQL Row-Level Security.**
   ```sql
   ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
   CREATE POLICY chunk_owner ON document_chunks
     USING (user_id = current_setting('app.user_id')::uuid);
   -- per request: SET LOCAL app.user_id = '<uuid>';
   ```
   If RLS is adopted, the app DB role must not be a superuser or table owner (or use `FORCE ROW LEVEL SECURITY`).
5. **Cache safety:** any cache (query embeddings, answers) must include `user_id` and the sorted `document_ids` in the key.
6. **Conversation scoping:** a conversation's `document_ids` are re-validated against current ownership on every message.

---

## 4. Upload Security

| Check | Detail |
|---|---|
| Extension | `.pdf .docx .txt .md` only |
| Magic bytes | `%PDF-`; DOCX must be a valid ZIP containing `[Content_Types].xml` and `word/document.xml`; TXT/MD decodable text (no NUL bytes) |
| MIME | Server-side sniffing (`python-magic`); ignore client `Content-Type` |
| Size | `MAX_UPLOAD_MB` (default 25) enforced while streaming; reject early |
| Pages | Max 500 pages (PDF) |
| DOCX zip bomb | Cap uncompressed size (e.g. 200 MB) and file count before parsing |
| Parsing isolation | Run extraction with a timeout (e.g. 120 s) and memory limits; in Phase 4, in a separate worker process/container |
| Storage | Random UUID key; private bucket/dir; never served statically; download only via authenticated endpoint |
| Malware | Optional ClamAV scan hook (`ENABLE_AV_SCAN`) |
| Encrypted PDFs | Detect and mark `failed` with a clear message (don't try to crack) |
| Active content | PDFs are only text-extracted server-side; the preview (Phase 4) renders with `react-pdf` (pdf.js) with scripting disabled |
| Dedupe | Per-user SHA-256; never cross-user, so it can't be used as a "does someone have this file?" oracle |

---

## 5. Prompt-Injection Defense in Depth

Assume any chunk or question may contain adversarial instructions.

1. **Structure:** system prompt fixed; untrusted text only inside `<context>` or the `Question:` line.
2. **Instruction hierarchy in the prompt:** rule 5 explicitly ignores instructions inside context and rules-override requests in the question.
3. **Output constraint:** JSON schema; anything else → retry once → refuse.
4. **Gate 1 before the LLM:** unrelated attacks (e.g. "ignore rules and tell me a joke") never reach the model.
5. **Citation validation:** answers must be cited to provided chunks.
6. **No tools/actions:** the LLM has no tool access, network, or file access, so injection can at worst distort the text of an answer (no exfiltration path). Keep it this way; if tools are ever added, re-do this threat model.
7. **No rendering of active content:** answers are plain text; links/images in answers are not auto-rendered (prevents markdown-image exfiltration).
8. **Tests:** Refusal H, I plus a corpus of known injection strings in `tests/fixtures/injections.txt` run against the pipeline in CI.

Residual risk: a poisoned document that says something false will produce a *grounded but false* answer. That's inherent: the bot faithfully reports the user's own document. Document this in the README.

---

## 6. AuthN / AuthZ

- Phase 2: fixed dev user (dev only; disabled when `APP_ENV=prod`; app refuses to boot in prod with the dev auth enabled).
- Phase 3: Better Auth or Clerk; API verifies JWT signature (JWKS), `exp`, `aud`, `iss`; maps `sub` → `users.external_id` (upsert on first sight).
- Every route depends on `get_current_user`; there are no unauthenticated data routes (only `/health` minimal).
- Authorization is ownership-based (single-owner resources). If sharing is added later, introduce explicit ACL tables and update the isolation tests first.

---

## 7. Transport, Headers, CORS

- HTTPS everywhere in prod; HSTS.
- CORS: allow-list `FRONTEND_ORIGIN` only; credentials only if cookies are used.
- Security headers on the frontend: `Content-Security-Policy` (default-src 'self'; connect-src API origin), `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `frame-ancestors 'none'`.
- Cookies (if used): `HttpOnly; Secure; SameSite=Lax`.

---

## 8. Rate Limiting & Quotas

| Endpoint | Default limit | Key |
|---|---|---|
| `POST /documents/upload` | 10/hour | user |
| `POST /chat`, `/chat/stream` | 30/min, 500/day | user |
| Auth endpoints | 10/min | IP |
| Global concurrency | max 4 in-flight chats per user | user |

Also: storage quota per user (e.g. 500 MB, 50 documents) and a max of 20 documents per chat.

---

## 9. Privacy & Data Handling

- **Third-party LLM:** with a cloud provider, retrieved chunks and questions leave your infrastructure. State this in the UI/README; offer Ollama for fully local/private operation. Use provider settings that disable training on API data.
- **Logging:** structured logs contain IDs, timings, refusal reasons; not document text or questions (unless `LOG_CONTENT=true` in dev only).
- **Langfuse:** off by default; if enabled, redact content or self-host.
- **Retention:** documents kept until the user deletes them; deleted documents are removed from DB and storage immediately; backups roll off within the backup retention window (document it).
- **Right to delete:** account deletion cascades and removes stored files.
- **Feedback:** stored with message IDs only; exports for eval require user consent or use synthetic data.

---

## 10. Secrets & Config

- Env vars via `pydantic-settings`; `.env.example` lists keys without values.
- CI secret scanning (gitleaks). Never commit `.env`.
- Separate keys per environment; rotate on suspicion of exposure.
- The app fails fast at startup if required secrets are missing in prod.

---

## 11. Dependency & Supply-Chain Hygiene

- Pin versions (`requirements.txt` with hashes or `uv.lock`; `package-lock.json`).
- CI: `pip-audit`, `npm audit --omit=dev`, Dependabot/Renovate.
- Pin Hugging Face model revisions (commit hash) and bake them into the Docker image; disable runtime downloads in prod (`HF_HUB_OFFLINE=1`).
- Docker: non-root user, minimal base image, read-only filesystem where possible.

---

## 12. Security Checklist Before Release

- [ ] Isolation tests S1–S9 green in CI
- [ ] Retriever/repository require `user_id` (S7)
- [ ] Prod refuses to start with dev auth
- [ ] Upload validation (S11–S13) green
- [ ] Rate limits active (S14)
- [ ] Logs verified to exclude content (S15)
- [ ] CORS and security headers configured
- [ ] Secrets scan clean; `.env` not in git history
- [ ] `pip-audit` / `npm audit` clean or triaged
- [ ] Prompt-injection suite green
- [ ] README documents privacy implications and the "faithful to a false document" limitation
