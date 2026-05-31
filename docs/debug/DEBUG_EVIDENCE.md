# Debug Evidence

Updated: 2026-06-01 02:34 +07

## Bootstrap Evidence
- Repository cwd: `E:\TUGAS AKHIR\SCPA`.
- Branch: `agent-run`.
- Start commit: `79b1614`.
- Initial worktree: dirty before this session with modified `README.md`, modified `SCPAv2`, modified notebooks, many untracked project files, and a dirty nested `frontend/` repository.
- Existing debug doc found: `docs/debug/BROWSER_E2E_ARCHITECTURE_REVIEW.md`.
- `morph-mcp`: requested by prompt, but no callable morph tool was exposed by current tool discovery; normal local edit tooling is used.

## Evidence Index
- Browser artifacts: final authenticated Selenium audit saved under `reports/debug/browser/`.
- API artifacts: gateway runtime probe artifacts under `reports/debug/api/`; final fixed run is `gateway_runtime_probe_20260531T081953Z.json` plus matching `.log`.
- Model artifacts: pending.
- Database artifacts: live Alembic current/upgrade/current validation recorded.
- Docker artifacts: compose build/up, service health, and browser re-check recorded.
- Security artifacts: pending.

## Baseline Evidence
- `pytest --collect-only -q`: pass, 389 tests collected in 8.64s.
- `alembic heads`: pass, head `012_ab_testing_and_monitoring`.
- `docker compose config --services`: pass, services `postgres`, `sbert`, `scraper`, `dqn`, `ncf`, `pipeline`, `gateway`.
- `docker compose config --quiet`: pass with dummy required env vars.
- `python scripts/verify_project.py --only import compile`: pass for selected service/script imports and compileall.
- `python -m pytest -q`: pass, 389 passed, 3 warnings in 205.51s.
- `npm run lint` in `frontend/`: pass, 0 errors, 16 warnings.
- `npm run build` in `frontend/`: pass, Next.js 16.2.6 built 12 static pages plus dynamic `/jobs/[id]`.
- `docker compose up -d --build`: fail while rebuilding gateway. Evidence: gateway build transferred about 5.06GB of context, then pip failed with `Could not open requirements file: requirements-db.txt`.
- Existing runtime probe: `http://127.0.0.1:9000/health` returned gateway healthy; `http://127.0.0.1:8000/health` refused connection; `http://127.0.0.1:3000` returned 200 from an existing Next dev server started from this checkout.
- Existing runtime probe: `http://127.0.0.1:9000/ready` returned gateway ready and pipeline healthy, but these containers predate the failed rebuild and are not proof that the current Docker build works.

## Browser Evidence
- `scripts/debug/selenium_full_audit.py` compiled and ran.
- Initial `127.0.0.1:3000` dev audit produced HMR WebSocket false positives and blank screenshots; canonical origin was changed to `localhost`.
- Production cross-check on `127.0.0.1:3001` showed 0 console errors, 0 network failures, 0 blank pages, but login failed due origin/API mismatch.
- Canonical authenticated audit on `http://localhost:3000` with `http://localhost:9000` succeeded for login and loaded all 9 routes with no blank pages or hydration errors.
- Canonical authenticated audit reproduced one product failure: `POST /api/recommendations/feedback` returned HTTP 500 from `/recommendations`.
- Gateway logs for that failure show `asyncpg.exceptions.ForeignKeyViolationError` on `feedback_events_slate_id_fkey`: the slate ID sent by the frontend is not present in `served_slates`.

## Feedback Slate Evidence
- Focused pre-fix regression: `tests\test_recommendation_feedback_slate.py` failed because `served_slates` count was 0 immediately after `/api/recommendations`.
- Root cause confirmed in current source: the gateway returned a generated slate ID but did not write `served_slates`/`served_slate_items`.
- Current-source fix validation:
  - `py_compile` passed for `services\gateway\main.py`, `tests\conftest.py`, and `tests\test_recommendation_feedback_slate.py`.
  - Focused regression passed.
  - Adjacent recommendation/pipeline suite passed with 6 tests.
  - Full backend suite passed with 390 tests.
- Browser re-verification later passed after Docker/runtime repair; the final route-level Selenium audit reported 0 network failures.

## Docker And Runtime Evidence
- `docker compose build gateway`: pass. Gateway context dropped from prior 5.06GB failure to 286.56KB; image built successfully.
- `docker run --rm ... scpa-gateway python -c "import services.gateway.main as gateway; print(gateway.app.title)"`: pass, printed `SCPA Gateway`.
- First `docker compose up -d --build gateway` after gateway repair built images but failed because `scpa-pipeline-1` was unhealthy.
- Pipeline logs showed `ModuleNotFoundError: No module named 'services'` from `stage_5_aggregate.py`.
- After pipeline Dockerfile/package-entrypoint repair, `docker compose up -d --build` passed and all services were healthy.
- Gateway health and readiness probes passed on port 9000.

