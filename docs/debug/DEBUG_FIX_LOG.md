# Debug Fix Log

Updated: 2026-05-31 15:20 +07

## FIX-API-FEEDBACK-SLATE

Status: committed in `342edb0`, focused/adjacent/full backend tests passed, final browser re-check passed after Docker/runtime repair.

Related hypothesis: `H4-API-FEEDBACK-SLATE-FK`.

Bug:
- Authenticated Selenium audit loaded `/recommendations`, then frontend impression tracking called `POST /api/recommendations/feedback`.
- The gateway returned HTTP 500.
- Gateway logs showed `feedback_events_slate_id_fkey`: feedback referenced a slate ID that did not exist in `served_slates`.

Root cause:
- `run_pipeline` generated and returned a `recommendation_id`/served slate ID for the frontend.
- The gateway did not persist the corresponding `served_slates` and `served_slate_items` rows before feedback arrived.
- The existing feedback write correctly enforced the database FK, so the missing served-slate write surfaced as a 500.

Fix:
- Added `_persist_served_slate` in `services/gateway/main.py`.
- The helper persists the returned slate and ranked jobs, including pipeline run ID, model provenance, fallback flags, context, component scores, and explanation metadata.
- `run_pipeline` now persists the served slate before returning recommendation data.
- `tests/conftest.py` now truncates feedback and served-slate tables for DB test isolation.
- Added `tests/test_recommendation_feedback_slate.py` to reproduce the exact API sequence: request recommendations, assert the served slate exists, then submit impression feedback and assert `feedback_events` is persisted.

Why this is correct:
- Feedback is now written against a durable slate row with the same UUID returned to the frontend.
- The fix preserves the FK rather than weakening it.
- The pipeline feedback forwarding path remains unchanged; only the missing local persistence contract is added.

Validation:
- Pre-fix focused regression failed because `served_slates` count was 0 after `/api/recommendations`.
- `py_compile` passed for changed Python files.
- Focused test passed: `tests\test_recommendation_feedback_slate.py`.
- Adjacent tests passed: recommendation reason filters, feedback outbox, and pipeline contracts.
- Full backend suite passed: 390 passed, 3 warnings.
- Final Selenium audit after rebuilding the current Docker runtime passed with 0 network failures.

## FIX-DOCKER-RUNTIME-BUILD

Status: committed in `b747954`, full compose build/up passed, current runtime healthy.

Related hypotheses: `H1-DOCKER-GATEWAY-REQ`, `H2-DOCKER-CONTEXT`, `H3-DOCKER-GATEWAY-CMD`, and discovered `H5-DOCKER-PIPELINE-PACKAGE`.

Bug:
- Initial `docker compose up -d --build` failed in the gateway image dependency layer because pip could not open `requirements-db.txt`.
- Gateway root build context transfer was about 5.06GB.
- After the gateway image built, full compose startup exposed a pipeline runtime import failure: `ModuleNotFoundError: No module named 'services'`.

Root cause:
- Gateway Dockerfile copied root `requirements.txt` instead of `services/gateway/requirements.txt`.
- Root `.dockerignore` was missing, so generated assets were sent to Docker.
- Gateway command referenced `main:app` despite root package layout.
- Pipeline Dockerfile ran `python main.py` from a service-local layout while stage 5 imports `services.pipeline.calibration`.

Fix:
- Added root `.dockerignore`.
- Updated gateway Dockerfile to install service requirements, copy only required runtime package paths, and run `services.gateway.main:app`.
- Updated pipeline compose build context to root and pipeline Dockerfile to run `services.pipeline.main:api`.

Validation:
- `docker compose build gateway` passed with a small context.
- Gateway container import smoke passed.
- `docker compose up -d --build` passed.
- `docker compose ps`, gateway `/health`, and gateway `/ready` all passed.

## FIX-API-RUNTIME-GUARDS

Status: committed in `6366b67`, focused/adjacent backend tests passed, rebuilt-runtime API probe passed.

Related hypotheses: `H2-API-INVALID-INPUT-SHAPES`, `H3-API-DOWNSTREAM-DEGRADATION`.

Bug:
- Runtime probe case `APPLICATIONS-CREATE-MISSING-JOB` returned HTTP 500 for an authenticated `POST /api/applications` request with a nonexistent job ID.
- Runtime probe case `FEEDBACK-MISSING-SLATE` returned HTTP 500 for authenticated recommendation feedback with a nonexistent served-slate ID.
- Gateway logs for valid recommendation requests showed asyncpg rejecting ISO string `posted_at` values during recommendation job upsert.

Root cause:
- `create_applications` converted any submitted job ID to a UUID and inserted directly, leaving missing jobs to fail at the database FK.
- `recommendation_feedback` inserted feedback before validating that a provided served-slate UUID exists for the current user.
- `_upsert_jobs_to_db` passed pipeline JSON timestamp strings directly to asyncpg for a datetime column.

Fix:
- `create_applications` now calls `_require_job_uuid` before insert.
- `recommendation_feedback` now validates job existence, malformed slate IDs, and current-user served-slate ownership before insert.
- `_coerce_posted_at` normalizes ISO strings to `datetime` before recommendation job upsert.
- Added `tests/test_gateway_api_runtime_guards.py` and a missing-slate regression in `tests/test_recommendation_feedback_slate.py`.

Why this is correct:
- The fix preserves database FKs and turns expected client-side invalid input into controlled 4xx responses.
- Served-slate validation is scoped to the authenticated user, avoiding cross-user slate references.
- Timestamp normalization matches the pipeline JSON contract without weakening the job persistence path.

Validation:
- Pre-fix focused tests failed for the same three runtime defects.
- Focused tests passed: 3 passed.
- Adjacent API tests passed: 10 passed.
- Rebuilt Docker gateway passed health checks.
- Final API runtime probe passed: 83/83, 0 HTTP 5xx.
