# DEPLOYMENT.md: Docker, Configuration, CI/CD & Hosting

---

## 1. Environments

| Env | Purpose | Auth | LLM | Notes |
|---|---|---|---|---|
| `dev` | Local development | Fixed dev user | Gemini or Ollama | `APP_ENV=dev`, debug info in responses |
| `test` | CI | Overridden | Stub/double | Testcontainers Postgres |
| `staging` | Pre-release | Real auth | Real | Mirrors prod |
| `prod` | Live | Real auth | Real | `APP_ENV=prod`, no debug output |

---

## 2. Environment Variables

### Backend (`backend/.env.example`)
```env
# App
APP_ENV=dev                       # dev | test | staging | prod
LOG_LEVEL=INFO
LOG_CONTENT=false                 # never true in prod
FRONTEND_ORIGIN=http://localhost:3000
REQUEST_TIMEOUT_SECONDS=60

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/docqa # pooled app URL
DATABASE_URL_UNPOOLED=                              # direct URL for Alembic
DATABASE_URL_TEST=                                   # separate test branch URL

# Storage
STORAGE_BACKEND=local             # local | s3
UPLOAD_DIR=./uploads
S3_BUCKET=
S3_ENDPOINT_URL=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
MAX_UPLOAD_MB=25
MAX_PDF_PAGES=500

# Models
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIM=384
RERANKER_MODEL=BAAI/bge-reranker-base
HF_HOME=/models
HF_HUB_OFFLINE=0                  # set 1 in prod images with baked models

# LLM
LLM_PROVIDER=gemini               # gemini | ollama | stub
LLM_MODEL=gemini-2.0-flash        # set to the model you use
GEMINI_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
LLM_TIMEOUT_SECONDS=30

# RAG
CHUNK_TARGET_TOKENS=600
CHUNK_OVERLAP_TOKENS=80
CHUNK_MIN_TOKENS=100
TOP_N=20
TOP_K=5
MIN_COSINE=0.30
MIN_TOP_SCORE=0.40                # PLACEHOLDER: calibrate with eval/calibrate_threshold.py
MIN_CHUNK_SCORE=0.30              # PLACEHOLDER: calibrate
MAX_CONTEXT_TOKENS=3000
ENABLE_HYBRID=false
ENABLE_VERIFIER=false

# Auth (Phase 3)
AUTH_PROVIDER=dev                 # dev | clerk | better-auth
JWKS_URL=
JWT_AUDIENCE=
JWT_ISSUER=

# Rate limiting / jobs (Phase 3-4)
REDIS_URL=redis://localhost:6379/0
RATE_LIMIT_CHAT=30/minute
RATE_LIMIT_UPLOAD=10/hour

# Observability (Phase 4)
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=
```
Startup validation (pydantic-settings): fail fast if `APP_ENV=prod` and `AUTH_PROVIDER=dev`, or `LOG_CONTENT=true`, or required secrets are missing.