## Database Migration Evidence
- `alembic current` before upgrade: `001_initial_schema`.
- `alembic upgrade head`: pass, applied migrations through `012_ab_testing_and_monitoring`.
- `alembic current` after upgrade: `012_ab_testing_and_monitoring (head)`.
- API-phase reconciliation found the running Docker PostgreSQL container still at `011_job_alerts` with no `experiments` tables. The existing `012_ab_testing_and_monitoring` DDL was applied through `docker compose exec -T postgres psql` because the gateway image intentionally lacks Alembic and Postgres is not host-exposed.
- Post-repair Docker DB checks returned `012_ab_testing_and_monitoring`, `experiments`, `experiment_assignments`, and `experiment_metrics`.

## Final Browser Evidence
- Final authenticated Selenium audit against the rebuilt Docker runtime: 9 pages, 0 console errors, 0 network failures, 0 blank pages, 0 hydration errors.
- Report artifact secret scan found no password, bearer token, authorization header, JWT-like token, or access-token strings.

## API Runtime Probe Evidence
- `scripts/debug/api_runtime_probe.py` compiled and ran against `http://127.0.0.1:9000`.
- Pre-fix corrected probe after Docker DB 012 repair: `reports/debug/api/gateway_runtime_probe_20260531T080750Z.json`, 83 total, 81 passed, 2 failed, HTTP 5xx cases `APPLICATIONS-CREATE-MISSING-JOB` and `FEEDBACK-MISSING-SLATE`.
- Pre-fix gateway logs confirmed:
  - `applications_job_id_fkey` for invalid application job IDs.
  - `feedback_events_slate_id_fkey` for unknown served-slate IDs.
  - asyncpg `DataError` when recommendation job upsert received ISO string `posted_at`.
- Post-fix local validation passed:
  - Focused red-to-green: `tests\test_gateway_api_runtime_guards.py tests\test_recommendation_feedback_slate.py::test_feedback_with_unknown_served_slate_returns_404 -q` -> 3 passed.
  - Adjacent suite: `tests\test_gateway_api_runtime_guards.py tests\test_recommendation_feedback_slate.py tests\test_feedback_outbox.py tests\test_saved_jobs_skip.py -q` -> 10 passed.
- Post-fix Docker validation:
  - `docker compose up -d --build gateway` passed and rebuilt the gateway plus dependent service images.
  - `docker compose ps` showed all services healthy.
  - Gateway `/health` returned healthy.
  - Final API probe `reports/debug/api/gateway_runtime_probe_20260531T081953Z.json` passed 83/83 with 0 HTTP 5xx.
  - Final API artifact secret scan found no password, bearer token, authorization header, JWT-like token, or access-token strings.

## Product-Quality Recovery Evidence
- `git log --oneline -20` shows latest commit `d511e1c docs: record api runtime probe evidence`.
- `git status --short --branch` confirms branch `agent-run` remains dirty with pre-existing modified/untracked files; no unrelated dirty work was staged during reconciliation.
- Required debug reports were re-read on 2026-05-31 16:26 +07. Stale debug state was found in `COMPACT_RECOVERY.md`, `DEBUG_MASTER_PLAN.md`, `DEBUG_BROWSER_REPORT.md`, `DEBUG_FRONTEND_REPORT.md`, and this evidence file.
- `impeccable` setup was invoked for the frontend phase. The project-local helper path was absent, and the installed skill helper reported `NO_PRODUCT_MD`; frontend design/product work therefore needs a minimal `PRODUCT.md` context before UI changes.

