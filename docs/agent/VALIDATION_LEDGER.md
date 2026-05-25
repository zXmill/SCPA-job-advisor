# Validation Ledger

## 2026-05-25 19:40 +07
- Task ID: `INIT-001`
- Command: `.\.venv\Scripts\python.exe -m json.tool docs\agent\TASK_QUEUE.json`
- Result: pass
- Summary: JSON parsed successfully with exit code 0.
- Related commit hash: `703c516`.

## 2026-05-25 19:40 +07
- Task ID: `INIT-001`
- Command: `git status --short --branch`
- Result: pass
- Summary: Command completed and confirmed pre-existing dirty state plus new initializer files.
- Related commit hash: `703c516`.

## 2026-05-25 19:40 +07
- Task ID: `INIT-001`
- Command: `git diff -- AGENTS.md docs\agent`
- Result: pass
- Summary: Command completed. It showed no output because the initializer files were still untracked; staged diff must be reviewed before commit.
- Related commit hash: `703c516`.

## 2026-05-25 19:47 +07
- Task ID: `INIT-001`
- Command: `git diff --cached --name-only`
- Result: pass
- Summary: Staged files were exactly `AGENTS.md` and the durable `docs/agent/` files.
- Related commit hash: `703c516`.

## 2026-05-25 19:47 +07
- Task ID: `INIT-001`
- Command: `git diff --cached --check`
- Result: pass
- Summary: No whitespace errors reported in staged initializer files.
- Related commit hash: `703c516`.

## 2026-05-25 19:47 +07
- Task ID: `INIT-001`
- Command: `git commit -m "docs: initialize codex long-running project state"`
- Result: pass
- Summary: Created commit `703c516` with 9 initializer files.
- Related commit hash: `703c516`.

## 2026-05-25 19:57 +07
- Task ID: `P0-001`
- Command: `.\.venv\Scripts\python.exe -m json.tool docs\agent\TASK_QUEUE.json`
- Result: pass
- Summary: JSON parsed successfully after starting the cleanup audit task.
- Related commit hash: `b2b4f55`.

## 2026-05-25 19:57 +07
- Task ID: `P0-001`
- Command: `git status --short --branch`
- Result: pass
- Summary: Command completed and showed only docs/agent task changes plus pre-existing dirty files.
- Related commit hash: `b2b4f55`.

## 2026-05-25 19:57 +07
- Task ID: `P0-001`
- Command: `git diff -- docs/agent`
- Result: pass
- Summary: Command completed and showed modified tracked state files; untracked `CLEANUP_AUDIT.md` requires staged diff review before commit.
- Related commit hash: `b2b4f55`.

## 2026-05-25 20:08 +07
- Task ID: `P0-002`
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
- Result: pass
- Summary: `291 passed, 11 warnings in 96.24s`.
- Related commit hash: `7b6ce82`.

## 2026-05-25 20:10 +07
- Task ID: `P0-002`
- Command: `npm run lint` in `frontend/`
- Result: fail
- Summary: 1 error and 18 warnings. The error is `react-hooks/rules-of-hooks` for conditional `useCallback` at `frontend/src/app/recommendations/page.tsx:329`.
- Related commit hash: `frontend:6e76e92`.

## 2026-05-25 20:18 +07
- Task ID: `P0-FE-001`
- Command: `npm run lint` in `frontend/`
- Result: pass
- Summary: Lint exited 0 with 18 warnings and no errors.
- Related commit hash: `frontend:6e76e92`.

## 2026-05-25 20:21 +07
- Task ID: `P0-FE-001`
- Command: `npm run build` in `frontend/`
- Result: pass
- Summary: Next.js 16.2.6 build compiled successfully, TypeScript completed, and 12 static pages generated.
- Related commit hash: `frontend:6e76e92`.

## 2026-05-25 20:28 +07
- Task ID: `P0-FE-001`
- Command: `git -C frontend commit -m "fix: resolve frontend hook order violation"`
- Result: pass
- Summary: Created nested frontend commit `6e76e92` adding `src/app/recommendations/page.tsx`.
- Related commit hash: `frontend:6e76e92`.

