# Debug Hypotheses

Updated: 2026-06-01 02:34 +07

Status: generated from static inventory and baseline validation, reconciled after served-slate/Docker fixes, and updated after gateway API runtime probing. Fixes are allowed only after the related reproduction evidence is recorded.

## Data Quality Product UI Hypotheses

### H-DATA-JOB-DESCRIPTION-SHALLOW
Hypothesis: scraper and pipeline runtime paths store listing-card summaries instead of detail-page descriptions, and the database/API contract cannot preserve structured job sections.

Expected: real scraped jobs keep source URL, full `description_text`, parsed sections, responsibilities, requirements, nice-to-have, seniority, employment type, job function, industry, and extracted skills when source detail is legally and technically available.

Actual: confirmed. Live DB has `2614` shallow descriptions under 200 characters out of `2645` jobs. Current schema has no rich job-description columns. Gateway job detail returns only `description` plus legacy `match_data.skills`.

Test: add parser/storage/API tests and run a real-data scrape path that refuses sample fallback.

Evidence location: `docs/debug/DATA_QUALITY_FINDINGS.md`.

### H-DATA-SAMPLE-JOBS-IN-RUNTIME
Hypothesis: production/runtime scraper and pipeline paths silently use local sample/fallback jobs when real scraping is unavailable.

Expected: runtime returns controlled empty/degraded results unless real configured sources return jobs; sample data is restricted to explicit test/evaluation flows.

Actual: confirmed in current code. `scrape_run` calls `sample()`, pipeline stage 1 returns `FALLBACK_JOBS`, and full pipeline merges `data/sample` jobs.

Test: focused tests should verify no configured source yields empty/degraded output, not fake jobs, while explicit test-only fixture paths remain available for tests.

Evidence location: `docs/debug/DATA_QUALITY_FINDINGS.md`.

### H-DATA-SKILL-TAXONOMY-SPARSE
Hypothesis: skill autocomplete is sparse because the runtime `skills` table is tiny and the production extractor uses a fake generated taxonomy instead of an authorized real taxonomy.

Expected: common skill queries return several real-world suggestions with aliases, category, source, and confidence metadata.

Actual: confirmed. Live `skills` table contains only three rows and API queries for `machine` and `data` return empty results. Current extractor contains fake generated `Skill 001` entries.

Test: taxonomy builder/search tests for `s`, `machine`, `data`, `docker`, `kubernetes`, `english`, `credit`, `airflow`, `terraform`, `komunikasi`, and `analisis`.

Evidence location: `docs/debug/DATA_QUALITY_FINDINGS.md`.

### H-DATA-SKILL-GAP-LOW-CONTEXT
Hypothesis: skill gap is inaccurate because it reads only `match_data.skills` from shallow scraped text instead of rich required/preferred/extracted skill fields.

Expected: skill gap prioritizes required skills from parsed sections, then preferred/extracted skills, and uses legacy `match_data.skills` only as a fallback.

Actual: confirmed statically. `_job_skill_gap` selects `match_data` only; user screenshot shows a one-skill gap for a Data Scientist role.

Test: focused skill-gap test with a rich job row containing required/preferred/extracted skill fields.

Evidence location: `docs/debug/DATA_QUALITY_FINDINGS.md`.

### H-FE-CURSOR-RING-LOADER-CONFUSION
Hypothesis: the reported stuck theme/loading spinner is actually the global custom cursor ring overlay rendered above product controls.

Expected: product controls use normal cursor behavior and do not show decorative blue circular overlays.

Actual: strongly confirmed by screenshots and code. `custom-cursor-ring` is fixed, blue, high z-index, and expands over buttons/inputs.

Test: remove or disable the custom cursor on product app surfaces; use Selenium screenshots around theme toggle and skill input.

Evidence location: `docs/debug/DATA_QUALITY_FINDINGS.md`.

## Runtime Contract Hypotheses

