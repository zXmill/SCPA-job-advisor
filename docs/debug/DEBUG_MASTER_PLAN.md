# Ultimate Debugging Master Plan

Updated: 2026-06-01 02:34 +07

## Session
- Task ID: DATA-QUALITY-PRODUCT-UI-001
- Branch: agent-run
- Active Phase: Real-data job description, skill taxonomy, skill-gap context, and product UI evidence/fix pass.

## Active Task
Investigate and remediate user-confirmed product-quality defects where job detail descriptions are too shallow, skill extraction/gap has too little context, skill autocomplete is too sparse, runtime paths still use sample jobs, and a global custom cursor ring looks like a stuck loader over controls.

## Next Exact Action
Commit the docs-only evidence update, then apply scoped product fixes in this order: custom cursor overlay, runtime sample fallback removal/purge path, rich job description storage/parser/API/frontend contract, real skill taxonomy baseline/search.

## Data Quality Evidence Status
- User supplied manual screenshots of shallow job detail, 0% skill gap with one generic required skill, sparse skill autocomplete, and blue ring overlay around theme/skill controls.
- Live API confirmed `/api/skills/search?q=s&limit=20` returns only `SQL` and `English`.
- Live API confirmed `/api/skills/search?q=machine&limit=20` and `q=data` return empty results.
- Live PostgreSQL confirmed `2645` jobs and `2614` shallow descriptions under 200 characters.
- Current code confirms runtime sample/fallback paths in scraper, pipeline stage 1, and full pipeline scripts.
- Current code confirms `custom-cursor-ring` with high z-index is rendered across product UI surfaces.

## Runtime Audit Status
- Complete in `f6c97cc`; retained here as prior phase context.
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
- Frontend fix commit: nested `frontend/` commit `7f746fe fix: harden runtime fetch cancellation contract`.
- Root CORS fix commit: `305391e fix: allow local production frontend CORS origin`.
- Final audit evidence: `reports/debug/runtime_contract/summary.json` generated 2026-05-31T14:37:33Z.
- Final audit result: 14 scenarios, 0 failed checks, 75 canceled request events, 0 severe console entries.
- Dev and production-mode frontend scenarios passed for jobs, recommendations, targeted cancellation, auth/session, theme toggle, and gateway restart.
- Theme product fix was not made because final runtime evidence did not reproduce a stuck spinner or persistence defect.

## Guardrails
- Do not use or generate sample job data for runtime job catalog fixes.
- Do not scrape LinkedIn or any other site in a way that violates terms, robots restrictions, or the existing scraper allowlist/SSRF contract.
- If real source access is blocked, return controlled empty/degraded results and document the blocker instead of fabricating jobs.
- Keep sample datasets only for explicit test/evaluation paths unless the user later asks to remove all test fixtures too.
- Do not start ML training or model redesign.
- Do not start broad unrelated frontend redesign.
- Do not fix P2 suggestions unless needed for these confirmed P0/P1 data quality defects.
- Do not commit unrelated dirty files.
- Keep commits scoped by finding.
- No `git add .`.

## Previous Work
- FIX-API-FEEDBACK-SLATE, FIX-DOCKER-RUNTIME-BUILD, FIX-API-RUNTIME-GUARDS are all committed (342edb0, b747954, 6366b67).
- API runtime probe passed 83/83 with 0 HTTP 5xx after gateway rebuild.
- Full backend suite passed 390 tests.
- Final Selenium audit passed 9 pages with 0 errors/blank/hydration failures.
- Code review remediation completed through `5598297`; deploy-safe migration validation passed.
