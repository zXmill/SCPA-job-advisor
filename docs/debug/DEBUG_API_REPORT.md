# Debug API Report

Updated: 2026-05-31 14:56 +07

Status: route inventory initialized; served-slate feedback bug fixed and browser-verified; broader API runtime probes pending.

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

## Confirmed Fix: FIX-API-FEEDBACK-SLATE
- `services/gateway/main.py` now persists the served slate and its ranked items before returning recommendation data.
- The persistence includes slate ID, user ID, pipeline run ID, model versions, fallback flags, request context, component scores, and explanation metadata.
- `tests/test_recommendation_feedback_slate.py` covers the route sequence that failed in the browser: authenticated `/api/recommendations`, then authenticated `/api/recommendations/feedback` using the returned slate ID.
- Focused, adjacent, and full backend tests pass.
- Browser re-check passed against the rebuilt current gateway runtime.