## 2026-05-25 20:38 +07
- Task ID: `P0-002`
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
- Result: pass
- Summary: `291 passed, 11 warnings in 97.94s`.
- Related commit hash: `7b6ce82`.

## 2026-05-25 20:38 +07
- Task ID: `P0-002`
- Command: `npm run lint` in `frontend/`
- Result: pass
- Summary: Lint exited 0 with 18 warnings and no errors.
- Related commit hash: `7b6ce82`.

## 2026-05-25 20:38 +07
- Task ID: `P0-002`
- Command: `docker compose config --quiet`
- Result: pass
- Summary: Compose configuration validated with no output.
- Related commit hash: `7b6ce82`.

## 2026-05-25 20:38 +07
- Task ID: `P0-002`
- Command: `.\.venv\Scripts\python.exe -m json.tool docs\agent\TASK_QUEUE.json`
- Result: pass
- Summary: JSON parsed successfully.
- Related commit hash: `7b6ce82`.

## 2026-05-25 20:45 +07
- Task ID: `P0-002`
- Command: `npm run build` in `frontend/`
- Result: pass
- Summary: Next.js 16.2.6 build compiled successfully, TypeScript completed, and 12 static pages generated.
- Related commit hash: `7b6ce82`.

## 2026-05-25 20:06 +07
- Task ID: `P1-SEC-001`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_internal_service_auth.py -q`
- Result: pass
- Summary: `3 passed in 0.14s`.
- Related commit hash: `1392e58`.

## 2026-05-25 20:06 +07
- Task ID: `P1-SEC-001`
- Command: `$env:INTERNAL_SERVICE_TOKEN='test-internal-token-32-bytes-long'; docker compose config --quiet`
- Result: pass
- Summary: Compose configuration validated with no output using a throwaway process-local internal token.
- Related commit hash: `1392e58`.

## 2026-05-25 20:07 +07
- Task ID: `P1-SEC-001`
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
- Result: pass
- Summary: `294 passed, 11 warnings in 98.51s`.
- Related commit hash: `1392e58`.

## 2026-05-25 20:08 +07
- Task ID: `P1-SEC-001`
- Command: `$env:INTERNAL_SERVICE_TOKEN='test-internal-token-32-bytes-long'; docker compose config --format json`
- Result: pass
- Summary: Rendered Compose config shows only `gateway: 8000->8000`; `postgres`, `scraper`, `sbert`, `ncf`, `dqn`, and `pipeline` have no host ports.
- Related commit hash: `1392e58`.

## 2026-05-25 20:08 +07
- Task ID: `P1-SEC-001`
- Command: `.\.venv\Scripts\python.exe -m json.tool docs\agent\TASK_QUEUE.json`
- Result: pass
- Summary: Durable task queue parsed successfully after marking P1-SEC-001 done.
- Related commit hash: `1392e58`.

## 2026-05-25 20:12 +07
- Task ID: `P1-SEC-002`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_ssrf_guard.py -q`
- Result: fail
- Summary: Expected TDD red failure. The scraper had no `_resolve_host_addresses`, `_validate_scrape_url`, or `_fetch_safe_url` helpers yet.
- Related commit hash: `be52d4f`.

## 2026-05-25 20:14 +07
- Task ID: `P1-SEC-002`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_ssrf_guard.py -q`
- Result: fail
- Summary: Initial implementation blocked `id.jobstreet.com`; allowlist needed to include the existing `jobstreet.com` seed host suffix.
- Related commit hash: `be52d4f`.

## 2026-05-25 20:14 +07
- Task ID: `P1-SEC-002`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_ssrf_guard.py -q`
- Result: pass
- Summary: `9 passed in 0.24s`.
- Related commit hash: `be52d4f`.

