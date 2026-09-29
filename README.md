# Document Q&A Bot: Context-Grounded RAG

Ask questions about your own documents and get answers **only** from them, with citations. If the answer isn't in your documents, the bot says so instead of guessing, even when the underlying LLM knows the answer.

> **"I couldn't find the answer in the uploaded documents."**

---

## Why this project exists

General chatbots blend document content with pretrained knowledge, so you can't tell which parts of an answer come from your files. This project treats **retrieved evidence as the only source of truth** and uses the LLM purely to turn that evidence into natural language, with explicit gates that stop the request when the evidence isn't there.

## Features

- Upload PDF, DOCX, TXT, Markdown (page-aware extraction)
- Semantic + keyword (hybrid) retrieval with cross-encoder reranking
- **Grounding gates:** relevance threshold → LLM answerability → citation validation
- Citations with document, page and quoted snippet; click to inspect the source
- Per-user isolation and per-chat document selection
- Follow-up questions via query rewriting (history is never used as a fact source)
- Streaming answers, feedback, conversation history
- Evaluation harness with abstention, faithfulness and retrieval metrics

## Demo

```
Upload: operating_systems.pdf

You: What is a process?
Bot: A process is a program in execution. [1]
     Sources: [1] operating_systems.pdf · page 12

You: Who invented Python?
Bot: I couldn't find the answer in the uploaded documents.
```

_(Add a screenshot/GIF here.)_

## Architecture

```
                 ┌───────────────────┐
                 │  Next.js Frontend │
                 └─────────┬─────────┘
                       REST / SSE
                 ┌─────────▼─────────┐
                 │  FastAPI Backend  │
                 └───┬───────────┬───┘
     Ingestion       │           │       Query
 ┌───────────────────▼──┐   ┌────▼───────────────────────────────┐
 │ Extract → Clean →    │   │ Rewrite → Embed → Retrieve →       │
 │ Chunk → Embed → Store│   │ Rerank → GATE 1 → LLM → GATE 2 →   │
 └──────────┬───────────┘   │ GATE 3 → Answer + Citations        │
            │               └────────────┬───────────────────────┘
            └──────────────┬─────────────┘
                 ┌─────────▼──────────┐
                 │ PostgreSQL+pgvector│
                 └────────────────────┘
```

### The grounding gates

| Gate | Check | On failure |
|---|---|---|
| 1. Relevance | Best reranker score ≥ calibrated threshold | Refuse **without calling the LLM** |
| 2. Answerability | LLM returns `answerable: true` with a non-empty answer | Refuse |
| 3. Citations | Every sentence cited; every citation maps to a provided chunk | Refuse |

## Tech Stack

Next.js · TypeScript · Tailwind · shadcn/ui · FastAPI · Pydantic · SQLAlchemy · PostgreSQL + pgvector · PyMuPDF · BGE embeddings (`bge-small-en-v1.5`) · BGE reranker · Gemini or Ollama · Docker · Langfuse

## Quick Start

```bash
git clone <repo> && cd <repo>
cp backend/.env.example backend/.env         # add GEMINI_API_KEY (or set LLM_PROVIDER=ollama)
cp frontend/.env.example frontend/.env.local
docker compose up --build
```
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

The first start downloads embedding/reranker models (~1 GB).

### Without Docker
See `docs/DEPLOYMENT.md §4`.

## Evaluation Results

_(Fill from `eval/reports/`.)_

| Metric | Value | Target |
|---|---|---|
| Abstention accuracy (out-of-scope + near-miss) | _TBD_ | ≥ 95% |
| Answer rate (in-scope) | _TBD_ | ≥ 85% |
| Faithfulness | _TBD_ | ≥ 95% |
| Citation accuracy | _TBD_ | ≥ 90% |
| Hit@5 | _TBD_ | ≥ 90% |
| p95 latency | _TBD_ | < 8 s |

Ablations (vector-only vs. hybrid; with/without reranker; with/without verifier): _TBD_.

## Testing

```bash
cd backend
pytest -q                 # everything
pytest tests/refusal -q   # "no outside knowledge" contract
pytest tests/security -q  # cross-user isolation
python -m eval.run_eval --dataset eval/dataset.jsonl
```

## Project Docs

| Doc | Purpose |
|---|---|
| [`prd.md`](prd.md) | Product requirements |
| [`trd.md`](trd.md) | Technical design |
| [`TASKS.md`](TASKS.md) | Build plan / task queue |
| [`CLAUDE.md`](CLAUDE.md) | Guide for AI coding agents |
| [`docs/DATABASE.md`](docs/DATABASE.md) | Schema and queries |
| [`docs/API.md`](docs/API.md) | REST/SSE API |
| [`docs/RAG_PIPELINE.md`](docs/RAG_PIPELINE.md) | Ingestion, retrieval, gates, prompts |
| [`docs/FRONTEND.md`](docs/FRONTEND.md) | UI spec |
| [`docs/TESTING.md`](docs/TESTING.md) | Test strategy |
| [`docs/EVALUATION.md`](docs/EVALUATION.md) | Metrics and calibration |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Threat model |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Docker, CI, hosting |

## Agent Workflows

Reusable workflows live in [`.claude/commands/`](.claude/commands/):

| Command | Purpose |
|---|---|
| [`next-task.md`](.claude/commands/next-task.md) | Implement the next unchecked task and stop at the phase boundary |
| [`run-refusal-tests.md`](.claude/commands/run-refusal-tests.md) | Run the grounding/refusal contract and report leakage risk |
| [`check-isolation.md`](.claude/commands/check-isolation.md) | Audit tenant isolation and ownership checks |
| [`calibrate-threshold.md`](.claude/commands/calibrate-threshold.md) | Calibrate relevance thresholds from the evaluation dataset |
| [`new-endpoint.md`](.claude/commands/new-endpoint.md) | Add an API endpoint with schemas, tests, and documentation |
| [`review-grounding.md`](.claude/commands/review-grounding.md) | Review changes against the grounding hard rules |

## Limitations

- **Grounded ≠ true.** The bot faithfully reports what your document says; if the document is wrong, so is the answer.
- Scanned PDFs need OCR (planned); tables and figures may extract imperfectly.
- Relevance thresholds are calibrated per embedding/reranker/chunking setup and must be re-calibrated when those change.
- "Summarize the whole document" is not well served by top-K retrieval.
- With a cloud LLM, retrieved passages and questions are sent to the provider. Use Ollama for fully local operation.
- English-only in V1.

## Roadmap

V0 proof of concept → V1 usable product → V2 production RAG (rerank, hybrid, auth, isolation) → V3 evaluation, observability, streaming, workers, PDF preview. See `TASKS.md`.

## License

_Choose a license (e.g. MIT)._
