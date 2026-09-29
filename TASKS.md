# TASKS.md: Work Queue

> Claude Code: work top to bottom. Complete one task at a time, run its checks, tick the box, and **stop at the end of each phase** for review.
> Legend: `[ ]` todo · `[x]` done · `(P0)` must · `(P1)` should · `(P2)` nice-to-have

## Implementation Plan

This queue is the executable implementation plan. Work in order and keep each phase reviewable:

1. **Bootstrap (Phase 0):** establish the repository, local PostgreSQL/pgvector, FastAPI app, configuration, migrations, and baseline checks.
2. **Prove the pipeline (Phase 1 / V0):** build extraction, cleaning, chunking, embeddings, retrieval, prompting, LLM adapters, and the first refusal path for one PDF.
3. **Make it usable (Phase 2 / V1):** expose document and chat APIs, persist conversations, add the Next.js interface, citations, document selection, and the first refusal-contract tests.
4. **Harden grounding (Phase 3 / V2):** add reranking, calibrated gates, structured output validation, query rewriting, hybrid retrieval, authentication, isolation, upload security, CI, and the full A–H acceptance suite.
5. **Showcase and operate (Phase 4 / V3):** add evaluation reports, threshold calibration, observability, post-validation streaming, workers, PDF preview, E2E coverage, and deployment.

### Dependency rules

- Do not begin a later phase until the preceding phase exit checks pass and the phase review is complete.
- Keep the refusal contract and tenant isolation tests blocking from the first implementation that can answer a question.
- Any change to extraction, chunking, embedding, reranking, or thresholds requires the relevant unit tests and an evaluation comparison before updating calibrated configuration.
- Any endpoint change updates `docs/API.md`, backend contract tests, and generated frontend types together.

### Phase exit gates

| Phase | Exit gate |
|---|---|
| 0 | Clean database migration up/down, health endpoint, lint/type/test commands run |
| 1 / V0 | Known in-scope PDF questions answer with sources; no-evidence questions refuse |
| 2 / V1 | Upload-to-ready-to-chat flow works; citations render; refusal tests A–D pass |
| 3 / V2 | Tests A–H and isolation suite pass; thresholds are calibrated; CI is green |
| 4 / V3 | Eval report is published; E2E and deployment smoke test pass |

---

## Phase 0: Project Bootstrap

- [x] **T0.1 Repo scaffold (P0)**
  - Create the folder layout from `CLAUDE.md §4`, `.gitignore`, `.env.example`, `README.md` stub.
  - *Accept:* `tree` matches layout; `.env` is gitignored.
- [ ] **T0.2 Docker Postgres + pgvector (P0)**
  - `docker-compose.yml` with `pgvector/pgvector:pg16`, volume, healthcheck.
  - *Accept:* `docker compose up -d db` → `psql` can run `CREATE EXTENSION vector;`.
- [x] **T0.3 Backend skeleton (P0)**
  - FastAPI app, `config.py` (pydantic-settings), `/api/health`, ruff + mypy + pytest configured.
  - *Accept:* `uvicorn` starts; `GET /api/health` returns 200; `pytest` runs (even if empty).
- [ ] **T0.4 DB layer + Alembic (P0)**
  - Async SQLAlchemy engine/session, Alembic initialized, first migration creates all tables from `docs/DATABASE.md`.
  - *Accept:* `alembic upgrade head` on empty DB succeeds; `alembic downgrade base` succeeds.

---

## Phase 1 (V0): Proof of Concept: single PDF → answer

- [ ] **T1.1 Extraction service (P0)**: `extraction_service.py`
  - PDF via PyMuPDF returning `list[PageText(page_number, text)]`.
  - *Accept:* unit test on a fixture PDF returns correct page count and text; scanned/empty PDF raises `NoExtractableTextError`.
- [ ] **T1.2 Text cleaning (P0)**
  - Whitespace normalization, de-hyphenation, repeating header/footer removal.
  - *Accept:* unit tests with before/after strings.
- [ ] **T1.3 Chunking service (P0)**: `chunking_service.py`
  - Recursive splitter (600 tokens, 80 overlap, 100 min), page mapping (`page_start`, `page_end`), section titles when detectable.
  - *Accept:* no chunk exceeds max size; overlap present; every chunk has a valid page; chunk text never crosses documents. See `docs/RAG_PIPELINE.md §3`.
- [ ] **T1.4 Embedding service (P0)**: `embedding_service.py`
  - Load BGE-small once (singleton), `embed_passages(list[str])`, `embed_query(str)` with BGE prefix, normalized vectors, batch size 32.
  - *Accept:* output dim = 384; norms ≈ 1; query/passages use different prefixes (test).
