---
description: Audit and test multi-tenant isolation
---

1. Run `pytest tests/security -q --tb=short` from `backend/`.
2. Grep the codebase for violations and report each hit:
   - `select(DocumentChunk` or raw SQL touching `document_chunks`, `documents`, `conversations`, `messages` outside `app/db/repositories/`.
   - Any repository/retriever function where `user_id` is optional or has a default.
   - Any route that loads a resource by id without an ownership check.
   - Any cache key missing `user_id` or the sorted `document_ids`.
3. Verify not-owned resources return 404 (not 403).
4. Verify logs never contain document text (see test S15).
5. Output a checklist of findings with file:line references and proposed fixes. Fix issues that are clearly violations; ask before larger refactors.
