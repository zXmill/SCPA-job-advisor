# Ultimate Debugging Master Plan

Updated: 2026-05-31 21:20 +07

## Session
- Task ID: RUNTIME-CONTRACT-DEBUG-001
- Branch: agent-run
- Active Phase: Bounded Full-Stack Runtime Contract Debugging Pass.

## Active Task
Investigate systemic runtime fetch, timeout, cancellation, auth/session, gateway contract, and UI state consistency defects from browser/runtime evidence.

## Next Exact Action
Apply minimal product fixes for confirmed runtime defects: stale canceled jobs/recommendations requests must not set final timeout UI, dashboard should avoid redundant `/api/auth/me`, and gateway CORS dev defaults must allow the local production frontend origin at `http://localhost:3001`.

## Runtime Audit Status
- Harness commit: `0bb7c54 test: add runtime contract browser audit`.
- Bootstrap fix commit: `745ac6f test: fix runtime audit storage bootstrap`.
- Harness hardening commit: `812da0c test: harden runtime contract browser audit`.
- First artifact set: `reports/debug/runtime_contract/`.
- First dev-mode evidence: jobs, recommendations, and gateway restart checks passed; auth/session and theme checks failed.
- First production-mode evidence: blocked at login automation, so production-mode scenarios are not yet valid evidence.
- Second dev-mode evidence reproduced canceled-request false timeout:
  - `/api/recommendations` canceled with final recommendation timeout UI.
  - Two canceled jobs filter requests were followed by a successful jobs response, but final UI still showed jobs timeout and retry.
- Second dev-mode theme evidence passed after harness hardening, so no theme product fix is currently justified.
- Production-mode evidence now reaches `/api/auth/login` but is blocked by CORS because `http://localhost:3001` is not allowed by the gateway dev CORS defaults.
- Product-code changes are now allowed for the confirmed stale cancellation and local production-origin CORS defects.

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
