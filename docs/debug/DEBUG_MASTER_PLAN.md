# Ultimate Debugging Master Plan

Updated: 2026-06-01 19:28 +07

## Session
- Task ID: CONTINUOUS-SCRAPE-001
- Branch: agent-run
- Active Phase: Continuous realtime scraping worker complete; docs/evidence state update.

## Active Task
Convert the finite realtime scrape/refresh path into an operator-safe continuous scraping system while preserving strict real-data quality gates, PostgreSQL as app source of truth, and bounded local harness validation.

## Next Exact Action
Commit the scoped debug/agent state update, then stop. Do not start source expansion, LinkedIn scraping, skill taxonomy expansion, ML training, or frontend redesign.

## Data Quality Evidence Status
- User supplied manual screenshots of shallow job detail, 0% skill gap with one generic required skill, sparse skill autocomplete, and blue ring overlay around theme/skill controls.
- Live API confirmed `/api/skills/search?q=s&limit=20` returns only `SQL` and `English`.
- Live API confirmed `/api/skills/search?q=machine&limit=20` and `q=data` return empty results.
- Live PostgreSQL confirmed `2645` jobs and `2614` shallow descriptions under 200 characters.
- Current code confirms runtime sample/fallback paths in scraper, pipeline stage 1, and full pipeline scripts.
- Current code confirms `custom-cursor-ring` with high z-index is rendered across product UI surfaces.

## Product Quality Final Status
- Root audit harness commit: `7286d84 test: add product quality selenium audit`.
- Root product/data commit: `fccb8a4 feat: require real job data with rich descriptions and skill taxonomy`.
- Nested frontend commit: `999e2a8 fix: stabilize product UI for rich jobs and skills`.
- Product-quality audit artifacts: `reports/debug/product_quality/`.
- Final audit result: 5 sections, 48 checks, 48 passed, 0 failed.
- Runtime database state after purge/rescrape: 10 jobs, 10 rich descriptions, 10 jobs with extracted skills, 10 non-sample source jobs, 8888 skills, Alembic `014_rich_job_desc_skill_sources`.
- Remaining limitation: the current real-source scrape is intentionally bounded to 10 jobs because larger live scrape batches can be slow or unstable. The runtime now returns real data only and does not fabricate sample jobs when real sources fail.

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

## Continuous Scraping Phase
- Task ID: CONTINUOUS-SCRAPE-001.
- Active status: complete in root commit `f26b208`.
- Architecture: `/scrape/run` and `/pipeline/run refresh_jobs=true` remain finite one-shot paths; new `scraper-worker` profile service runs `services.pipeline.continuous_scraper` as a separate continuous process.
- App source of truth remains PostgreSQL `jobs`; app API `/api/jobs` reads from DB.
- No LinkedIn production scraping was added. Current allowed production source is Kalibrr.
- Final runtime evidence: bounded 1-cycle and 2-cycle Docker harness runs passed, final DB/API guard reports 8 Kalibrr jobs, 8 distinct source URLs, 0 sample jobs, 0 under-300 descriptions, 0 missing skill-signal jobs, and API total matches DB total.
- Next exact action: commit this debug/agent state update, then stop unless a separate source-reliability or broader scraper-source expansion phase is requested.
