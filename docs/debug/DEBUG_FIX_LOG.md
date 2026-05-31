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