## Code Review Remediation Recovery Evidence
- `git log --oneline -8` on 2026-05-31 20:29 +07 shows latest commit `5963523 docs: mark DEBUG-ULT-001 and remediation complete in task queue`.
- `git status --short --branch` confirms branch `agent-run` remains dirty with pre-existing unrelated changes and untracked files. These are not staged for this remediation pass.
- Focused remediation tests passed: `.\.venv\Scripts\python.exe -m pytest tests/test_security.py tests/test_saved_jobs_skip.py tests/test_market_aware_skill_path.py -q` -> 32 passed, 1 warning.
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini heads` passed with `013_hot_indexes_concurrent (head)`.
- `docker compose config --quiet && docker compose config --services` passed.
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini current` reported current database revision `012_ab_testing_and_monitoring`.
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head` failed while running `013_hot_indexes_concurrent`.
- Failure root evidence: `sqlalchemy.exc.InvalidRequestError: This connection has already initialized a SQLAlchemy Transaction() object via begin() or autobegin; isolation_level may not be altered unless rollback() or commit() is called first.`

## Code Review Remediation Final Evidence
- Product fix commit: `6f49402 db: make recommendation hot indexes deploy safe`.
- `db/migrations/009_reco_hot_indexes.py` now creates and drops the hot jobs/application indexes with `CREATE/DROP INDEX CONCURRENTLY` inside Alembic `autocommit_block()`.
- `db/migrations/013_hot_indexes_concurrent.py` now uses `autocommit_block()` and acts as an idempotent repair migration for databases that reached `012` before the 009 change.
- `.\.venv\Scripts\python.exe -m py_compile db\migrations\009_reco_hot_indexes.py db\migrations\013_hot_indexes_concurrent.py` passed.
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head` passed after the fix.
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini downgrade 012_ab_testing_and_monitoring` passed.
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head` passed after the downgrade smoke.
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini current` reported `013_hot_indexes_concurrent (head)`.
- `.\.venv\Scripts\python.exe -m pytest tests/test_security.py tests/test_saved_jobs_skip.py tests/test_market_aware_skill_path.py -q` passed with 32 tests and 1 warning.
- `docker compose config --quiet` passed.

## Runtime Contract Debug Recovery Evidence
- `git log --oneline -25` on 2026-05-31 20:52 +07 showed latest commit `5598297 docs: record code review remediation evidence` before the runtime-contract phase began.
- Follow-up recovery on 2026-05-31 21:09 +07 shows latest committed runtime checkpoint `745ac6f test: fix runtime audit storage bootstrap`.
- `git status --short --branch` confirms branch `agent-run` remains dirty with pre-existing unrelated modified/untracked files, including root docs/notebooks and a dirty nested `frontend/` repository.
- Required debug reports were read before product-code changes: compact recovery, master plan, browser, frontend, API, evidence, validation ledger, fix log, hypotheses, security, and model reports.
- `impeccable` product context was loaded from `PRODUCT.md`; register is `product`. The matching product reference was read.
- Existing frontend conventions inspected: `frontend/src/app/globals.css`, `frontend/src/lib/api.ts`, `frontend/src/lib/auth-context.tsx`, `frontend/src/lib/theme-context.tsx`, and `frontend/src/components/shared/Navbar.tsx`.
- Manual runtime symptoms were recorded in `docs/debug/RUNTIME_CONTRACT_FINDINGS.md`.

## Runtime Contract Audit Evidence
- Harness commit: `0bb7c54 test: add runtime contract browser audit`.
- Harness bootstrap fix commit: `745ac6f test: fix runtime audit storage bootstrap`.
- `.\.venv\Scripts\python.exe -m py_compile scripts\debug\runtime_contract_audit.py` passed on 2026-05-31 21:09 +07.
- First audit artifacts: `reports/debug/runtime_contract/runtime_contract_report.md`, `summary.json`, `network.ndjson`, `console.ndjson`, `gateway_logs.ndjson`, screenshots, and DOM snapshots.
- First audit result: failed overall with 2 failed dev checks and production-mode login blocked.
- Dev jobs evidence: `/analytics` rendered 25 job links after successful jobs response and did not show timeout text.
- Dev recommendations evidence: `/recommendations` rendered recommendation cards after successful response and did not show timeout text.
- Dev auth/session evidence: fast navigation produced 6 `/api/auth/me` calls across 4 routes; final UI had no persistent timeout text.
- Dev theme evidence: repeated toggle produced no stuck spinner or hydration warning, but `localStorage.scpa_theme` remained null after reload.
- Dev gateway restart evidence: `docker compose restart gateway` returned success; gateway recovered healthy and jobs page retained no timeout state.
- Production-mode evidence: blocked because login automation did not submit successfully; production-mode runtime contract remains unverified.
- First audit captured 0 canceled request events, so user-observed canceled fetches still require targeted reproduction.

## Runtime Contract Reproduction Evidence
- Harness hardening commit: `812da0c test: harden runtime contract browser audit`.
- Second audit command: `.\.venv\Scripts\python.exe scripts\debug\runtime_contract_audit.py --mode both --dev-url http://localhost:3000 --prod-url http://localhost:3001 --api-base http://localhost:9000 --email <demo-email> --password <redacted> --restart-gateway --exercise-actions --settle-seconds 3`.
- Second audit result: failed overall with 4 failed checks, 3 canceled request events, and 2 production CORS console errors.
- Secret scan: `rg -n "password123|access_token|refresh_token|Authorization|Bearer |eyJ...|budi@example.com" reports/debug/runtime_contract scripts/debug/runtime_contract_audit.py` returned no matches.
- Dev recommendations reproduction: network trace shows `/api/recommendations` loading failed with `net::ERR_ABORTED`; final DOM contained `Pencocokan AI memakan waktu terlalu lama. Coba lagi sebentar.` and `Coba Lagi`.
- Dev jobs reproduction: targeted filter run captured canceled `GET /api/jobs?experience=entry&page=1&limit=25` and `GET /api/jobs?experience=mid&page=1&limit=25`, then successful `GET /api/jobs?experience=senior&page=1&limit=25` status 200. Final DOM still contained `Permintaan kehabisan waktu. Coba lagi.` and `Coba Lagi`.
- Dev auth/session evidence: 6 `/api/auth/me` requests across 4 full navigations; final UI did not retain timeout text.
- Dev theme evidence: repeated toggle passed after harness hardening; after clicks and reload, `data-theme=dark`, `colorScheme=dark`, and `localStorage.scpa_theme=dark`.
- Dev gateway restart evidence: passed after second run.
- Production-mode evidence: login reached `/api/auth/login`, but CORS preflight returned without `Access-Control-Allow-Origin` for origin `http://localhost:3001`; Chrome blocked the request.