- [ ] **T1.5 Ingestion script (P0)**
  - CLI: `python -m app.scripts.ingest path/to.pdf --user dev`. Inserts document + chunks in one transaction.
  - *Accept:* rows exist; `status=ready`; failure mid-way leaves no partial chunks.
- [ ] **T1.6 Retriever v0 (P0)**: `retriever.py`
  - Cosine top-N scoped by `user_id` + `document_ids` (required params).
  - *Accept:* integration test (testcontainers) returns expected chunk for a known question; calling without `user_id` is a type/test failure.
- [ ] **T1.7 LLM client (P0)**: `llm_client.py`
  - `LLMClient` protocol + Gemini adapter (+ Ollama adapter stub). Temperature 0, JSON output.
  - *Accept:* mocked test for parse success/failure; real call behind an env flag.
- [ ] **T1.8 Prompt + generation (P0)**: `prompts.py`, `pipeline.py` (v0)
  - Use system prompt from `docs/RAG_PIPELINE.md §7`; parse into `LLMAnswer` Pydantic model.
  - *Accept:* CLI `python -m app.scripts.ask "question"` prints answer + sources.
- [ ] **T1.9 Minimal refusal (P0)**
  - `REFUSAL_MESSAGE` constant; refuse when no chunks or `answerable=false`.
  - *Accept:* Tests A and C pass with real or stubbed LLM.

**⛔ STOP: Phase 1 review.** Summarize; wait for approval.

---

## Phase 2 (V1): Usable Product

### Backend
- [ ] **T2.1 Models & schemas (P0)**: SQLAlchemy models + Pydantic schemas per `docs/DATABASE.md`, `docs/API.md`.
- [ ] **T2.2 Auth stub (P0)**: `deps.py` provides `get_current_user` returning a fixed dev user (replaced in Phase 3). All routes take `user` via dependency.
- [ ] **T2.3 Upload endpoint (P0)**: `POST /api/documents/upload`
  - Validation (extension, magic-bytes MIME, size), content-hash dedupe, store file, create row `uploaded`, kick off background ingestion.
  - *Accept:* 202 with `document_id`; 400/409/413 cases tested.
- [ ] **T2.4 Background ingestion (P0)**: status `processing → ready | failed` with `error_message`.
  - *Accept:* integration test polls until `ready`; corrupt PDF → `failed`.
- [ ] **T2.5 Document endpoints (P0)**: list, get, download file, delete (cascade + file removal, ownership checked).
- [ ] **T2.6 TXT / MD / DOCX extraction (P1)**: extend `extraction_service` (headings → `section_title`).
- [ ] **T2.7 Chat endpoint (P0)**: `POST /api/chat`
  - Validates all `document_ids` belong to user and are `ready`; runs pipeline; persists conversation + messages; returns `{answer, sources, grounded}`.
- [ ] **T2.8 Cosine floor gate (P0)**: drop candidates below `MIN_COSINE`; refuse if none. `grounded` flag set correctly.
- [ ] **T2.9 Basic citations (P0)**: `[n]` markers + `sources[]` with document, page, snippet (first ~200 chars of the chunk).
- [ ] **T2.10 Conversations endpoints (P1)**: list, get messages, delete.
- [ ] **T2.11 Feedback endpoint (P2)**: thumbs up/down.

### Frontend
- [ ] **T2.12 Next.js scaffold (P0)**: TS strict, Tailwind, shadcn/ui, TanStack Query, `lib/api.ts`.
- [ ] **T2.13 Document sidebar (P0)**: upload dropzone, list with status badges, polling while `processing`, checkbox selection, delete.
- [ ] **T2.14 Chat window (P0)**: message list, composer, loading state, disabled if no ready doc selected.
- [ ] **T2.15 Citations UI (P0)**: `CitationBadge` + `SourceDrawer`; render `[n]` in answers.
- [ ] **T2.16 Refusal UI (P0)**: distinct neutral style when `grounded=false`.
- [ ] **T2.17 Error & empty states (P1)**: per `docs/FRONTEND.md §7`.

### Tests
- [ ] **T2.18 Refusal Tests A–D (P0)** (see `docs/TESTING.md §4`).
- [ ] **T2.19 API contract tests (P0)**: response shapes for upload/list/chat/refusal.

**⛔ STOP: Phase 2 review.**

---

## Phase 3 (V2): Production RAG

### Grounding & retrieval quality
- [ ] **T3.1 Reranker (P0)**: `reranker.py` (BGE cross-encoder); scores top-N → top-K; thread-pooled.
  - *Accept:* deterministic ordering test on fixture; batch inference.