### H-RUNTIME-ABORT-AS-TIMEOUT
Hypothesis: the frontend API client classifies browser `AbortError` as a 408 timeout, causing canceled stale requests to render user-facing timeout messages.

Expected: Abort/cancel is tracked separately from real timeout and cannot set final error state after a newer success.

Actual: confirmed. Current `frontend/src/lib/api.ts` maps `AbortError` to `ApiError(408, 'Permintaan kehabisan waktu...')`, and page code maps any `controller.signal.aborted` to timeout UI. Second runtime audit captured canceled jobs/recommendation requests and final false timeout UI.

Test: fix current-request guards and rerun Selenium runtime-contract audit with jobs/recommendations cancellation.

Evidence location: `reports/debug/runtime_contract/`.

### H-RUNTIME-AUTH-REMOUNT-STORM
Hypothesis: auth provider initialization or route navigation repeatedly calls `/api/auth/me`, causing dependent page requests to abort and occasionally show stale timeout UI.

Expected: authenticated state stabilizes with minimal `/api/auth/me` calls; dependent requests do not cascade into timeout UI.

Actual: confirmed in dev. Runtime audit counted 6 `/api/auth/me` requests across 4 full navigated routes. Dashboard and profile also call `api.getMe()` in page data fetches, adding avoidable duplication on top of auth-provider refresh.

Test: audit reload and fast navigation scenarios with request counts and final UI state.

Evidence location: `reports/debug/runtime_contract/`.

### H-RUNTIME-ENDPOINT-TIMEOUT-MISMATCH
Hypothesis: recommendation and learning-path routes can exceed frontend timeout expectations or gateway downstream timeout behavior, producing false timeout UI.

Expected: endpoint timeout policy matches gateway/model latency and returns controlled degraded state.

Actual: partially confirmed as frontend cancellation handling. Second dev audit showed `/api/recommendations` canceled after about 15 seconds and final timeout UI. Model/gateway latency may still influence how often the timeout path is reached, but stale/cancel handling is the confirmed UI defect.

Test: capture recommendation/learning-path request durations, gateway logs, and UI state in dev and production frontend modes.

Evidence location: `reports/debug/runtime_contract/`, `DEBUG_MODEL_REPORT.md` if model latency is implicated.

### H-RUNTIME-THEME-MOUNTED-GUARD
Hypothesis: theme mounted/persistence behavior leaves the toggle icon or loading indicator visually stuck after repeated clicks or reload.

Expected: icon and `localStorage.scpa_theme` agree after repeated toggles and reload with no hydration warning.

Actual: stale after harness hardening. Second dev audit observed no stuck spinner, persisted `localStorage.scpa_theme=dark`, and no hydration warning. No product fix is currently justified for the theme toggle.

Test: Selenium repeated-click scenario with screenshots and DOM/localStorage capture.

Evidence location: `reports/debug/runtime_contract/`.

## Frontend

### H1-FRONTEND-API-BASE
Hypothesis: local frontend runtime depends on `NEXT_PUBLIC_API_URL=http://localhost:9000`, while some docs and commands still reference gateway port 8000, causing browser/API failures when the wrong port is used.

Expected: browser requests use port 9000 or the app clearly documents how to run gateway on 8000.

Actual: `localhost:9000/health` responds; `localhost:8000/health` refuses connection.

Test: Selenium audit plus network-log capture for frontend API requests.

Evidence location: `reports/debug/browser/`, `DEBUG_BROWSER_REPORT.md`.

### H2-FRONTEND-RECOMMENDATION-HOOK-DEPS
Hypothesis: `frontend/src/app/recommendations/page.tsx` can use stale `eventContext` in effects because lint reports missing dependencies.

Expected: save/skip/feedback events use the current recommendation slate context.

Actual: lint warning only; runtime behavior unknown.

Test: browser interaction audit for recommendation save/skip/feedback and inspect request payloads.

Evidence location: `DEBUG_FRONTEND_REPORT.md`, browser network logs.

