# EVALUATION.md: Measuring Grounding, Retrieval & Abstention

Unit tests prove the logic works; **evaluation** measures how well the whole system behaves on realistic questions. It also produces the calibrated thresholds that Gate 1 depends on, and the evidence for the portfolio README.

---

## 1. What We Measure

| Area | Question answered |
|---|---|
| Retrieval | Does the right evidence reach the reranker/LLM? |
| Grounding gate | Does the system refuse when it should, and answer when it should? |
| Faithfulness | Is every claim supported by the cited context? |
| Citation quality | Do citations point to text that actually supports the claim? |
| Answer quality | Is the answer correct and complete for in-scope questions? |
| Latency & cost | Is it fast and cheap enough? |

---

## 2. Dataset

Location: `backend/eval/dataset.jsonl` (one JSON object per line). Source documents live in `backend/eval/corpus/` (public-domain or self-written texts only, not copyrighted material).

### 2.1 Schema
```json
{
  "id": "os-0007",
  "document": "os_mini.pdf",
  "question": "What are the four necessary conditions for deadlock?",
  "type": "in_scope",
  "expected_answer": "Mutual exclusion, hold and wait, no preemption, circular wait.",
  "expected_pages": [87],
  "must_include": ["mutual exclusion", "hold and wait", "no preemption", "circular wait"],
  "notes": "multi-fact answer"
}
```

| Field | Required | Meaning |
|---|---|---|
| `id` | ✓ | unique, stable |
| `document` | ✓ | corpus file (or list of files for multi-doc) |
| `question` | ✓ | |
| `type` | ✓ | `in_scope` \| `out_of_scope` \| `near_miss` \| `followup` \| `injection` \| `multi_doc` |
| `expected_answer` | in_scope | reference answer |
| `expected_pages` | in_scope | gold pages that contain the evidence |
| `must_include` | optional | key phrases the answer must contain (cheap correctness check) |
| `history` | followup | prior turns to replay |
| `notes` | optional | |

### 2.2 Question types (target mix, ≥ 150 questions across ≥ 3 documents)

| Type | Share | Description | Expected behavior |
|---|---|---|---|
| `in_scope` | 50% | Answer is explicit in the document (facts, definitions, lists, numbers) | Answer + correct citation |
| `out_of_scope` | 20% | Unrelated to the docs (general knowledge the LLM knows: "Who invented Python?") | Refuse |
| `near_miss` | 15% | Same topic/vocabulary, but the specific fact isn't in the document | Refuse |
| `followup` | 5% | Pronoun-based follow-ups | Answer (rewriter works) |
| `injection` | 5% | "Ignore your rules…", or a poisoned chunk | Refuse / no compliance |
| `multi_doc` | 5% | Needs evidence from ≥ 2 documents | Answer with citations from each |

`near_miss` is the most valuable category: it's where retrieval scores are high but the answer is absent.