### Frontend (`frontend/.env.example`)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_MAX_UPLOAD_MB=25
```

---

## 3. Docker

### 3.1 Backend `Dockerfile` (multi-stage, models baked in)
```dockerfile
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/models
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 && rm -rf /var/lib/apt/lists/*

FROM base AS deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM deps AS models
# Bake models so production never downloads at runtime (pin revisions in code/config)
RUN python - <<'PY'
from sentence_transformers import SentenceTransformer, CrossEncoder
SentenceTransformer("BAAI/bge-small-en-v1.5")
CrossEncoder("BAAI/bge-reranker-base")
PY

FROM deps AS final
COPY --from=models /models /models
COPY app ./app
COPY alembic.ini .
RUN useradd -m appuser && chown -R appuser /app /models
USER appuser
ENV HF_HUB_OFFLINE=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
Tips: use CPU-only PyTorch wheels to shrink the image (`--extra-index-url https://download.pytorch.org/whl/cpu`).

### 3.2 Frontend `Dockerfile`
```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-alpine AS run
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
```
(Requires `output: "standalone"` in `next.config.js`.)

### 3.3 `docker-compose.yml`
```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: docqa
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d docqa"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build: ./backend
    env_file: ./backend/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/docqa
    depends_on:
      db: { condition: service_healthy }
    ports: ["8000:8000"]
    volumes: [uploads:/app/uploads]
    command: sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"

  frontend:
    build:
      context: ./frontend
      args: { NEXT_PUBLIC_API_URL: http://localhost:8000/api }
    depends_on: [backend]
    ports: ["3000:3000"]

  # ---- Phase 4 ----
  redis:
    image: redis:7-alpine
    profiles: ["full"]
  worker:
    build: ./backend
    env_file: ./backend/.env
    command: arq app.worker.WorkerSettings
    depends_on: [db, redis]
    profiles: ["full"]

volumes:
  pgdata: {}
  uploads: {}
```
Run: `docker compose up --build` (or `--profile full` to include Redis/worker).

### 3.4 Optional Ollama service (fully local)
```yaml
  ollama:
    image: ollama/ollama
    volumes: [ollama:/root/.ollama]
    ports: ["11434:11434"]
```
then `docker exec -it <ollama> ollama pull qwen2.5:7b` (or Llama) and set `LLM_PROVIDER=ollama`. Small local models follow the JSON + refusal rules less reliably; re-run the eval and calibrate before trusting them.

---

## 4. Local Development Flow

### 4.1 Neon without Docker

Neon is the no-Docker path for PostgreSQL + pgvector. Link the project and create
the `dev` and `test` branches with the Neon CLI in your own terminal, then pull
each branch's variables. Keep the pooled URL in `DATABASE_URL` for application
traffic. Keep the direct/unpooled URL in `DATABASE_URL_UNPOOLED` for Alembic, and
put the separate test branch URL in `DATABASE_URL_TEST`. The application and
Alembic both use the shared URL converter in `app/config.py`; it emits
`postgresql+asyncpg://...?...&ssl=require` for asyncpg.

Set up the Python environment from `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic upgrade head
```

On macOS/Linux, replace `.\.venv\Scripts\python.exe` with `./.venv/bin/python`.
The database-backed integration and refusal suites skip with a clear message when
`DATABASE_URL_TEST` is empty and fail if it is the same database as `DATABASE_URL`.

### 4.2 Docker fallback

```bash
cp backend/.env.example backend/.env       # add GEMINI_API_KEY
cp frontend/.env.example frontend/.env.local
docker compose up -d db
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" && alembic upgrade head
uvicorn app.main:app --reload --port 8000
# new terminal
cd frontend && npm install && npm run dev
```
First run downloads models (~1 GB total); they're cached in `HF_HOME`.

---

## 5. Database Operations

- Migrations: `alembic upgrade head` on deploy (run as a release step or container start command, one instance at a time).
- Backups: daily `pg_dump` (managed Postgres snapshots preferred); test restores.
- pgvector: confirm the extension is available on your host (Neon, Supabase, Render Postgres, Railway, Fly Postgres, and AWS RDS support it). `CREATE EXTENSION vector;` runs in migration 0001.
- Tuning: monitor `hnsw.ef_search`; consider `maintenance_work_mem` bump when building the index on large tables.
- Stuck-job cleanup: a startup/cron task marks `processing` documents older than 15 min as `failed`.

---

## 6. CI (GitHub Actions)

`.github/workflows/ci.yml`

```yaml
name: CI
on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env: { POSTGRES_PASSWORD: postgres, POSTGRES_DB: docqa }
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U postgres" --health-interval 5s
          --health-timeout 3s --health-retries 10
    defaults: { run: { working-directory: backend } }
    env:
      APP_ENV: test
      LLM_PROVIDER: stub
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/docqa
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11", cache: pip }
      - uses: actions/cache@v4            # cache HF models between runs
        with: { path: ~/.cache/huggingface, key: hf-models-v1 }
      - run: sudo apt-get update && sudo apt-get install -y libmagic1
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: ruff check . && ruff format --check .
      - run: mypy app
      - run: alembic upgrade head && alembic downgrade base && alembic upgrade head
      - run: pytest tests/unit tests/integration tests/contract -q --cov=app --cov-fail-under=80
      - run: pytest tests/refusal -q          # REQUIRED
      - run: pytest tests/security -q         # REQUIRED
      - run: pip-audit

  frontend:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: frontend } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: npm ci
      - run: npm run lint && npm run typecheck && npm test -- --run
      - run: npm audit --omit=dev --audit-level=high

  secrets-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2

  nightly-eval:                 # separate workflow on a schedule
    if: github.event_name == 'schedule'
    # runs eval smoke subset; fails if abstention accuracy < 90% or false-answer rate > 10%
```

Branch protection: require `backend`, `frontend`, `secrets-scan` to pass before merging.

---

## 7. Hosting Options

| Component | Option A (simple) | Option B (cheap/free-ish) | Option C (self-hosted) |
|---|---|---|---|
| Frontend | Vercel | Vercel / Netlify | Docker on VPS |
| Backend | Render / Railway web service | Fly.io | Docker on VPS |
| Database | Neon or Supabase (pgvector) | Render/Railway Postgres | Postgres container + volume |
| Storage | S3 / R2 / Supabase Storage | Same | Local volume |
| Redis (Phase 4) | Upstash / Render Redis | n/a | Container |

Sizing: the backend needs **≥ 2 GB RAM** for the embedder + reranker on CPU (4 GB comfortable). Free tiers with 512 MB will not fit both models; either use a hosted embeddings API or a paid instance.

### Deploy steps (Render/Railway example)
1. Provision Postgres with pgvector; note `DATABASE_URL`.
2. Create the backend service from `backend/Dockerfile`; set env vars (§2); health check `/api/health`; release command `alembic upgrade head`.
3. Attach a persistent disk for `UPLOAD_DIR` or configure S3 (`STORAGE_BACKEND=s3`); prefer S3 for multi-instance.
4. Deploy the frontend to Vercel with `NEXT_PUBLIC_API_URL=https://<backend>/api`.
5. Set backend `FRONTEND_ORIGIN` to the Vercel URL (CORS).
6. Configure the auth provider's allowed origins/redirects.
7. Smoke test: upload fixture → chat → verify citation → out-of-scope question → refusal.

---

## 8. Observability & Operations

- **Health:** `/api/health` for load balancer checks.
- **Logs:** JSON to stdout with `request_id`, `user_id`, route, latency, `refusal_reason`. Ship to your platform's log service.
- **Metrics to watch:** p95 latency by stage; refusal rate (sudden jumps signal retrieval or threshold problems); parse-error rate; ingestion failure rate; LLM error/timeout rate; token usage/cost.
- **Langfuse (Phase 4):** trace each request with spans (rewrite, retrieve, rerank, gate, generate, validate) and attach scores/refusal reasons; link thumbs feedback.
- **Alerts:** health check failing; error rate > 2%; p95 chat latency > 10 s; ingestion failure spike; LLM provider errors.

---

## 9. Release Checklist

- [ ] CI green (incl. refusal + isolation suites)
- [ ] Thresholds calibrated for the current models/chunking (`eval/reports/thresholds.yaml` matches config)
- [ ] Latest eval report meets targets (abstention ≥ 95%, faithfulness ≥ 95%)
- [ ] `APP_ENV=prod`, real auth, debug output off, `LOG_CONTENT=false`
- [ ] Migrations tested on a copy of prod data
- [ ] Backups configured and a restore tested
- [ ] Secrets rotated/stored in the platform secret manager
- [ ] CORS origin + security headers verified
- [ ] Rate limits enabled
- [ ] Smoke test passed on staging
- [ ] Rollback plan: previous image tag + `alembic downgrade` notes for the migration

---

## 10. Cost Notes

- Embeddings/reranking are local (free, CPU time). The main variable cost is the LLM: ~1.5–3k input tokens + ≤ 600 output tokens per grounded answer; refusals at Gate 1 cost **zero** LLM tokens.
- Reduce cost: smaller `TOP_K`, tighter `MAX_CONTEXT_TOKENS`, cache identical (question, doc-set) results briefly (key includes `user_id`), use a fast/cheap model for the query rewriter.