### H3-FRONTEND-AUTH-STATES
Hypothesis: protected pages may render incomplete states or failed API errors when no token is present.

Expected: controlled redirect or clear unauthenticated state on dashboard/profile/recommendations/analytics/apply.

Actual: unknown until browser route audit.

Test: visit protected routes without local storage token; capture screenshot, console, network failures, and visible text.

Evidence location: `DEBUG_BROWSER_REPORT.md`.

### H4-FRONTEND-BUILD-WARNINGS
Hypothesis: unused imports and raw `<img>` warnings do not block build but may hide dead UI paths or image performance issues.

Expected: warnings are either intentional or removed after runtime audit.

Actual: lint reports 16 warnings, build passes.

Test: inspect warned files and correlate with browser page coverage before cleanup.

Evidence location: `DEBUG_FRONTEND_REPORT.md`.

## Backend API

### H1-API-PIPELINE-RUN-PROTECTION
Hypothesis: gateway `/pipeline/run` must be admin-only and pipeline `/pipeline/run` must require the internal service token.

Expected: unauthenticated/public callers cannot trigger pipeline execution.

Actual: gateway runtime probe passed for unauthenticated, non-admin, and admin cases. Direct pipeline internal-token probing remains in the security phase.

Test: send unauthenticated, non-admin, admin, and internal-token requests where feasible.

Evidence location: `DEBUG_API_REPORT.md`, `DEBUG_SECURITY_REPORT.md`.

### H2-API-INVALID-INPUT-SHAPES
Hypothesis: at least one public API route returns 500 for malformed or empty input instead of controlled 4xx.

Expected: invalid input returns 400/401/403/404/422 with safe response shape.

Actual: confirmed and fixed in `6366b67`. Runtime probe found `POST /api/applications` with a nonexistent job ID and `POST /api/recommendations/feedback` with an unknown served-slate ID returned 500. Final rebuilt-runtime probe passed 83/83 with 0 HTTP 5xx.

Test: invalid/empty payload probes for auth, profile, uploads, jobs, recommendations, experiments, and events.

Evidence location: `DEBUG_API_REPORT.md`.

### H3-API-DOWNSTREAM-DEGRADATION
Hypothesis: gateway recommendation and learning-path routes may not degrade consistently when downstream pipeline/model services are slow or unavailable.

Expected: controlled error/degradation response without leaking stack traces.

Actual: current-service gateway recommendation and learning-path runtime probes passed. Server logs also exposed a nonfatal recommendation job upsert failure for ISO string `posted_at`; fixed in `6366b67`. Explicit downstream-unavailable simulation remains pending.

Test: run route smoke with current services, then simulate bad downstream URL in process-level tests if needed.

Evidence location: `DEBUG_API_REPORT.md`, `DEBUG_BACKEND_REPORT.md`.

### H4-API-FEEDBACK-SLATE-FK
Hypothesis: recommendation feedback fails because the gateway emits a frontend `recommendation_id`/served slate ID but does not persist the corresponding `served_slates` row before impression feedback is inserted.

Expected: recommendation response creates or references a persisted served slate, and feedback insert succeeds.

Actual: confirmed by Selenium and gateway logs; fixed in `342edb0`. Final Selenium audit after Docker/runtime repair showed no network failure from feedback.

Test: add a regression test that calls `/api/recommendations`, then posts impression feedback using the returned recommendation ID and asserts 200 plus persisted feedback.

Evidence location: `DEBUG_API_REPORT.md`, `DEBUG_BROWSER_REPORT.md`, `DEBUG_FIX_LOG.md`.

## Database

### H1-DB-MIGRATION-RUNTIME
Hypothesis: live migration execution is not currently proven because the gateway container lacks Alembic and the current gateway image cannot rebuild.

Expected: `alembic upgrade head` can be run in a documented current runtime path.