## Runtime Contract Final Evidence
- Frontend tracked product commit: nested `frontend/` commit `7f746fe fix: harden runtime fetch cancellation contract`.
- Root product commit: `305391e fix: allow local production frontend CORS origin`.
- Focused syntax/test validation:
  - `git -C frontend diff --check -- src/lib/api.ts src/app/analytics/page.tsx src/app/recommendations/page.tsx` passed before frontend commit.
  - `.\.venv\Scripts\python.exe -m py_compile services\gateway\main.py tests\test_cors_config.py` passed.
  - `.\.venv\Scripts\python.exe -m pytest tests\test_cors_config.py -q` passed: 4 passed, 1 warning.
  - `npm run lint` in `frontend/` passed with 0 errors and the existing 16 warnings.
  - `npm run build` in `frontend/` passed.
  - `docker compose config --quiet` passed.
- Runtime validation:
  - Gateway was rebuilt/restarted with development CORS allowing `http://localhost:3001`.
  - Production-mode Next server was restarted on `http://localhost:3001`.
  - Final audit command: `.\.venv\Scripts\python.exe scripts\debug\runtime_contract_audit.py --mode both --dev-url http://localhost:3000 --prod-url http://localhost:3001 --api-base http://localhost:9000 --email <demo-email> --password <redacted> --restart-gateway --exercise-actions --settle-seconds 3`.
  - Final audit result: 14 scenarios, 0 failed checks, 75 canceled request events, 0 severe console entries.
  - Dev and prod jobs checks passed with no timeout UI after successful jobs responses.
  - Dev targeted jobs cancellation captured canceled requests and still ended with no timeout/retry UI after current success.
  - Dev and prod recommendations checks passed with recommendation cards rendered and no timeout UI.
  - Prod recommendations captured canceled events without final timeout UI.
  - Auth/session checks passed in dev and prod with 5 `/api/auth/me` requests across 4 navigated routes and no persistent timeout state.
  - Theme toggle checks passed in dev and prod: no spinner/loading indicator, persisted `scpa_theme=dark`, and no hydration warning.
  - Gateway restart checks passed in dev and prod; gateway became healthy and the jobs page retained no permanent timeout state.
- Final artifact paths: `reports/debug/runtime_contract/runtime_contract_report.md`, `summary.json`, `network.ndjson`, `console.ndjson`, `gateway_logs.ndjson`, `screenshots/`, and `dom_snapshots/`.
- Final secret scan over `reports/debug/runtime_contract` and `scripts/debug/runtime_contract_audit.py` found no demo password, demo email, token value, bearer header, refresh token, or JWT-like value.