## 2026-05-25 20:15 +07
- Task ID: `P1-SEC-002`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_red_team_failure_modes.py::test_scraper_handles_zero_partial_duplicate_and_blocked_sources -q`
- Result: fail
- Summary: Existing red-team test still expected a `502 fetch failed`; new guard correctly returns `400` before outbound fetch.
- Related commit hash: `be52d4f`.

## 2026-05-25 20:15 +07
- Task ID: `P1-SEC-002`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_red_team_failure_modes.py::test_scraper_handles_zero_partial_duplicate_and_blocked_sources -q`
- Result: pass
- Summary: `1 passed in 4.76s` after updating the expected localhost-block contract to `400`.
- Related commit hash: `be52d4f`.

## 2026-05-25 20:17 +07
- Task ID: `P1-SEC-002`
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
- Result: pass
- Summary: `303 passed, 11 warnings in 92.78s`.
- Related commit hash: `be52d4f`.

## 2026-05-25 20:17 +07
- Task ID: `P1-SEC-002`
- Command: `.\.venv\Scripts\python.exe -m json.tool docs\agent\TASK_QUEUE.json`
- Result: pass
- Summary: Durable task queue parsed successfully after marking P1-SEC-002 done.
- Related commit hash: `be52d4f`.

## 2026-05-25 20:19 +07
- Task ID: `P1-SEC-003`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_pipeline_execution_auth.py -q`
- Result: fail
- Summary: Expected TDD red failure. Direct `/pipeline/run` returned 200 without credentials because the route had no auth dependency.
- Related commit hash: `8c4f9b1`.

## 2026-05-25 20:20 +07
- Task ID: `P1-SEC-003`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_pipeline_execution_auth.py -q`
- Result: pass
- Summary: `1 passed in 0.03s`.
- Related commit hash: `8c4f9b1`.

## 2026-05-25 20:23 +07
- Task ID: `P1-SEC-003`
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
- Result: pass
- Summary: `304 passed, 11 warnings in 93.32s`.
- Related commit hash: `8c4f9b1`.

## 2026-05-25 20:23 +07
- Task ID: `P1-SEC-003`
- Command: `.\.venv\Scripts\python.exe -m json.tool docs\agent\TASK_QUEUE.json`
- Result: pass
- Summary: Durable task queue parsed successfully after marking P1-SEC-003 done.
- Related commit hash: `8c4f9b1`.

## 2026-05-25 20:24 +07
- Task ID: `P1-CI-001`
- Command: `.\.venv\Scripts\python.exe -m json.tool docs\agent\TASK_QUEUE.json`
- Result: pass
- Summary: Durable task queue parsed successfully after marking P1-CI-001 in progress for the survival checkpoint.
- Related commit hash: pending checkpoint commit.

## 2026-05-25 20:25 +07
- Task ID: `P1-CI-001`
- Command: `.\.venv\Scripts\python.exe -c "import pathlib, yaml; yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text(encoding='utf-8')); print('workflow yaml ok')"`
- Result: pass
- Summary: Workflow YAML parsed successfully.
- Related commit hash: `7ee1e4d`.

## 2026-05-25 20:26 +07
- Task ID: `P1-CI-001`
- Command: `.\.venv\Scripts\python.exe -m pip check`
- Result: pass
- Summary: No broken requirements found.
- Related commit hash: `7ee1e4d`.

## 2026-05-25 20:26 +07
- Task ID: `P1-CI-001`
- Command: `.\.venv\Scripts\python.exe -m alembic -c alembic.ini heads`
- Result: pass
- Summary: Alembic reports `008_feature_extension_foundation (head)`.
- Related commit hash: `7ee1e4d`.

## 2026-05-25 20:26 +07
- Task ID: `P1-CI-001`
- Command: `.\.venv\Scripts\python.exe scripts\verify_project.py --only import compile`
- Result: pass
- Summary: Import checks and compileall passed for services, scripts, and tests.
- Related commit hash: `7ee1e4d`.

## 2026-05-25 20:28 +07
- Task ID: `P1-CI-001`
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
- Result: pass
- Summary: `304 passed, 11 warnings in 93.76s`.
- Related commit hash: `7ee1e4d`.

