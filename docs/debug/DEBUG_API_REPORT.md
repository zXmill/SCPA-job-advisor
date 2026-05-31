# Debug API Report

Updated: 2026-05-31 09:12 +07

Status: route inventory initialized; request/response probes pending.

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