Actual: local `alembic heads` passed. Container-local Alembic is not part of the gateway runtime image; repo-local `.venv` Alembic was used against the running PostgreSQL container and succeeded.

Test: after Docker repair or explicit local DB config, run `alembic upgrade head` and `alembic current`.

Evidence location: `DEBUG_DATABASE_REPORT.md`, `DEBUG_VALIDATION_LEDGER.md`.

### H2-DB-SCHEMA-HEAD-DRIFT
Hypothesis: repository migrations are at head `012_ab_testing_and_monitoring`, but the live database may not be at that revision.

Expected: live DB current revision equals head.

Actual: confirmed again during API probing. Running Docker PostgreSQL reported `011_job_alerts` and lacked `experiments` tables; the existing 012 DDL was applied through `psql`, and the running DB now reports `012_ab_testing_and_monitoring` with experiment tables present.

Test: run Alembic current against the intended DB with known non-secret connection config.

Evidence location: `DEBUG_DATABASE_REPORT.md`, `DEBUG_VALIDATION_LEDGER.md`.

### H3-DB-HOT-PATH-INDEXES
Hypothesis: recommendation, feedback, skill taxonomy, and job alert hot paths require migration-backed indexes that may not exist in a live DB if migrations lag.

Expected: model metadata/tests and live schema both include required indexes.

Actual: model tests passed; live schema pending.

Test: inspect metadata and query live indexes after migration validation.

Evidence location: `DEBUG_DATABASE_REPORT.md`.

## Scraper

### H1-SCRAPER-SSRF-RUNTIME
Hypothesis: SSRF protections pass tests but still need runtime confirmation for redirects, private IPs, loopback, metadata IP, and disallowed domains.

Expected: unsafe URLs return controlled 4xx and approved job-board domains are allowed.

Actual: unit tests pass; runtime probe pending.

Test: call `/scrape/url` with approved and unsafe targets using no secrets.

Evidence location: `DEBUG_SECURITY_REPORT.md`, `DEBUG_API_REPORT.md`.

### H2-SCRAPER-EMPTY-SOURCE-DEGRADATION
Hypothesis: empty or blocked scraping sources should degrade to safe sample/fallback behavior without crashing pipeline.

Expected: controlled empty or fallback result with degradation flag.

Actual: tests pass; runtime probe pending.

Test: run scraper sample and forced-empty pipeline smoke.

Evidence location: `DEBUG_BACKEND_REPORT.md`.

### H3-SCRAPER-NORMALIZATION-OPTIONAL-FIELDS
Hypothesis: scraped jobs with missing logo, salary, skills, or location can still normalize safely.

Expected: optional fields default safely and do not break job upsert/recommendation stages.

Actual: tests pass; runtime sample pending.

Test: run normalization smoke and inspect output schema.

Evidence location: `DEBUG_BACKEND_REPORT.md`.

## Pipeline

### H1-PIPELINE-INTERNAL-AUTH
Hypothesis: pipeline state-changing endpoints require `INTERNAL_SERVICE_TOKEN`.

Expected: missing token is rejected; correct internal token is accepted.

Actual: automated tests pass; runtime probe pending.

Test: call pipeline endpoints through gateway/container path with and without token.

Evidence location: `DEBUG_API_REPORT.md`.

### H2-PIPELINE-LATENCY-TARGET
Hypothesis: SBERT stage latency can exceed the configured p95 target and push gateway requests close to `HTTP_TIMEOUT_SECONDS=15`.

Expected: p95 telemetry stays under target or timeout handling is explicit.

Actual: existing `/ready` telemetry reports SBERT p95 around 14.3s against a 15s gateway timeout.

Test: run controlled recommendation smoke and capture stage timings.

Evidence location: `DEBUG_API_REPORT.md`, `DEBUG_MODEL_REPORT.md`.

### H3-PIPELINE-EMPTY-CANDIDATES
Hypothesis: empty candidate pools return a valid empty recommendation response.