## 2026-05-25 20:29 +07
- Task ID: `P1-CI-001`
- Command: `npm run lint` in `frontend/`
- Result: pass
- Summary: Lint exited 0 with 18 warnings and no errors.
- Related commit hash: `7ee1e4d`.

## 2026-05-25 20:30 +07
- Task ID: `P1-CI-001`
- Command: `npm run build` in `frontend/`
- Result: pass
- Summary: Next.js 16.2.6 build compiled successfully, TypeScript completed, and 12 static pages generated.
- Related commit hash: `7ee1e4d`.

## 2026-05-25 20:30 +07
- Task ID: `P1-CI-001`
- Command: `.\.venv\Scripts\python.exe -m json.tool docs\agent\TASK_QUEUE.json`
- Result: pass
- Summary: Durable task queue parsed successfully after marking P1-CI-001 done.
- Related commit hash: `7ee1e4d`.

## 2026-05-25 20:32 +07
- Task ID: `P1-PERF-001`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_sbert_job_embedding_cache.py -q`
- Result: fail
- Summary: Expected TDD red failure. The encode stage had no `_job_text_hash` helper and reused stale job embeddings when only the job text changed.
- Related commit hash: `f167a99`.

## 2026-05-25 20:33 +07
- Task ID: `P1-PERF-001`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_sbert_job_embedding_cache.py -q`
- Result: pass
- Summary: `2 passed in 0.04s`.
- Related commit hash: `f167a99`.

## 2026-05-25 20:33 +07
- Task ID: `P1-PERF-001`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_caching.py -q`
- Result: pass
- Summary: `15 passed in 0.24s`.
- Related commit hash: `f167a99`.

## 2026-05-25 20:33 +07
- Task ID: `P1-PERF-001`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_pipeline_contracts.py -q`
- Result: pass
- Summary: `2 passed in 0.05s`.
- Related commit hash: `f167a99`.

## 2026-05-25 20:36 +07
- Task ID: `P1-PERF-001`
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
- Result: pass
- Summary: `306 passed, 11 warnings in 91.17s`.
- Related commit hash: `f167a99`.

## 2026-05-25 20:36 +07
- Task ID: `P1-PERF-001`
- Command: `.\.venv\Scripts\python.exe -m json.tool docs\agent\TASK_QUEUE.json`
- Result: pass
- Summary: Durable task queue parsed successfully after marking P1-PERF-001 done.
- Related commit hash: `f167a99`.

## 2026-05-25 20:38 +07
- Task ID: `P1-PERF-002`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_dqn_policy_contracts.py -q`
- Result: fail
- Summary: Expected TDD red failure. DQN rank made six policy-network forward calls for three jobs instead of one batched call.
- Related commit hash: pending batch scoring commit.

## 2026-05-25 20:39 +07
- Task ID: `P1-PERF-002`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_dqn_policy_contracts.py -q`
- Result: pass
- Summary: `3 passed in 3.84s`.
- Related commit hash: pending batch scoring commit.

## 2026-05-25 20:40 +07
- Task ID: `P1-PERF-002`
- Command: `.\.venv\Scripts\python.exe -m pytest tests\test_ncf_neumf_contracts.py -q`
- Result: pass
- Summary: `4 passed in 3.98s`.
- Related commit hash: pending batch scoring commit.

## 2026-05-25 20:42 +07
- Task ID: `P1-PERF-002`
- Command: `.\.venv\Scripts\python.exe -m pytest -q`
- Result: pass
- Summary: `307 passed, 11 warnings in 91.10s`.
- Related commit hash: pending batch scoring commit.

## 2026-05-25 20:42 +07
- Task ID: `P1-PERF-002`
- Command: `.\.venv\Scripts\python.exe -m json.tool docs\agent\TASK_QUEUE.json`
- Result: pass
- Summary: Durable task queue parsed successfully after marking P1-PERF-002 done.
- Related commit hash: pending batch scoring commit.
