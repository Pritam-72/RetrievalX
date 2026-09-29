---
description: Review recent changes for grounding and leakage risks
---

Review the current diff (or `$ARGUMENTS` files) against the Hard Rules in `CLAUDE.md §6`:

- Is any path calling the LLM before Gate 1 has passed?
- Does any code build answers from anything other than retrieved chunks (e.g. history, hard-coded text, provider knowledge)?
- Is the refusal string always `REFUSAL_MESSAGE`, with no extra hints?
- Are citations validated against provided chunk numbers?
- Are thresholds read from config, not hardcoded?
- Could chunk text or question text end up in logs?
- Is untrusted text kept inside `<context>`?

Output a short report: findings ranked by severity, file:line, and a suggested fix. Don't change code unless asked.
