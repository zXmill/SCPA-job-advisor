# Debug Fix Log

Updated: 2026-05-31 21:41 +07

## REMEDIATION-01 — Auth Refresh-Token JTI Coverage
Status: **FIXED** in `tests/test_security.py`

- Added `_FakeRedis` async stand-in to exercise `rotate_refresh_token` used-jti tracking.
- Replaced raw `jwt.encode()` in `test_rotation_with_expired_refresh_fails` with `TokenManager(refresh_ttl_seconds=-1)` to test production path.
- Validation: 22 security tests pass.

## REMEDIATION-02 — Deploy-Safe Index Migration
Status: **FIXED** in `db/migrations/009_reco_hot_indexes.py` and `db/migrations/013_hot_indexes_concurrent.py`

- `009_reco_hot_indexes.py` now uses `CREATE INDEX CONCURRENTLY IF NOT EXISTS` and `DROP INDEX CONCURRENTLY IF EXISTS` inside Alembic `autocommit_block()` so fresh deployments avoid long write-blocking index builds.
- `013_hot_indexes_concurrent.py` now uses `autocommit_block()` correctly and remains an idempotent repair migration for databases that reached `012` before this fix.
- Validation: py_compile passed; `alembic upgrade head`, `downgrade 012_ab_testing_and_monitoring`, `upgrade head`, `current`, and `heads` passed.

## REMEDIATION-03 — Gateway Startup Degradation
Status: **FIXED** in `docker-compose.yml`

- Removed `pipeline: condition: service_healthy` from gateway's `depends_on`.
- Gateway now starts when postgres is healthy; routes return controlled 502/504 when downstream unavailable.
- Validation: `docker compose config --quiet && docker compose config --services` passes.

## REMEDIATION-04 — .env.example Password Consistency
Status: **FIXED** in `.env.example`

- Changed `GATEWAY_DATABASE_URL` password from `CHANGE_ME` to `CHANGE_ME_USE_STRONG_PASSWORD`.
- Validation: grep confirms `POSTGRES_PASSWORD` and `GATEWAY_DATABASE_URL` use matching placeholder.

## REMEDIATION-05 — Model Weights Volume Shadowing
Status: **FIXED** in `docker-compose.yml`

- Removed `volumes: - weights:/app/weights` from `ncf` and `dqn` services.
- Removed unused `volumes: weights` declaration.
- Validation: `docker compose config --services` shows no weights volume mount.

## REMEDIATION-06 — Interaction State Signal Preservation
Status: **FIXED** in `services/gateway/main.py`

- `_set_job_interaction_state`: Changed to pass `:clicked` and `:applied` parameters; updated ON CONFLICT DO UPDATE SET to preserve booleans via OR.
- Validation: `tests/test_saved_jobs_skip.py::test_save_preserves_prior_click_and_apply_flags` passes; `test_skip_job_marks_dismissed_and_clears_saved` passes.

## REMEDIATION-07 — Feedback Handler State Transitions
Status: **FIXED** in `services/gateway/main.py`

- Replaced OR semantics for `saved`/`dismissed` with CASE-based transitions:
  - `saved = CASE WHEN dismissed THEN false WHEN saved THEN true ELSE existing END`
  - `dismissed = CASE WHEN saved THEN false WHEN dismissed THEN true ELSE existing END`
- This ensures save clears dismissed, dismiss (skip) clears saved.
- Validation: Tests pass; no contradictory saved=true/dismissed=true states on combined events.

## REMEDIATION-08 — Market Demand Job Count Formula
Status: **FIXED** in `services/gateway/main.py`

- Changed `_compute_skill_market_demand` return type from `dict[str, float]` to `dict[str, tuple[float, int]]`.
- Endpoint now uses raw `job_count` from tuple instead of recomputing from normalized score.
- Validation: `tests/test_market_aware_skill_path.py::test_market_demand_job_count_does_not_inflate_with_skill_count` passes.

## Full Test Suite
`.\.venv\Scripts\python.exe -m pytest -q` → 397 passed, 3 warnings

## RUNTIME-01 — Stale Canceled Jobs/Recommendations Timeout UI
Status: **FIXED** in nested frontend commit `7f746fe`

- Root cause: `AbortError` from canceled requests was normalized as a timeout-style `ApiError`, and page-level catch/finally blocks could still set timeout/error/loading state after a newer request became active.
- Files changed: `frontend/src/lib/api.ts`, `frontend/src/app/analytics/page.tsx`, `frontend/src/app/recommendations/page.tsx`.
- Fix: introduced `ApiCancellationError`, separated timeout aborts from non-timeout cancellations, added monotonic active-request guards, and only clears loading/error for the active request.
- Recommendation timeout policy changed from 15 seconds to 45 seconds because hybrid recommendation calls can fan out through gateway/model services.
- Validation: frontend lint/build passed; final runtime contract audit passed dev/prod jobs, recommendations, targeted cancellation, and gateway-restart scenarios with no stale timeout UI.

## RUNTIME-02 — Local Production Frontend CORS Contract
Status: **FIXED** in root commit `305391e`

- Root cause: the local production-mode Next server runs at `http://localhost:3001`, but gateway development CORS defaults and compose defaults allowed only `http://localhost:3000` and `http://localhost:8000`.
- Files changed: `.env.example`, `docker-compose.yml`, `services/gateway/main.py`, `tests/test_cors_config.py`.
- Fix: added `http://localhost:3001` to development CORS defaults and examples without weakening production wildcard/empty-origin rejection.
- Validation: `tests/test_cors_config.py` passed, `docker compose config --quiet` passed, and final production-mode runtime audit authenticated successfully and passed all scenarios.

## RUNTIME-03 — Theme Toggle Stuck State
Status: **NOT FIXED, NOT REPRODUCED AFTER HARNESS HARDENING**

