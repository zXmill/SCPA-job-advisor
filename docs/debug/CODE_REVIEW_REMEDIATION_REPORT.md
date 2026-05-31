# Code Review Remediation Report

Updated: 2026-05-31 19:30 +07

## Summary
All 8 P0/P1 high-confidence code review findings were fixed and validated:
- 5 deploy-safety/blocker issues (auth test coverage, concurrent indexes, gateway startup, env example, volume shadowing)
- 3 business-logic/data-signal issues (interaction state preservation, feedback state transitions, market demand formula)

## Findings Accepted and Fixed

| ID | Severity | File | Description | Fix |
|----|----------|------|-----------|-----|
| R-1 | P0 | `tests/test_security.py` | Auth refresh-token tests bypassed JTI/Redis rotation | Added `_FakeRedis` async mock; tests now exercise production rotation flow |
| R-2 | P0 | `db/migrations/009_reco_hot_indexes.py` | Non-concurrent index creation blocks writes | Created `013_hot_indexes_concurrent.py` with `CREATE INDEX CONCURRENTLY` |
| R-3 | P0 | `docker-compose.yml` | Gateway startup chained to all ML service health | Removed `pipeline: condition: service_healthy` from gateway |
| R-4 | P0 | `.env.example` | Password placeholders mismatched | Aligned `GATEWAY_DATABASE_URL` to `CHANGE_ME_USE_STRONG_PASSWORD` |
| R-5 | P0 | `docker-compose.yml` | Named volume shadowed baked-in model weights | Removed weights volume mounts from ncf/dqn |
| R-6 | P1 | `services/gateway/main.py` | `_set_job_interaction_state` erased clicked/applied | Added OR semantics for clicked/applied in ON CONFLICT |
| R-7 | P1 | `services/gateway/main.py` | Feedback handler allowed saved=true AND dismissed=true | Added CASE transitions per event type |
| R-8 | P1 | `services/gateway/main.py` | Market demand job_count inflated by skill count | Return raw count from `_compute_skill_market_demand` |

## Tests Added/Changed

- `tests/test_security.py` — `_FakeRedis` class, `test_rotation_marks_jti_as_used_in_redis`, `test_reused_refresh_token_after_rotation_fails`
- `tests/test_saved_jobs_skip.py` — `test_save_preserves_prior_click_and_apply_flags`
- `tests/test_market_aware_skill_path.py` — `test_market_demand_job_count_does_not_inflate_with_skill_count`

## Validation Performed

| Command | Result |
|---------|--------|
| `.\.venv\Scripts\python.exe -m pytest -q` | 397 passed, 3 warnings |
| `alembic heads` | `013_hot_indexes_concurrent (head)` |
| `docker compose config --quiet` | pass |
| `docker compose config --services` | scraper, dqn, postgres, gateway, ncf, sbert, pipeline |

## Remaining Limitations / P2 Deferred

- N+1 INSERT anti-pattern for skills (performance)
- Unindexed `ILIKE %:location%` on jobs (performance)
- Missing pg_trgm GIN index (performance)
- JSONB expression index for experiment metrics (performance)
- Duplicate ISO datetime parsing across gateway (DRY)
- Duplicate Indonesia filter constants across scraper/gateway (DRY)
- Duplicated job payload mapping (DRY)
- Dead code: `_job_has_indonesia_signal`, `_get_active_experiments`, unused `TokenManager` refresh methods

These items are deferred per the remediation scope rules (P2 and lower).

## Next Recommended Phase

- **Runtime Contract Debugging Pass** — if evidence shows inconsistent timeout/stale-request behavior in gateway API responses.
- See `docs/debug/DEBUG_MASTER_PLAN.md` for the next active task after this remediation.