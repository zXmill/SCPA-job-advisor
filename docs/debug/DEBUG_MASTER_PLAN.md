# Ultimate Debugging Master Plan

Updated: 2026-05-31 09:12 +07

## Session
- Task ID: DEBUG-ULT-001
- Branch: agent-run
- Start commit: 79b1614
- Scope: full evidence-based audit across frontend, gateway/API, ML services, pipeline, database, Docker, and security.
- Editing rule: no product code fix before reproduction evidence and root-cause notes exist.

## Current Phase
Hypothesis generation after static inventory and baseline validation.

## Active Task
Document baseline evidence, generate subsystem hypotheses, then add the Selenium/Chrome browser audit harness.

## Next Exact Action
Commit static inventory, baseline validation, and initial hypotheses. Then create `scripts/debug/selenium_full_audit.py`.

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
- Database: Alembic head is `012_ab_testing_and_monitoring`; live migration upgrade still needs a current-image database run.
- Docker: `docker compose config` passed, but `docker compose up -d --build` failed while rebuilding gateway because `requirements-db.txt` is not present inside the gateway image build context.
