# Ultimate Debugging Master Plan

Updated: 2026-05-31 09:12 +07

## Session
- Task ID: DEBUG-ULT-001
- Branch: agent-run
- Start commit: 79b1614
- Scope: full evidence-based audit across frontend, gateway/API, ML services, pipeline, database, Docker, and security.
- Editing rule: no product code fix before reproduction evidence and root-cause notes exist.

## Current Phase
Bootstrap and baseline discovery.

## Active Task
Create required debug documentation, checkpoint durable state, then run static inventory and baseline validation.

## Next Exact Action
Validate `docs/agent/TASK_QUEUE.json`, inspect the staged doc diff, and commit the initialization docs as `docs: initialize ultimate debugging session`.

## Method
1. Inventory the current repository surfaces from files, not memory.
2. Record baseline validation output before fixes.
3. Generate testable hypotheses per subsystem.
4. Add Selenium/Chrome browser audit harness and save artifacts under `reports/debug/browser/`.
5. Reproduce failures, collect evidence, fix one root cause at a time, and verify.
6. Update `COMPACT_RECOVERY.md` before and after each major phase.

## Guardrails
- Do not log secrets, tokens, full CV contents, or private user data.
- Keep commits scoped; this repository started dirty.
- `morph-mcp` was requested but no callable morph tool was exposed by tool discovery; use normal local editing tools.