Expected: 200-style controlled empty ranked list with degradation metadata.

Actual: tests pass; runtime probe pending.

Test: run `/pipeline/run` or gateway recommendation with forced empty candidates if feasible.

Evidence location: `DEBUG_API_REPORT.md`.

## SBERT

### H1-SBERT-FINETUNED-RUNTIME
Hypothesis: SBERT runtime should load the fine-tuned checkpoint without falling back when transformer loading is enabled.

Expected: `/health` or smoke loader reports fine-tuned model version, dim 384, fallback false.

Actual: prior tests pass; current runtime smoke pending.

Test: call health and `/encode` with Indonesian text and batch input.

Evidence location: `DEBUG_MODEL_REPORT.md`.

### H2-SBERT-EMPTY-INPUT
Hypothesis: empty text batches must return a controlled validation response rather than crash.

Expected: controlled 4xx/empty result per contract.

Actual: tests cover some edge cases; runtime endpoint probe pending.

Test: call `/encode` and `/match/semantic` with empty input variants.

Evidence location: `DEBUG_MODEL_REPORT.md`.

### H3-SBERT-LATENCY-CACHE
Hypothesis: embedding cache or model warm state may be required to keep SBERT below gateway timeout during recommendation flow.

Expected: second identical request is materially faster or timeout/degradation is controlled.

Actual: `/ready` telemetry shows SBERT p95 near timeout.

Test: repeated encode/recommendation smoke with timings.

Evidence location: `DEBUG_MODEL_REPORT.md`.

## NCF / NeuMF

### H1-NCF-UNKNOWN-ID-FALLBACK
Hypothesis: unknown user/item IDs return safe cold-start scores rather than index errors.

Expected: bounded score output and fallback metadata.

Actual: tests pass; runtime probe pending.

Test: `/recommend/ncf` with unknown user and candidate IDs.

Evidence location: `DEBUG_MODEL_REPORT.md`.

### H2-NCF-FEEDBACK-PERSISTENCE
Hypothesis: feedback updates online state and invalidation behavior consistently.

Expected: feedback response is controlled and subsequent score/request behavior reflects update or cache invalidation.

Actual: tests pass; runtime probe pending.

Test: `/feedback`, `/users/{user_id}/invalidate`, then scoring smoke.

Evidence location: `DEBUG_MODEL_REPORT.md`.

### H3-NCF-ARTIFACT-LOAD
Hypothesis: service loads expected NeuMF artifacts/maps from `services/ncf/weights`.

Expected: model status exposes artifact readiness.

Actual: static artifacts exist; runtime status pending.

Test: `/model/status` and `/metrics` smoke.

Evidence location: `DEBUG_MODEL_REPORT.md`.

## DQN

### H1-DQN-ACTION-CONTRACT
Hypothesis: DQN returns skill/career actions, not raw job postings, for learning path responses.

Expected: action metadata describes skill/course/certificate/career milestones.

Actual: tests pass; runtime probe pending.

Test: `/learning-path` with missing skills and target role.

Evidence location: `DEBUG_MODEL_REPORT.md`.

### H2-DQN-STATE-SHAPE
Hypothesis: missing skills, empty skills, and unknown target roles must produce valid state vectors.

Expected: no shape/type exception; controlled fallback metadata.

Actual: tests pass; runtime probe pending.

Test: `/rank`, `/learning-path`, and `/rerank` with edge-case profiles.

Evidence location: `DEBUG_MODEL_REPORT.md`.

### H3-DQN-REWARD-UPDATE
Hypothesis: reward/feedback endpoints update online learner state without corrupting artifacts.

Expected: controlled feedback response and metrics update.

Actual: tests pass; runtime probe pending.

Test: `/reward` or `/feedback`, then `/metrics`.

Evidence location: `DEBUG_MODEL_REPORT.md`.

## Recommendation Aggregation

### H1-AGG-CALIBRATOR-SHAPE
Hypothesis: calibration feature vectors can drift from the learned feature schema.

