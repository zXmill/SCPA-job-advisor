# Code Review Remediation Plan

Updated: 2026-05-31 20:34 +07

## Review Context
- Branch: `agent-run`
- Base: `origin/master` (merge base `0c65c9d2e2f007b6ddcac384bf1a677af786e390`)
- Review scope: runtime core additions (gateway, scraper, pipeline, DB migrations, Docker, auth)
- High-confidence findings evaluated: security (manual), performance, business logic, deploy safety, duplication, dead code

## Accepted Findings

### P0 — CRITICAL

1. **R-1: Auth refresh-token test bypasses production jti/Redis rotation** ✅ **FIXED**
   - Changed `tests/test_security.py` to use in-memory `_FakeRedis` instead of `redis_client=None`
   - Added `test_rotation_marks_jti_as_used_in_redis` and `test_reused_refresh_token_after_rotation_fails`
   - Validation: 22 tests passed

2. **R-2: Hot-path index migration uses non-concurrent DDL** ✅ **FIXED**
   - Updated `db/migrations/009_reco_hot_indexes.py` to build/drop hot indexes with PostgreSQL `CONCURRENTLY` inside Alembic `autocommit_block()`.
   - Updated `db/migrations/013_hot_indexes_concurrent.py` as an idempotent repair migration for databases that reached `012` before the 009 deploy-safety fix.
   - Validation: `alembic downgrade 012_ab_testing_and_monitoring`, `alembic upgrade head`, `alembic current`, and `alembic heads` all pass.

3. **R-3: Gateway startup blocks on non-critical ML services** ✅ **FIXED**
   - Removed `depends_on: pipeline: condition: service_healthy` from gateway's compose block
   - Gateway now starts when postgres is healthy only
   - Validation: `docker compose config` passes

4. **R-4: .env.example password mismatch** ✅ **FIXED**
   - Changed `GATEWAY_DATABASE_URL` password from `CHANGE_ME` to `CHANGE_ME_USE_STRONG_PASSWORD`
   - Validation: grep confirms consistency

5. **R-5: Empty named volumes shadow baked-in model weights** ✅ **FIXED**
   - Removed `volumes: - weights:/app/weights` from ncf and dqn services in compose
   - Removed unused `volumes: weights` declaration
   - Validation: `docker compose config --services` passes, volume not declared

### P1 — WARNING

6. **R-6: _set_job_interaction_state hardcodes clicked/applied=false** ✅ **FIXED**
   - Changed SQL INSERT to use `:clicked` and `:applied` parameters instead of hardcoded `false`
   - Changed ON CONFLICT DO UPDATE SET to preserve clicked/applied via OR semantics
   - Validation: `tests/test_saved_jobs_skip.py::test_save_preserves_prior_click_and_apply_flags` passes

7. **R-7: Feedback handler OR semantics preserve contradictory flags** ✅ **FIXED**
   - Replaced OR semantics with explicit CASE transitions in PostgreSQL
   - `saved` is cleared when `dismissed` is True; `dismissed` is cleared when `saved` is True
   - Validation: `tests/test_saved_jobs_skip.py::test_skip_job_marks_dismissed_and_clears_saved` passes (save-then-skip clears saved)

8. **R-8: Market-demand job_count formula inflates by total skill count** ✅ **FIXED**
   - Changed `_compute_skill_market_demand` to return `{skill: (score, raw_job_count)}`
   - `market_demand` endpoint now uses raw count directly
   - Validation: `tests/test_market_aware_skill_path.py::test_market_demand_job_count_does_not_inflate_with_skill_count` passes

## Deferred Findings
- Outbox retry N+1 UPDATE anti-pattern (performance)
- Leading-wildcard ILIKE location without pg_trgm GIN index (performance)
- JSONB experiment expression index missing (performance)
- N+1 skill INSERT anti-pattern in profile endpoints (performance)
- Duplicate ISO datetime parsing (DRY)
- Duplicate Indonesia filter constants across gateway/scraper (DRY)
- Duplicated job-row-to-response-dict mapping (DRY)
- Dead code cleanup (_job_has_indonesia_signal, _get_active_experiments, DEFAULT_SKILL_TAXONOMY dead issue, TokenManager refresh methods)

## Rejected / Stale
None. All P0/P1 findings were confirmed against current source and fixed.

## Commit Log
1. `docs/debug/COMPACT_RECOVERY.md`, `docs/debug/DEBUG_MASTER_PLAN.md`, `docs/debug/CODE_REVIEW_REMEDIATION_PLAN.md` — reconciliation
2. `tests/test_security.py` — auth refresh-token coverage fix
3. `db/migrations/013_hot_indexes_concurrent.py` — deploy-safe index migration
4. `docker-compose.yml` — gateway startup dependency fix, env example fix, volume shadowing fix
5. `services/gateway/main.py` — interaction state preservation fix, feedback handler transition fix, market demand formula fix
6. `tests/test_saved_jobs_skip.py` — regression test for interaction state
7. `tests/test_market_aware_skill_path.py` — regression test for market demand job_count

## Validation Commands Run
- `.\.venv\Scripts\python.exe -m pytest tests/test_security.py tests/test_saved_jobs_skip.py tests/test_market_aware_skill_path.py -q` → 32 passed, 1 warning
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini heads` → `013_hot_indexes_concurrent (head)`
- `docker compose config --quiet && docker compose config --services` → pass
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini current` → current database remains at `012_ab_testing_and_monitoring`
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head` → fail on `013_hot_indexes_concurrent` autocommit handling
- `.\.venv\Scripts\python.exe -m py_compile db\migrations\009_reco_hot_indexes.py db\migrations\013_hot_indexes_concurrent.py` → pass
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head` after fix → pass
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini downgrade 012_ab_testing_and_monitoring` → pass
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head` after downgrade → pass
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini current` → `013_hot_indexes_concurrent (head)`
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini heads` → `013_hot_indexes_concurrent (head)`

## Current Active Task
Complete. All P0/P1 remediation findings have been triaged, fixed or deferred by scope, validated, documented, and committed.

## Next Exact Action
Stop per the remediation pass stop condition. Do not start P2 cleanup or unrelated runtime debugging in this phase.
