# Debug Fix Log

Updated: 2026-05-31 10:20 +07

## FIX-API-FEEDBACK-SLATE

Status: committed in `342edb0`, focused/adjacent/full backend tests passed, browser re-check pending current-runtime Docker repair.

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
