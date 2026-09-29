---
description: Add an API endpoint following project conventions
---

Add the endpoint described in `$ARGUMENTS`:

1. Check `docs/API.md`. If the endpoint isn't specified, add its spec there first (path, request, response, errors).
2. Add Pydantic request/response schemas in `app/schemas/`.
3. Put logic in `app/services/` or `app/rag/`; keep the router thin.
4. Require `user: User = Depends(get_current_user)`; use repository helpers that take `user_id`. Return 404 for resources the user doesn't own.
5. Use the standard error format from `docs/API.md §1.1`.
6. Add tests: happy path, validation errors, ownership (404 for another user), and a contract test against the documented schema.
7. Regenerate frontend API types if the frontend uses it (`npm run gen:api`).
8. Run ruff, mypy, and the relevant pytest suites.
