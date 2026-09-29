---
description: Calibrate relevance thresholds on the eval set
---

1. Ensure `backend/eval/dataset.jsonl` exists with in_scope, out_of_scope, and near_miss questions (see `docs/EVALUATION.md §2`). If it has fewer than 60 rows, say so and stop.
2. Run: `python -m eval.calibrate_threshold --dataset eval/dataset.jsonl`.
3. Review the output: score histograms, chosen `MIN_TOP_SCORE`, `MIN_CHUNK_SCORE`, `MIN_COSINE`, and the abstention accuracy / answer rate at the chosen point.
4. If separability is poor (heavy overlap), follow `docs/EVALUATION.md §6.3` and report options. Do not just lower the abstention target.
5. Write `eval/reports/thresholds.yaml` and propose the `.env` values. Do not silently overwrite `.env`; show the diff.
6. Re-run `pytest tests/refusal -q` with the new thresholds.