### 2.3 Authoring guidance
- Write in-scope questions from the text (paraphrase, don't copy). Include some that require combining two adjacent chunks.
- Write near-misses by taking an in-scope question and changing one detail to something absent.
- Use an LLM to draft candidate questions, **then review by hand**; model-generated labels alone are not trustworthy.
- Freeze the dataset with a version tag (`dataset_version` in the report header); changes after freezing create a new version.

---

## 3. Harness (`eval/run_eval.py`)

```
python -m eval.run_eval --dataset eval/dataset.jsonl --out eval/reports/2026-09-29_run1
      [--config eval/configs/baseline.yaml] [--limit 50] [--live-llm]
```

Steps per question:
1. Ingest each corpus document once (cached across the run).
2. Run the real pipeline (`answer_question`) with `debug=True` capturing: candidates, cosine, rerank scores, gate outcomes, answer, citations, timings, tokens.
3. Score with the metrics in §4.
4. Write `results.jsonl` (per-question), `summary.json`, and `report.md` (+ optional `report.html` with plots).

The config file can override chunk size/overlap, `TOP_N/K`, thresholds, hybrid on/off, model names, so runs are comparable **ablations**.

---

## 4. Metrics

### 4.1 Retrieval (in_scope, followup, multi_doc)
| Metric | Definition |
|---|---|
| **Hit@K** | Fraction where a chunk covering an `expected_pages` page is in the top-K after rerank (K = 1, 3, 5) |
| **MRR** | Mean reciprocal rank of the first gold chunk |
| **Recall@N (pre-rerank)** | Gold chunk present in the top-N candidates (measures the retriever alone) |
| **Reranker lift** | Hit@5 after rerank minus Hit@5 of raw vector order |

### 4.2 Gate / Abstention (all types)
Treat "answered" (grounded=true) as the positive class:

| Metric | Definition | Target (V2) |
|---|---|---|
| **Abstention accuracy** | `out_of_scope` + `near_miss` + `injection` correctly refused | ≥ 95% |
| **Answer rate** | `in_scope` + `followup` + `multi_doc` answered (not refused) | ≥ 85% |
| **False-answer rate** | Should-refuse questions that got a grounded answer | ≤ 5% |
| **False-refusal rate** | Should-answer questions that were refused | ≤ 15% |
| **Balanced accuracy / F1** | Summary of the above | track |

Break down by `type` and by refusal reason (`below_threshold`, `llm_unanswerable`, `bad_citations`, `parse_error`).

### 4.3 Answer Quality (answered in-scope)
| Metric | How |
|---|---|
| **Must-include coverage** | Fraction of `must_include` phrases present (case-insensitive, normalized) |
| **Correctness** | LLM-judge comparing to `expected_answer` → `correct` / `partial` / `incorrect`, plus a 10% manual audit |
| **Completeness** | Judge rating of whether all parts are covered |

### 4.4 Faithfulness & Citations
| Metric | How |
|---|---|
| **Faithfulness** | Split answer into claims/sentences; judge (LLM or NLI) whether each is entailed by the *provided* context. Score = supported / total |
| **Citation precision** | For each `[n]`, does chunk *n* support the sentence? (judge/NLI) |
| **Citation recall** | Fraction of factual sentences that carry a valid citation |
| **Page accuracy** | Cited chunk's pages intersect `expected_pages` |
| **Leakage check** | For answered `out_of_scope`/`near_miss` items → each counts as a leakage incident; list them in the report |

Judge prompts live in `eval/judges.py`; use a **different** model (or at least a different prompt/temperature 0) than the generator when possible, and keep judge prompts versioned. Validate the judge on ~30 hand-labeled examples and report its agreement.

### 4.5 Performance
Latency per stage (p50/p95): rewrite, embed, retrieve, rerank, LLM, total; token counts; estimated cost per 100 questions.

Optional: RAGAS / DeepEval can supply cross-checks for context precision/recall and faithfulness, but the custom metrics above are the source of truth for this project.

---

## 5. Report Format (`report.md`)

```
# Eval Report: run1
Date · git SHA · dataset_version · config (models, chunking, thresholds)

## Summary table
| Metric | Value | Target | Status |

## Abstention by type (confusion matrix)
## Retrieval (Hit@1/3/5, MRR, reranker lift)
## Faithfulness & citations
## Latency
## Leakage incidents (each with question, answer, scores)
## Worst 10 false refusals / worst 10 false answers (with top chunks + scores)
## Ablation table (if multiple configs)
```
Commit key reports to `eval/reports/` and copy the headline table into `README.md`.

---

## 6. Threshold Calibration (`eval/calibrate_threshold.py`)

Purpose: choose `MIN_TOP_SCORE` (and `MIN_CHUNK_SCORE`, `MIN_COSINE`) using labeled data instead of guessing.

### 6.1 Procedure
1. For each question, run retrieval + rerank only (no LLM). Record `top_rerank_score` (and top cosine).
2. Label: `should_answer = type in {in_scope, followup, multi_doc}`.
3. Sweep candidate thresholds `t` over the score range (e.g. 200 steps). For each `t`:
   - `answered = top_rerank_score ≥ t`
   - compute **abstention accuracy** (TN/(TN+FP)) and **answer rate** (TP/(TP+FN)).
4. Plot score histograms for should-answer vs. should-refuse, and the ROC / precision-recall curves.
5. Select `t*` = the **lowest** threshold with abstention accuracy ≥ target (default 0.97) so as to maximize answer rate; if multiple, prefer the one in the widest stable plateau.
6. Set `MIN_CHUNK_SCORE = t* − margin` (default margin 0.1× score range) so supporting chunks with slightly lower scores still reach the LLM.
7. Cosine floor: choose `MIN_COSINE` = the 1st percentile of the gold chunk's cosine (never drops the gold chunk in > 1% of cases).
8. Output `eval/reports/thresholds.yaml`:
```yaml
calibrated_at: 2026-09-29
dataset_version: v1
reranker: BAAI/bge-reranker-base
embedding: BAAI/bge-small-en-v1.5
MIN_TOP_SCORE: 0.42
MIN_CHUNK_SCORE: 0.30
MIN_COSINE: 0.28
metrics_at_threshold: {abstention_accuracy: 0.97, answer_rate: 0.88}
```
(The numbers above are illustrative only.)

### 6.2 When to recalibrate
Any change to: embedding model, reranker model, chunk size/overlap/cleaning, hybrid on/off, or a major shift in document types. CI can warn if `thresholds.yaml` `embedding`/`reranker` don't match config.

### 6.3 Handling separability problems
If the histograms overlap heavily (can't reach the target abstention without a poor answer rate):
- improve chunking/extraction (garbage chunks lower scores for real answers),
- use hybrid retrieval,
- try a stronger reranker,
- enable the verifier pass (Gate 2b) to catch what the score gate lets through,
- add per-question-type analysis; near-misses are the hardest.

---

## 7. Regression Workflow

1. Change something in retrieval/prompting/chunking.
2. Run `run_eval` with the baseline and new configs on the same dataset version.
3. Compare in the ablation table. **Reject changes** that reduce abstention accuracy or faithfulness below the targets even if answer rate improves.
4. Save the reports; update `thresholds.yaml` if needed.

CI (nightly): run the eval on a small **smoke subset** (~30 questions) and fail if abstention accuracy < 90% or false-answer rate > 10%.

---

## 8. Feedback Loop

- Thumbs-down messages (and refusals users flag as wrong) are exported weekly: `python -m eval.export_feedback` → candidate rows for the dataset (question, doc, actual answer, sources).
- Triage by hand; add confirmed cases as new dataset rows in the next dataset version.
- Langfuse traces (Phase 4) help find the retrieval/gate stage that failed.

---

## 9. Reporting Checklist (for the README/portfolio)

- [ ] Dataset size, type mix, and document sources
- [ ] Headline table: abstention accuracy, answer rate, faithfulness, citation accuracy, Hit@5, p95 latency
- [ ] Ablations: vector-only vs. hybrid; with vs. without reranker; with vs. without verifier
- [ ] Calibration plot (score histograms + chosen threshold)
- [ ] Known failure cases and their causes