- User-reported defect: theme icon/spinner appeared stuck or overlapping.
- Evidence: final dev and prod runtime audits clicked the toggle 5 times, reloaded, saw `scpa_theme=dark`, no stuck spinner/loading state, and no hydration warning.
- Decision: no product-code change was made because runtime evidence did not confirm a current defect.

## PRODUCT-01 — Real Runtime Job Data Only
Status: **FIXED** in root commit `fccb8a4`

- Runtime sample/fallback job paths were removed from scraper and pipeline catalog refresh flows.
- Scraper `/sample` now returns 410, and scraper/pipeline empty or failure paths return controlled empty/degraded results instead of fabricating sample job records.
- Added `scripts/data/purge_jobs_for_real_rescrape.py` for explicit catalog purge before real-source refresh.
- Validation: live DB now has 10 real-source jobs and 0 sample-source runtime jobs after purge/rescrape.

## PRODUCT-02 — Rich Job Descriptions and Skill Signals
Status: **FIXED** in root commit `fccb8a4` and nested frontend commit `999e2a8`

- Added rich job-description parser/storage/API fields and migration `014_rich_job_desc_skill_sources`.
- Gateway job responses now expose full `description_text`, parsed sections, metadata, and required/preferred/extracted skills.
- Frontend job detail now renders structured sections and skill-gap context when fields are available.
- Validation: product audit opened five real job details with 523 to 2655 character descriptions and structured skill/section payloads.

## PRODUCT-03 — Real-World Skill Taxonomy Autocomplete
Status: **FIXED** in root commit `fccb8a4` and nested frontend commit `999e2a8`

- Added O*NET 30.3 plus local Indonesian/technical alias taxonomy with 8888 normalized entries.
- Gateway skill search now returns taxonomy-ranked suggestions with category, source, aliases, and confidence.
- Frontend profile autocomplete shows alias/category detail and blocks duplicate selected skills.
- Validation: targeted API/Selenium checks passed for `s`, `machine`, `data`, `docker`, `english`, and related queries.

## PRODUCT-04 — Theme/Control Overlay Visual Defect
Status: **FIXED** in nested frontend commit `999e2a8`

- Root cause: `custom-cursor-ring`/`custom-cursor-dot` overlaid controls and visually matched the blue stuck loading ring in user screenshots.
- Removed the custom cursor overlay from the product shell and hid legacy cursor CSS classes.
- Theme provider/toggle state was stabilized so icon state follows persisted theme.
- Validation: product audit clicked theme toggle across major routes, reloaded, and saw no stuck spinner or hydration warning.

## PRODUCT-05 — Product-Quality Selenium Audit Harness
Status: **ADDED** in root commit `7286d84`

- Added `scripts/debug/selenium_product_quality_audit.py`.
- Harness records semantic checks, screenshots, DOM snapshots, console logs, and network events under `reports/debug/product_quality/`.
- Validation: final run passed 48/48 checks and redacted auth material from artifacts.

## PRODUCT-06 — Realtime Scrape Quality Gate
Status: **FIXED** in root commit `f236820`

- Root cause: the direct realtime scraper endpoint could return listing-page summaries or empty descriptions when external sources exposed only search-card content. This meant the database could be real-source but still too shallow for skill extraction and skill-gap.
- Files changed: `services/scraper/main.py`, `services/shared/job_description.py`, `docker-compose.yml`, `tests/test_job_description_quality.py`.
- Fix: prioritize higher-signal sources, cap realtime URL/concurrency to avoid timeout storms, fetch more candidates before filtering, reject short/generic/missing-skill candidates, and parse additional inline job-description headings.
- Validation: focused scraper/parser tests passed; Docker compose config passed; rebuilt scraper passed direct `/scrape/run?limit=10`; pipeline `refresh_jobs=true` upserted 7 quality-gated real jobs; DB guard checks show `sample_jobs=0`, `under_300_desc=0`, `no_skill_signal=0`.

## CONTINUOUS-01 — Continuous Realtime Scraper Worker
Status: **FIXED** in root commit `f26b208`

- Root cause: the realtime scraper/pipeline path was quality-gated but still finite. `/scrape/run?limit=N` and `/pipeline/run refresh_jobs=true` could refresh a bounded catalog, but there was no operator-safe worker that could keep discovering, validating, deduplicating, and upserting jobs over time.
- Files changed: `.env.example`, `docker-compose.yml`, `db/models.py`, `db/migrations/015_continuous_scrape_metadata.py`, `services/pipeline/stages/stage_1_scrape.py`, `services/pipeline/continuous_scraper.py`, `scripts/harness_continuous_scrape.py`, `scripts/check_realtime_job_quality.py`, `tests/test_continuous_scraper.py`, `tests/test_job_upsert_idempotency.py`.
- Fix: added a separate continuous worker process under Compose profile `continuous`, kept request handlers finite, added bounded test mode through `SCRAPER_TEST_MAX_CYCLES`, added structured per-cycle evidence output, and made upsert identity stable through normalized non-empty `source_url`.
- Database lifecycle metadata added: `external_id`, `scraped_at`, `first_seen_at`, `last_seen_at`, `quality_status`, `quality_reject_reason`, and `content_hash`.
- Quality gate remains strict: sample/fake jobs, missing source URLs, descriptions under 300 characters, generic listing summaries, jobs without skill signals, and disallowed sources remain rejected.
- Validation: continuous runner/upsert tests passed, model/pipeline contract checks passed, scraper quality tests passed, Compose config passed with and without the continuous profile, Docker images built, bounded 1-cycle and 2-cycle harness runs passed, pipeline `refresh_jobs=true` remained compatible, and final DB/API guard showed 8 Kalibrr rows with no duplicate explosion or quality violations.
