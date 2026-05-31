# Ultimate Debugging Master Plan

Updated: 2026-05-31 15:20 +07

## Session
- Task ID: DEBUG-ULT-001
- Branch: agent-run
- Start commit: 79b1614
- Scope: full evidence-based audit across frontend, gateway/API, ML services, pipeline, database, Docker, and security.
- Editing rule: no product code fix before reproduction evidence and root-cause notes exist.

## Current Phase
Security runtime probing after completed gateway API runtime audit.

## Active Task
Commit API runtime evidence, then verify high-risk security controls at runtime.

## Next Exact Action
Stage and commit API runtime evidence docs/artifacts. Then run security runtime probes for admin/model-health, gateway `/pipeline/run`, pipeline internal-token enforcement, JWT fail-fast, production CORS, and scraper SSRF protections.

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

## Baseline Summary
- Backend: import/compile passed; full pytest passed with `389 passed, 3 warnings`.
- Frontend: `npm run lint` passed with 16 warnings; `npm run build` passed and generated 12 static pages.
- Database: Alembic head is `012_ab_testing_and_monitoring`; running Docker PostgreSQL drifted to `011_job_alerts` during API probing and was reconciled to 012 with the existing migration DDL.
- Docker: initial rebuild failed, then `b747954` repaired gateway/pipeline packaging and `f77445b` recorded the checkpoint. Full `docker compose up -d --build` passed.
- API: gateway runtime probe harness passed 83/83 after `6366b67` fixed invalid application job IDs, unknown feedback slate IDs, and ISO `posted_at` job upsert.
