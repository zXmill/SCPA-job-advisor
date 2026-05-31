# Ultimate Debugging Master Plan

Updated: 2026-05-31 20:52 +07

## Session
- Task ID: RUNTIME-CONTRACT-DEBUG-001
- Branch: agent-run
- Active Phase: Bounded Full-Stack Runtime Contract Debugging Pass.

## Active Task
Investigate systemic runtime fetch, timeout, cancellation, auth/session, gateway contract, and UI state consistency defects from browser/runtime evidence.

## Next Exact Action
Build `scripts/debug/runtime_contract_audit.py` and run baseline Selenium evidence in both dev frontend mode (`localhost:3000`) and production frontend mode (`localhost:3001`) before changing product code.

## Guardrails
- Do not start broad award-style frontend redesign during this bounded runtime pass.
- Do not fix P2 suggestions (performance, duplication, dead code) unless they are a prerequisite for a confirmed runtime-contract fix.
- Do not commit unrelated dirty files.
- Keep commits scoped by finding.
- No `git add .`.
- Do not start ML training, scraper redesign, taxonomy work, job-description enrichment, or unrelated feature work.

## Previous Work
- FIX-API-FEEDBACK-SLATE, FIX-DOCKER-RUNTIME-BUILD, FIX-API-RUNTIME-GUARDS are all committed (342edb0, b747954, 6366b67).
- API runtime probe passed 83/83 with 0 HTTP 5xx after gateway rebuild.
- Full backend suite passed 390 tests.
- Final Selenium audit passed 9 pages with 0 errors/blank/hydration failures.
- Code review remediation completed through `5598297`; deploy-safe migration validation passed.
