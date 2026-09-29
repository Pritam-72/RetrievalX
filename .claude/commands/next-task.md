---
description: Complete the next unchecked task in TASKS.md, then stop
---

Follow this procedure exactly:

1. Read `CLAUDE.md` (Hard Rules and Workflow Rules) and `TASKS.md`.
2. Find the first unchecked `[ ]` task. If `$ARGUMENTS` names a task ID (e.g. `T1.3`), use that one instead.
3. Read the docs the task references (e.g. `docs/RAG_PIPELINE.md`, `docs/DATABASE.md`, `docs/API.md`).
4. Write the plan in 3-6 bullets before coding. If anything conflicts with a Hard Rule, stop and ask.
5. Write or update tests first for anything touching the pipeline, gates, or isolation.
6. Implement the smallest change that satisfies the task's acceptance criteria.
7. Run the relevant checks from `CLAUDE.md §5` (pytest for the touched area, ruff, mypy; for frontend: lint, typecheck, tests). Fix failures.
8. Tick the task in `TASKS.md`. Add a row under "Decisions & Notes" if you deviated or made an assumption.
9. If this was the last task in a phase, STOP and summarize what was built and what to review. Do not begin the next phase.
10. Report: what changed, files touched, test results, and any follow-ups.

Do not start another task in the same run.