Expected: static baseline fallback and learned output are both present with no shape error.

Actual: tests pass and smoke artifact exists; runtime pipeline summary pending.

Test: pipeline run and aggregate-stage summary inspection.

Evidence location: `DEBUG_MODEL_REPORT.md`.

### H2-AGG-REASON-FILTER-SCORES
Hypothesis: gateway reason-filter scores should be stable 0-1 values and sorted consistently by frontend controls.

Expected: semantic, interaction, career, location, and recency filters are present with labels.

Actual: tests pass; browser interaction pending.

Test: API recommendation smoke plus browser sort/filter audit.

Evidence location: `DEBUG_API_REPORT.md`, `DEBUG_BROWSER_REPORT.md`.

### H3-AGG-FAIRNESS-LATENCY
Hypothesis: fairness/rerank logic may increase latency or alter ranking unexpectedly under skewed candidates.

Expected: fairness metadata is present and latency remains controlled.

Actual: tests pass; runtime telemetry pending.

Test: run recommendation smoke with skewed profile/candidate set.

Evidence location: `DEBUG_MODEL_REPORT.md`.

## Docker / Networking

### H1-DOCKER-GATEWAY-REQ
Hypothesis: gateway Docker build fails because its Dockerfile copies root `requirements.txt` without the referenced requirement files needed by that root file.

Expected: gateway image installs requirements successfully.

Actual: fixed in `b747954`; gateway image now installs service requirements and builds successfully.

Test: inspect Dockerfile/compose context, then rebuild after a minimal Dockerfile/context fix.

Evidence location: `DEBUG_DOCKER_REPORT.md`, `DEBUG_FIX_LOG.md`.

### H2-DOCKER-CONTEXT
Hypothesis: missing root `.dockerignore` makes gateway builds slow and fragile by sending generated data, models, reports, and nested repos into the Docker build context.

Expected: build context excludes bulky/generated/unneeded files.

Actual: fixed in `b747954`; root `.dockerignore` exists and gateway build context is small.

Test: add scoped `.dockerignore`, rebuild, and compare context transfer/build time.

Evidence location: `DEBUG_DOCKER_REPORT.md`, `DEBUG_FIX_LOG.md`.

### H3-DOCKER-GATEWAY-CMD
Hypothesis: after dependency installation is fixed, gateway container may fail at runtime because Dockerfile command uses `uvicorn main:app` while the app lives at `services.gateway.main:app` when root context is copied.

Expected: container starts current gateway app.

Actual: fixed in `b747954`; rebuilt gateway uses `services.gateway.main:app` and health checks pass.

Test: rebuild after dependency fix and inspect container logs/health.

Evidence location: `DEBUG_DOCKER_REPORT.md`, `DEBUG_FIX_LOG.md`.

### H4-DOCKER-PORT-CONTRACT
Hypothesis: docs/runtime/API clients can drift between gateway host port 8000 and compose host port 9000.

Expected: one documented local API base is used for browser/dev flow, or each run mode is explicitly distinguished.

Actual: `frontend/.env.local` uses 9000; `localhost:8000` refused; some instructions still mention 8000.

Test: browser network audit and docs/config inspection.

Evidence location: `DEBUG_BROWSER_REPORT.md`, `DEBUG_DOCKER_REPORT.md`.

## Auth / Security

### H1-AUTH-JWT-FAILFAST
Hypothesis: missing or weak JWT secrets fail fast in app startup/config paths.

Expected: startup or token manager rejects missing/short secrets.

Actual: tests pass; process-level smoke pending.

Test: run isolated gateway config import with missing and short secrets.

Evidence location: `DEBUG_SECURITY_REPORT.md`.

### H2-AUTH-ADMIN-GUARDS
Hypothesis: admin routes and pipeline execution cannot be reached by normal authenticated users.

Expected: unauthenticated gets 401; non-admin gets 403; admin succeeds where allowed.