- [ ] **T3.2 Relevance gate on rerank score (P0)**: `gate_relevance()` using `MIN_TOP_SCORE` / `MIN_CHUNK_SCORE` from config. See `docs/RAG_PIPELINE.md §6`.
- [ ] **T3.3 Structured output + answerability (P0)**: Pydantic `LLMAnswer`; retry-once-then-refuse on parse failure.
- [ ] **T3.4 Citation validation gate (P0)**: `validate_citations()`; refuse on failure. Unit tests for every failure mode.
- [ ] **T3.5 Query rewriter (P1)**: uses history only to make the question standalone; never answers.
  - *Accept:* follow-up test ("What are its four conditions?" → standalone question).
- [ ] **T3.6 Hybrid retrieval (P1)**: tsvector keyword search + Reciprocal Rank Fusion, behind `ENABLE_HYBRID`.
  - *Accept:* exact-token test (e.g. "HTTP 404", ID strings) improves vs. vector-only.
- [ ] **T3.7 Context builder (P0)**: numbered, delimited context with token cap; prompt-injection wording.
- [ ] **T3.8 Optional verifier pass (P2)**: second LLM check "is the answer fully supported?" behind `ENABLE_VERIFIER`.
- [ ] **T3.9 Multi-doc balance (P2)**: per-document retrieval quota so one document can't dominate.

### Auth, security, hardening
- [ ] **T3.10 Real authentication (P0)**: JWT verification (Better Auth/Clerk), `users` table sync, ownership checks on every route.
- [ ] **T3.11 Isolation test suite (P0)**: `tests/security/` per `docs/TESTING.md §5`. Must pass in CI.
- [ ] **T3.12 Upload hardening (P0)**: page-count cap, magic-byte MIME, random storage names, optional ClamAV hook.
- [ ] **T3.13 Rate limiting (P1)**: per-user limits on upload and chat.
- [ ] **T3.14 Prompt-injection tests (P0)**: Test H + poisoned-document test.

### Ops
- [ ] **T3.15 Full Docker Compose (P0)**: db, backend, frontend; models baked/cached in image.
- [ ] **T3.16 CI (P0)**: GitHub Actions per `docs/DEPLOYMENT.md §6`: lint, types, tests, refusal smoke, isolation.
- [ ] **T3.17 Refusal Tests A–H (P0)**: all passing.
- [ ] **T3.18 Baseline eval run (P0)**: create dataset (≥ 60 questions), run `run_eval`, calibrate thresholds, commit the config + first report.

**⛔ STOP: Phase 3 review.**

---

## Phase 4 (V3): AI-Engineering Showcase

- [ ] **T4.1 Full eval pipeline (P0)**: all metrics in `docs/EVALUATION.md §5`, markdown/HTML report to `eval/reports/`.
- [ ] **T4.2 Threshold calibration script (P0)**: sweep, plots, recommended thresholds written to a config snippet.
- [ ] **T4.3 Langfuse tracing (P1)**: span per stage, refusal reason, scores, latency, tokens; behind a flag.
- [ ] **T4.4 Streaming (P1)**: `POST /api/chat/stream` (SSE), stream only after all gates pass.
- [ ] **T4.5 Background workers (P1)**: Redis + ARQ for ingestion; keep BackgroundTasks fallback for dev.
- [ ] **T4.6 PDF preview (P1)**: `react-pdf` viewer, jump to cited page, highlight snippet.
- [ ] **T4.7 Conversation history UI (P1)**: sidebar of past conversations.
- [ ] **T4.8 OCR for scanned PDFs (P2)**: Tesseract fallback when no extractable text.
- [ ] **T4.9 NLI-based citation support check (P2)**: entailment score per answer sentence.
- [ ] **T4.10 Playwright E2E (P1)**: upload → ask → citation → refusal.
- [ ] **T4.11 README + demo (P0)**: architecture diagram, eval results table, screenshots/GIF.
- [ ] **T4.12 Deployment (P1)**: per `docs/DEPLOYMENT.md §7`.

**⛔ STOP: Final review.**

---

## Decisions & Notes (Claude Code: append here)

| Date | Task | Decision / Deviation | Reason |
|---|---|---|---|
| 2026-09-29 | T0.2 | Compose file is implemented, but live pgvector validation is pending because Docker is unavailable on the host. | `docker` is not installed or on PATH. |
| 2026-09-29 | T0.3 | Health, lint, and formatting checks pass; mypy is pending because it is not installed. | The environment has no `mypy` executable. |
| 2026-09-29 | T0.4 | ORM metadata, migration syntax, offline SQL generation, and unit checks pass; live upgrade/down is pending. | The available PostgreSQL server rejects the documented local credentials, and Docker is unavailable. |

## Known Issues / Backlog

- Table-heavy PDFs may extract poorly (consider layout-aware extraction).
- "Summarize the whole document" isn't served by top-K retrieval (consider a separate map-reduce mode).
- Multilingual support requires a multilingual embedder + reranker.
