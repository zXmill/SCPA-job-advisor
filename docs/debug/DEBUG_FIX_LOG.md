# Debug Fix Log

Updated: 2026-05-31 19:30 +07

## REMEDIATION-01 — Auth Refresh-Token JTI Coverage
Status: **FIXED** in `tests/test_security.py`

- Added `_FakeRedis` async stand-in to exercise `rotate_refresh_token` used-jti tracking.
- Replaced raw `jwt.encode()` in `test_rotation_with_expired_refresh_fails` with `TokenManager(refresh_ttl_seconds=-1)` to test production path.
- Validation: 22 security tests pass.

## REMEDIATION-02 — Deploy-Safe Index Migration
Status: **FIXED** via follow-up migration `db/migrations/013_hot_indexes_concurrent.py`

- Created `013_hot_indexes_concurrent.py` that uses `CREATE INDEX CONCURRENTLY IF NOT EXISTS`.
- Uses `autocommit_block()` to avoid ACCESS EXCLUSIVE lock during index builds.
- Validation: `alembic heads` shows `013_hot_indexes_concurrent`.

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