Actual: tests pass; runtime probe pending.

Test: register/login users with roles or use test client fixtures for route probes.

Evidence location: `DEBUG_SECURITY_REPORT.md`.

### H3-CORS-PRODUCTION
Hypothesis: production mode rejects wildcard/empty CORS origins.

Expected: explicit origins are required in production.

Actual: tests pass; runtime config smoke pending.

Test: import app/config under production env with wildcard/empty origins.

Evidence location: `DEBUG_SECURITY_REPORT.md`.

### H4-SECURITY-SECRET-LEAKAGE
Hypothesis: the dirty worktree may contain untracked generated secret files that must not be committed.

Expected: no `.env`, API key, token, or private credential is staged.

Actual: `secrets/` is untracked; contents have not been inspected or staged.

Test: staged-file audit before every commit and targeted secret scan excluding generated/binary bulk where practical.

Evidence location: `DEBUG_SECURITY_REPORT.md`.

## CI / Build

### H1-CI-DOCKER-DIVERGENCE
Hypothesis: CI installs top-level `requirements.txt` successfully, but gateway Docker build uses the same root requirements file without copying its referenced files, causing Docker-only failure.

Expected: dependency install semantics are consistent between CI and Docker.

Actual: current Docker build fails; CI workflow would install from repo checkout where referenced files exist.

Test: repair Docker install layer, rebuild gateway, and run CI-equivalent import checks.

Evidence location: `DEBUG_DOCKER_REPORT.md`.

### H2-CI-NODE-PARITY
Hypothesis: local Node/npm versions match CI enough for frontend lint/build parity.

Expected: local Node 22 and npm are compatible with CI Node 22.

Actual: local Node v22.6.0 and npm 10.5.2; frontend lint/build pass.

Test: no fix unless CI reports drift; record versions.

Evidence location: `DEBUG_FRONTEND_REPORT.md`.

### H3-CI-WARNING-POLICY
Hypothesis: warnings are allowed in local lint/build and CI, so important warning classes can persist unnoticed.

Expected: warnings are either accepted with rationale or cleaned when they point to real runtime risk.

Actual: 16 frontend lint warnings persisted while build passed.

Test: correlate warnings with browser/runtime behavior and decide whether to fix.

Evidence location: `DEBUG_FRONTEND_REPORT.md`.

## Runtime Contract

### H1-RUNTIME-ABORT-AS-TIMEOUT
Hypothesis: frontend request cancellation is classified as timeout and stale canceled requests can overwrite newer successful page state.

Expected: canceled stale requests are ignored or recorded only as diagnostics; timeout UI appears only for the active request that actually times out.

Actual: confirmed by the second runtime audit. Jobs and recommendations displayed timeout UI after canceled requests even when later/current data succeeded.

Test: targeted jobs filter cancellation and rapid recommendations navigation in `scripts/debug/runtime_contract_audit.py`.

Evidence location: `reports/debug/runtime_contract/summary.json`, `DEBUG_EVIDENCE.md`, `DEBUG_FRONTEND_REPORT.md`.

Status: **fixed** in nested frontend commit `7f746fe`; final dev/prod runtime audit passed with 0 failed checks.

### H2-RUNTIME-PROD-CORS-LOCALHOST-3001
Hypothesis: local production-mode Next.js server at `http://localhost:3001` is not allowed by gateway development CORS defaults.

Expected: local dev CORS allows both `localhost:3000` dev frontend and `localhost:3001` production-mode frontend, while production still rejects wildcard/empty origins.

Actual: confirmed by the second runtime audit. Browser CORS preflight blocked `POST /api/auth/login` from `http://localhost:3001`.

Test: CORS config regression tests plus production-mode runtime audit login.

Evidence location: `DEBUG_API_REPORT.md`, `DEBUG_SECURITY_REPORT.md`, `reports/debug/runtime_contract/summary.json`.

