# Failure Ledger

## 2026-05-25 20:12 +07 - Frontend lint hook-order failure
- Error message: `React Hook "useCallback" is called conditionally. React Hooks must be called in the exact same order in every component render.`
- Command that caused it: `npm run lint` in `frontend/`.
- Root cause: `markImpressed = useCallback(...)` is declared after `if (authLoading || !user) return (...)` in `frontend/src/app/recommendations/page.tsx`.
- Fix attempted: Moved `markImpressed = useCallback(...)` above the auth early return.
- Final fix if solved: `npm run lint` exits 0 with warnings only; `npm run build` exits 0.
- Related files: `frontend/src/app/recommendations/page.tsx`.
- Do not repeat notes: Hooks must be declared before any conditional return in the component body.

## 2026-05-25 20:13 +07 - SSRF focused test allowlist gap
- Error message: `HTTPException: 400: scraper URL host is not allowed` for `https://id.jobstreet.com/id/jobs`.
- Command that caused it: `.\.venv\Scripts\python.exe -m pytest tests\test_ssrf_guard.py -q`.
- Root cause: The SSRF allowlist included `jobstreet.co.id` but not the existing scraper seed host suffix `jobstreet.com`.
- Fix attempted: Add `jobstreet.com` to `SCRAPER_ALLOWED_HOST_SUFFIXES`.
- Final fix if solved: Added `jobstreet.com` to the SSRF allowlist; focused SSRF tests passed with `9 passed`.
- Related files: `services/scraper/main.py`, `tests/test_ssrf_guard.py`.
- Do not repeat notes: Keep SSRF allowlist aligned with `SOURCE_URL_TEMPLATES` and existing seed hosts.

## 2026-05-25 20:52 +07 - Alembic revision id length failure
- Error message: `psycopg2.errors.StringDataRightTruncation: value too long for type character varying(32)`.
- Command that caused it: `.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head`.
- Root cause: New revision id `009_recommendation_hot_path_indexes` exceeded the existing `alembic_version.version_num varchar(32)` limit.
- Fix attempted: Shorten the revision id to `009_reco_hot_indexes`.
- Final fix if solved: Shortened the revision id and filename to `009_reco_hot_indexes`; `alembic upgrade head`, one-step downgrade, and re-upgrade passed.
- Related files: `db/migrations/009_reco_hot_indexes.py`.
- Do not repeat notes: Keep Alembic `revision` values at or below 32 characters in this project.

## 2026-05-25 21:05 +07 - Parallel pytest database bootstrap race
- Error message: `asyncpg.exceptions.UniqueViolationError: duplicate key value violates unique constraint "pg_type_typname_nsp_index"` while creating PostgreSQL enum type `userrole`.
- Command that caused it: `.\.venv\Scripts\python.exe -m pytest tests\test_jobs_upsert.py -q`, run in parallel with other pytest commands.
- Root cause: Multiple pytest processes bootstrapped the same shared `db_scpa_test` database at the same time. One process was creating enum types while another still had the type namespace in use.
- Fix attempted: Retry DB-backed pytest sequentially after the parallel auth-route checks finish.
- Final fix if solved: Sequential retry passed with `5 passed`.
- Related files: `tests/conftest.py`, `tests/test_jobs_upsert.py`.
- Do not repeat notes: Do not run DB-backed pytest commands in parallel against the same local test database unless each process uses a separate `SCPA_TEST_DB`.

## 2026-05-25 21:56 +07 - P2-005 stale aggregate strategy assertions
- Error message: `AssertionError` because tests expected `hybrid_scores_with_skill_alignment` or `learned_scores_no_static_domain_cap` while the aggregate now reports `learned_logistic_calibrator_with_static_baseline`.
- Command that caused it: `.\.venv\Scripts\python.exe -m pytest -q`.
- Root cause: The learned calibration layer intentionally replaced the old strategy labels, but two existing tests still asserted the previous aggregate strategy strings.
- Fix attempted: Update the E2E and online recommender tests to assert the learned calibrator strategy, calibrator metadata, and static baseline preservation. Also blend 15% of the static baseline into the served calibrated score so user-facing match percentages remain on the existing aggregate scale.
- Final fix if solved: Full backend pytest passed with `326 passed, 1 warning`.
- Related files: `tests/test_e2e_pipeline.py`, `tests/test_online_recommender_learning.py`, `services/pipeline/stages/stage_5_aggregate.py`.
- Do not repeat notes: When changing strategy labels, update contract tests to assert durable capabilities rather than legacy display strings.
