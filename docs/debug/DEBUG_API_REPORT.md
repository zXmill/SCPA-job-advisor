# Debug API Report

Updated: 2026-05-31 15:20 +07

Status: gateway API runtime probes completed and fixed; final rebuilt-runtime probe passed with 83/83 cases and 0 HTTP 5xx responses.

## Audit Rules
- Determine method, path, and auth requirement for each route.
- Send valid, invalid, and empty input when feasible.
- Record status code, response shape, and server logs.
- Confirm dangerous routes are protected.
- Confirm ML routes degrade gracefully when dependencies are unavailable.

## Gateway Route Groups
- Open/health: `/`, `/health`, `/ready`, `/api/company-logo`.
- Auth/profile: `/api/auth/register`, `/api/auth/login`, `/api/auth/me`, `/api/profile/completeness`, `/api/profile`, `/api/profile/onboarding`, `/api/profile/cv`, `/api/profile/certificates`.
- Jobs/user actions: `/api/jobs`, `/api/jobs/{job_id}`, `/api/jobs/saved`, save/unsave/skip, applications, skill gap, market demand, job alerts.
- Recommendation/learning: `/api/recommendations`, `/recommendations`, `/api/recommendations/feedback`, `/api/learning-path`.
- Admin/ops: `/api/admin/model-health`, `/pipeline/run`.
- Experiment/event tracking: `/api/experiments`, lifecycle/assignment/metrics routes, `/api/events/track`.

## Internal Service Route Groups
- Pipeline internal-token routes: `/pipeline/run`, `/training/status`, `/training/run-once`, `/feedback`, `/pipeline/invalidate-user/{user_id}`.
- Scraper: health, HTML scrape, URL scrape, run, sample.
- SBERT: health, semantic match, encode, metrics.
- NCF: health, jobs upsert, feedback, train, predict, recommend, invalidate, model status, metrics.
- DQN: health, jobs upsert, rank, learning path, rerank, reward/feedback, recommend, train, model status, metrics.

## Runtime Findings
- `POST /api/auth/login` succeeds for the demo account advertised on `/auth`.
- Authenticated Selenium audit found `POST /api/recommendations/feedback` returns HTTP 500 during impression tracking.
- Gateway log root cause: `feedback_events.slate_id` violates the FK to `served_slates.id`; the gateway returns a new `recommendation_id`/served slate ID to the frontend but does not persist the corresponding `served_slates` row before feedback arrives.
- Final authenticated Selenium audit after the served-slate and Docker/runtime fixes reports 0 network failures; recommendation feedback no longer returns HTTP 500 in the browser path.

## API Runtime Probe: 2026-05-31
- Harness: `scripts/debug/api_runtime_probe.py`.
- Final artifacts: `reports/debug/api/gateway_runtime_probe_20260531T081953Z.json` and `reports/debug/api/gateway_runtime_probe_20260531T081953Z.log`.
- Coverage: generated normal/admin probe users; open/health, skills search, auth/profile, profile upload validation, jobs/saved/skip/applications/skill-gap/market-demand/job-alerts, recommendations/feedback/learning-path, admin model-health, admin `/pipeline/run`, experiments lifecycle, event tracking.
- Initial corrected run after DB migration repair: 83 cases, 81 passed, 2 failed. The failed cases were `APPLICATIONS-CREATE-MISSING-JOB` and `FEEDBACK-MISSING-SLATE`, both HTTP 500.
- Final rebuilt-runtime run after `6366b67` and harness token-key sanitization: 83 cases, 83 passed, 0 failed, 0 HTTP 5xx.
- Server log check: no application FK error, feedback slate FK error, recommendation job upsert error, or internal-server-error log remained in the final probe. The only matched traceback is the known passlib/bcrypt version-warning path during password hashing.

## Confirmed Fix: FIX-API-RUNTIME-GUARDS
- Commit: `6366b67 fix: harden gateway api runtime guards`.
- `POST /api/applications` now validates each requested job with `_require_job_uuid` before inserting, returning controlled `404 Job not found` instead of leaking an application FK violation as 500.
- `POST /api/recommendations/feedback` now validates the job and any provided served-slate UUID before persistence. Unknown served slates return controlled `404 Served slate not found`; malformed slate IDs return 400.
- Recommendation job upsert now normalizes ISO string `posted_at` values from pipeline JSON into `datetime` objects before asyncpg insertion.
- Regression tests: `tests/test_gateway_api_runtime_guards.py` and `tests/test_recommendation_feedback_slate.py::test_feedback_with_unknown_served_slate_returns_404`.

## Confirmed Fix: FIX-API-FEEDBACK-SLATE
- `services/gateway/main.py` now persists the served slate and its ranked items before returning recommendation data.
- The persistence includes slate ID, user ID, pipeline run ID, model versions, fallback flags, request context, component scores, and explanation metadata.
- `tests/test_recommendation_feedback_slate.py` covers the route sequence that failed in the browser: authenticated `/api/recommendations`, then authenticated `/api/recommendations/feedback` using the returned slate ID.
- Focused, adjacent, and full backend tests pass.
- Browser re-check passed against the rebuilt current gateway runtime.