Status: **fixed** in root commit `305391e`; final production-mode runtime audit authenticated and passed all scenarios.

### H3-RUNTIME-THEME-SPINNER-STUCK
Hypothesis: theme provider/toggle leaves a stuck spinner or hydration/persistence mismatch after repeated clicks and reload.

Expected: repeated toggle clicks produce no permanent loading indicator, persist `scpa_theme`, and do not emit hydration warnings.

Actual: not confirmed after harness hardening. Final dev and prod audits passed repeated-click/reload checks.

Test: theme-toggle scenario in `scripts/debug/runtime_contract_audit.py`.

Evidence location: `DEBUG_BROWSER_REPORT.md`, `reports/debug/runtime_contract/summary.json`.

Status: **not fixed, no current runtime reproduction**.

## Product Quality / Data Signal

### H1-DATA-RUNTIME-SAMPLE-JOBS
Hypothesis: runtime scraper/pipeline fallback paths insert sample jobs into the product catalog when real source fetches fail or are not configured.

Expected: runtime catalog refresh either stores real source jobs or returns a controlled empty/degraded result; it never fabricates sample jobs for production-facing pages.

Actual: confirmed before fix by static code and live shallow/sample-like catalog evidence. Fixed in `fccb8a4`; scraper `/sample` is disabled and pipeline fallback no longer fabricates jobs.

Test: focused full-pipeline/red-team fallback tests plus live DB real-source count after purge/rescrape.

Evidence location: `DEBUG_EVIDENCE.md`, `DEBUG_DATABASE_REPORT.md`, `reports/debug/product_quality/summary.json`.

Status: **fixed**.

### H2-DATA-JOB-DESCRIPTION-SHALLOW
Hypothesis: the app stored/displayed card-level summaries instead of rich job detail text, leaving skill extraction and skill-gap with too little context.

Expected: job detail API and UI expose full description text plus parsed sections and skill signals when source data provides them.

Actual: confirmed before fix by 2614 shallow descriptions out of 2645 jobs and one-line detail UI. Fixed in `fccb8a4` and `frontend/` commit `999e2a8`.

Test: parser/unit tests, live `/api/jobs`, and Selenium job-detail semantic audit over five real jobs.

Evidence location: `DEBUG_DATABASE_REPORT.md`, `DEBUG_BROWSER_REPORT.md`, `reports/debug/product_quality/summary.json`.

Status: **fixed for current real-source catalog**.

### H3-DATA-SKILL-AUTOCOMPLETE-SPARSE
Hypothesis: skill autocomplete was backed by a tiny skill table/hardcoded list, causing queries such as `s`, `machine`, and `data` to return too few or no useful suggestions.

Expected: taxonomy-backed skill search returns multiple real-world suggestions with aliases/categories and duplicate handling.

Actual: confirmed before fix by live skill count of 3 and empty `machine`/`data` search. Fixed in `fccb8a4` and `frontend/` commit `999e2a8`.

Test: `tests/test_skill_taxonomy_search.py`, live skill-search probes, and product-quality Selenium autocomplete checks.

Evidence location: `DEBUG_API_REPORT.md`, `DEBUG_FRONTEND_REPORT.md`, `reports/debug/product_quality/summary.json`.

Status: **fixed**.

### H4-FE-CUSTOM-CURSOR-OVERLAY
Hypothesis: the blue ring in screenshots is not the theme icon itself but a global custom cursor ring with high z-index overlapping controls.

Expected: product controls should not have an unrelated cursor ring/spinner overlay.

Actual: confirmed by code inspection and screenshots. Fixed in nested frontend commit `999e2a8` by removing the cursor overlay from the shell and hiding legacy cursor classes.

Test: product-quality Selenium theme/skills screenshots and repeated theme-toggle checks.

Evidence location: `DEBUG_FRONTEND_REPORT.md`, `reports/debug/product_quality/screenshots/`.

Status: **fixed**.
