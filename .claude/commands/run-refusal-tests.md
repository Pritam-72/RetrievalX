---
description: Run the refusal-contract suite and report leakage risk
---

1. From `backend/`, run: `pytest tests/refusal -q -x --tb=short`.
2. If any test fails, do not "fix" it by loosening assertions. Diagnose the stage (`no_chunks`, `below_threshold`, `llm_unanswerable`, `bad_citations`) using the debug info, then fix the pipeline.
3. Confirm these invariants hold:
   - Refusal responses have `answer == REFUSAL_MESSAGE`, `grounded == false`, `sources == []`.
   - On Gate 1 refusals, the LLM spy recorded 0 calls.
   - Tests A, C, E, G (should answer) and B, D, F, H, I, J (should refuse) all pass.
4. If `$ARGUMENTS` contains `live`, also run: `RUN_LIVE_LLM=1 pytest tests/refusal -m live -q`.
5. Summarize: pass/fail per test ID, any xfail (with reason), and remaining leakage risks.
