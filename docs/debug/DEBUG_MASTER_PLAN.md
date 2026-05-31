# Ultimate Debugging Master Plan

Updated: 2026-05-31 21:09 +07

## Session
- Task ID: RUNTIME-CONTRACT-DEBUG-001
- Branch: agent-run
- Active Phase: Bounded Full-Stack Runtime Contract Debugging Pass.

## Active Task
Investigate systemic runtime fetch, timeout, cancellation, auth/session, gateway contract, and UI state consistency defects from browser/runtime evidence.

## Next Exact Action
Harden `scripts/debug/runtime_contract_audit.py` login/redaction behavior, add targeted cancellation scenarios, and rerun Selenium evidence in both dev frontend mode (`localhost:3000`) and production frontend mode (`localhost:3001`) before changing product code.

## Runtime Audit Status
- Harness commit: `0bb7c54 test: add runtime contract browser audit`.
- Bootstrap fix commit: `745ac6f test: fix runtime audit storage bootstrap`.
- First artifact set: `reports/debug/runtime_contract/`.
- First dev-mode evidence: jobs, recommendations, and gateway restart checks passed; auth/session and theme checks failed.
- First production-mode evidence: blocked at login automation, so production-mode scenarios are not yet valid evidence.
- Product-code changes remain blocked until targeted cancellation and production-mode evidence are collected.

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
