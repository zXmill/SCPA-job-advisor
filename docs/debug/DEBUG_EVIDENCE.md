# Debug Evidence

Updated: 2026-05-31 15:20 +07

## Bootstrap Evidence
- Repository cwd: `E:\TUGAS AKHIR\SCPA`.
- Branch: `agent-run`.
- Start commit: `79b1614`.
- Initial worktree: dirty before this session with modified `README.md`, modified `SCPAv2`, modified notebooks, many untracked project files, and a dirty nested `frontend/` repository.
- Existing debug doc found: `docs/debug/BROWSER_E2E_ARCHITECTURE_REVIEW.md`.
- `morph-mcp`: requested by prompt, but no callable morph tool was exposed by current tool discovery; normal local edit tooling is used.

## Evidence Index
- Browser artifacts: final authenticated Selenium audit saved under `reports/debug/browser/`.
- API artifacts: gateway runtime probe artifacts under `reports/debug/api/`; final fixed run is `gateway_runtime_probe_20260531T081953Z.json` plus matching `.log`.
- Model artifacts: pending.
- Database artifacts: live Alembic current/upgrade/current validation recorded.
- Docker artifacts: compose build/up, service health, and browser re-check recorded.
- Security artifacts: pending.

## Baseline Evidence
- `pytest --collect-only -q`: pass, 389 tests collected in 8.64s.
- `alembic heads`: pass, head `012_ab_testing_and_monitoring`.
- `docker compose config --services`: pass, services `postgres`, `sbert`, `scraper`, `dqn`, `ncf`, `pipeline`, `gateway`.
- `docker compose config --quiet`: pass with dummy required env vars.
- `python scripts/verify_project.py --only import compile`: pass for selected service/script imports and compileall.
- `python -m pytest -q`: pass, 389 passed, 3 warnings in 205.51s.
- `npm run lint` in `frontend/`: pass, 0 errors, 16 warnings.
- `npm run build` in `frontend/`: pass, Next.js 16.2.6 built 12 static pages plus dynamic `/jobs/[id]`.
- `docker compose up -d --build`: fail while rebuilding gateway. Evidence: gateway build transferred about 5.06GB of context, then pip failed with `Could not open requirements file: requirements-db.txt`.
- Existing runtime probe: `http://127.0.0.1:9000/health` returned gateway healthy; `http://127.0.0.1:8000/health` refused connection; `http://127.0.0.1:3000` returned 200 from an existing Next dev server started from this checkout.
- Existing runtime probe: `http://127.0.0.1:9000/ready` returned gateway ready and pipeline healthy, but these containers predate the failed rebuild and are not proof that the current Docker build works.

## Browser Evidence
- `scripts/debug/selenium_full_audit.py` compiled and ran.
- Initial `127.0.0.1:3000` dev audit produced HMR WebSocket false positives and blank screenshots; canonical origin was changed to `localhost`.
- Production cross-check on `127.0.0.1:3001` showed 0 console errors, 0 network failures, 0 blank pages, but login failed due origin/API mismatch.
- Canonical authenticated audit on `http://localhost:3000` with `http://localhost:9000` succeeded for login and loaded all 9 routes with no blank pages or hydration errors.
- Canonical authenticated audit reproduced one product failure: `POST /api/recommendations/feedback` returned HTTP 500 from `/recommendations`.
- Gateway logs for that failure show `asyncpg.exceptions.ForeignKeyViolationError` on `feedback_events_slate_id_fkey`: the slate ID sent by the frontend is not present in `served_slates`.

## Feedback Slate Evidence
- Focused pre-fix regression: `tests\test_recommendation_feedback_slate.py` failed because `served_slates` count was 0 immediately after `/api/recommendations`.
- Root cause confirmed in current source: the gateway returned a generated slate ID but did not write `served_slates`/`served_slate_items`.
- Current-source fix validation:
  - `py_compile` passed for `services\gateway\main.py`, `tests\conftest.py`, and `tests\test_recommendation_feedback_slate.py`.
  - Focused regression passed.
  - Adjacent recommendation/pipeline suite passed with 6 tests.
  - Full backend suite passed with 390 tests.
- Browser re-verification of the fix is pending because the live browser target currently uses an existing/stale gateway container and the current Docker gateway rebuild is separately broken.

## Docker And Runtime Evidence
- `docker compose build gateway`: pass. Gateway context dropped from prior 5.06GB failure to 286.56KB; image built successfully.
- `docker run --rm ... scpa-gateway python -c "import services.gateway.main as gateway; print(gateway.app.title)"`: pass, printed `SCPA Gateway`.
- First `docker compose up -d --build gateway` after gateway repair built images but failed because `scpa-pipeline-1` was unhealthy.
- Pipeline logs showed `ModuleNotFoundError: No module named 'services'` from `stage_5_aggregate.py`.
- After pipeline Dockerfile/package-entrypoint repair, `docker compose up -d --build` passed and all services were healthy.
- Gateway health and readiness probes passed on port 9000.

## Database Migration Evidence
- `alembic current` before upgrade: `001_initial_schema`.
- `alembic upgrade head`: pass, applied migrations through `012_ab_testing_and_monitoring`.
- `alembic current` after upgrade: `012_ab_testing_and_monitoring (head)`.
- API-phase reconciliation found the running Docker PostgreSQL container still at `011_job_alerts` with no `experiments` tables. The existing `012_ab_testing_and_monitoring` DDL was applied through `docker compose exec -T postgres psql` because the gateway image intentionally lacks Alembic and Postgres is not host-exposed.
- Post-repair Docker DB checks returned `012_ab_testing_and_monitoring`, `experiments`, `experiment_assignments`, and `experiment_metrics`.

## Final Browser Evidence
- Final authenticated Selenium audit against the rebuilt Docker runtime: 9 pages, 0 console errors, 0 network failures, 0 blank pages, 0 hydration errors.
- Report artifact secret scan found no password, bearer token, authorization header, JWT-like token, or access-token strings.

## API Runtime Probe Evidence
- `scripts/debug/api_runtime_probe.py` compiled and ran against `http://127.0.0.1:9000`.
- Pre-fix corrected probe after Docker DB 012 repair: `reports/debug/api/gateway_runtime_probe_20260531T080750Z.json`, 83 total, 81 passed, 2 failed, HTTP 5xx cases `APPLICATIONS-CREATE-MISSING-JOB` and `FEEDBACK-MISSING-SLATE`.
- Pre-fix gateway logs confirmed:
  - `applications_job_id_fkey` for invalid application job IDs.
  - `feedback_events_slate_id_fkey` for unknown served-slate IDs.
  - asyncpg `DataError` when recommendation job upsert received ISO string `posted_at`.
- Post-fix local validation passed:
  - Focused red-to-green: `tests\test_gateway_api_runtime_guards.py tests\test_recommendation_feedback_slate.py::test_feedback_with_unknown_served_slate_returns_404 -q` -> 3 passed.
  - Adjacent suite: `tests\test_gateway_api_runtime_guards.py tests\test_recommendation_feedback_slate.py tests\test_feedback_outbox.py tests\test_saved_jobs_skip.py -q` -> 10 passed.
- Post-fix Docker validation:
  - `docker compose up -d --build gateway` passed and rebuilt the gateway plus dependent service images.
  - `docker compose ps` showed all services healthy.
  - Gateway `/health` returned healthy.
  - Final API probe `reports/debug/api/gateway_runtime_probe_20260531T081953Z.json` passed 83/83 with 0 HTTP 5xx.
  - Final API artifact secret scan found no password, bearer token, authorization header, JWT-like token, or access-token strings.