## Data Quality Product UI Recovery Evidence
- `git log --oneline -25` on 2026-06-01 02:34 +07 shows latest root commit `f6c97cc docs: record runtime contract debugging evidence`.
- `git status --short --branch` confirms branch `agent-run` remains dirty with pre-existing unrelated modified/untracked files. These must not be staged.
- `git -C frontend log --oneline -10` shows latest nested frontend commit `7f746fe fix: harden runtime fetch cancellation contract`.
- `git -C frontend status --short --branch` confirms nested frontend still has pre-existing dirty/untracked files.
- `impeccable` product context was loaded from `PRODUCT.md` and `reference/product.md` was read for product UI quality rules.
- User screenshots show a blue ring overlapping theme toggle and skill input. Current code confirms `frontend/src/components/AppLayout.tsx` renders `custom-cursor-dot` and `custom-cursor-ring`, and `frontend/src/app/globals.css` gives the ring fixed positioning and `z-index: 9998`.
- Live Docker runtime is up: `docker compose ps` shows postgres, gateway, scraper, sbert, ncf, dqn, and pipeline healthy.
- Live skill search evidence:
  - `GET http://localhost:9000/api/skills/search?q=s&limit=20` returned only `SQL` and `English`.
  - `GET http://localhost:9000/api/skills/search?q=machine&limit=20` returned `[]`.
  - `GET http://localhost:9000/api/skills/search?q=data&limit=20` returned `[]`.
  - PostgreSQL `skills` count is `3`, with rows `English`, `Python`, and `SQL`.
- Live job data evidence:
  - `GET http://localhost:9000/api/jobs?page=1&limit=5` returned short sample-like descriptions and sample-like company rows.
  - PostgreSQL jobs summary: `total_jobs=2645`, `missing_source_url=12`, `shallow_desc=2614`, and `distinct_fingerprints=2645`.
  - Example rows include short descriptions around 130 to 181 characters and `match_data.skills` arrays with no structured required/preferred skill fields.
- Static code evidence:
  - `services/scraper/main.py::scrape_run` returns `sample()` when no seed URLs are configured or when no unique jobs are found.
  - `services/pipeline/stages/stage_1_scrape.py` returns `FALLBACK_JOBS` on failure and when scraper jobs are empty.
  - `scripts/run_full_pipeline.py` imports and merges `scripts.sample_dataset` into pipeline jobs and calls scraper `/sample`.
  - `services/pipeline/pipeline/extractors/skills.py` contains a small hand list plus fake generated `Skill 001` to `Skill 429`.
  - `services/gateway/main.py::_job_skill_gap` builds required skills only from `match_data.skills`.

## Product Quality Data/UI Final Evidence
- Root audit harness commit: `7286d84 test: add product quality selenium audit`.
- Root product/data commit: `fccb8a4 feat: require real job data with rich descriptions and skill taxonomy`.
- Nested frontend commit: `999e2a8 fix: stabilize product UI for rich jobs and skills`.
- Runtime DB state after purge/rescrape:
  - `jobs=10`
  - `rich_jobs=10`
  - `jobs_with_extracted_skills=10`
  - `real_source_jobs=10`
  - `skills=8888`
  - `alembic_version=014_rich_job_desc_skill_sources`
- API evidence:
  - `/api/skills/search?q=s&limit=10` returns SQL, Statistics, and additional O*NET-backed suggestions.
  - `/api/skills/search?q=machine&limit=5` returns Machine Learning plus related machine-control tool entries.
  - `/api/skills/search?q=data&limit=5` returns Data Analysis, Data Engineering, Data Science, and related entries.
  - `/api/jobs?page=1&limit=2` returns real Kalibrr-source rows with `description_text`, `description_sections`, required skills, and extracted skills.
- Browser/product audit evidence:
  - Harness: `scripts/debug/selenium_product_quality_audit.py`.
  - Artifacts: `reports/debug/product_quality/product_quality_report.md`, `summary.json`, `console.ndjson`, `network.ndjson`, `screenshots/`, and `dom_snapshots/`.
  - Final result: 5 sections, 48 checks, 48 passed, 0 failed.
  - Job vacancies: 10 real job cards rendered; no false timeout/retry UI.
  - Recommendations: cards rendered; no false timeout/retry UI after successful data and save/skip actions.
  - Theme toggle: repeated toggle/reload checks passed; no stuck spinner or hydration warning.
  - Skills autocomplete: taxonomy suggestions rendered and duplicate selection was blocked.
  - Job detail quality: five real detail pages opened; descriptions ranged from 523 to 2655 characters and structured skill fields were present.
- Validation evidence:
  - Focused backend/data tests passed: 9 passed, 1 warning.
  - Changed Python modules compile.
  - `docker compose config --quiet` passed.
  - Frontend `npm run lint` passed with existing warnings only.
  - Frontend `npm run build` passed.
  - Secret scan over product-quality artifacts and harness found no auth/token/secret material.
- Limitation:
  - The current real-source scrape is intentionally bounded to 10 jobs. Larger live scrape batches remain a separate reliability concern because external job-board access can be slow or unstable. The fixed runtime path does not fabricate sample jobs when real sources are unavailable.
