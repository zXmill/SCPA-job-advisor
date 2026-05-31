# Debug Validation Ledger

Updated: 2026-05-31 14:56 +07

| Timestamp | Command | Result | Related ID | Summary |
| --- | --- | --- | --- | --- |
| 2026-05-31 09:12 +07 | `git status --short --branch` | pass | DEBUG-ULT-001 | Confirmed the repo was dirty before debug-session docs were created. |
| 2026-05-31 09:12 +07 | `tool_search morph-mcp` | not available | DEBUG-ULT-001 | No callable morph edit tool was exposed; use normal local editing tools. |
| 2026-05-31 09:12 +07 | `.\.venv\Scripts\python.exe -m json.tool docs\agent\TASK_QUEUE.json` | pass | DEBUG-ULT-001 | Durable task queue parsed after adding `DEBUG-ULT-001`. |
| 2026-05-31 09:22 +07 | `.\.venv\Scripts\python.exe -m pytest --collect-only -q` | pass | BASELINE | 389 tests collected in 8.64s. |
| 2026-05-31 09:22 +07 | `.\.venv\Scripts\python.exe -m alembic -c alembic.ini heads` | pass | DB-BASELINE | Reported `012_ab_testing_and_monitoring (head)`. |
| 2026-05-31 09:22 +07 | `docker compose config --services` | pass | DOCKER-BASELINE | Resolved services: postgres, sbert, scraper, dqn, ncf, pipeline, gateway. |
| 2026-05-31 09:22 +07 | `docker --version; docker compose version` | pass | DOCKER-BASELINE | Docker 29.1.2 and Compose v2.40.3 are available. |
| 2026-05-31 09:30 +07 | `.\.venv\Scripts\python.exe -m pytest -q` | pass | BACKEND-BASELINE | 389 passed, 3 warnings in 205.51s. |
| 2026-05-31 09:34 +07 | `npm run lint` in `frontend/` | pass | FRONTEND-BASELINE | ESLint returned 0 errors and 16 warnings. |
| 2026-05-31 09:36 +07 | `npm run build` in `frontend/` | pass | FRONTEND-BASELINE | Next.js 16.2.6 production build completed. |
| 2026-05-31 09:37 +07 | `docker compose config --quiet` | pass | DOCKER-BASELINE | Compose file validated with dummy required env vars. |
| 2026-05-31 09:47 +07 | `docker compose up -d --build` | fail | H1-DOCKER-GATEWAY-REQ | Gateway image build failed because pip could not open `requirements-db.txt`; build context transfer reached about 5.06GB. |
| 2026-05-31 09:49 +07 | `.\.venv\Scripts\python.exe scripts\verify_project.py --only import compile` | pass | BACKEND-BASELINE | Selected imports and compileall passed. |
| 2026-05-31 09:49 +07 | `Invoke-WebRequest http://127.0.0.1:9000/health` | pass | RUNTIME-BASELINE | Existing gateway container returned healthy on port 9000. |
| 2026-05-31 09:49 +07 | `Invoke-WebRequest http://127.0.0.1:8000/health` | fail | H3-DOCKER-PORTS | No listener on port 8000. |
| 2026-05-31 09:49 +07 | `Invoke-WebRequest http://127.0.0.1:3000` | pass | FRONTEND-BASELINE | Existing Next dev server returned 200. |
| 2026-05-31 09:51 +07 | `docker compose exec -T postgres pg_isready -U postgres -d db_scpa` | pass | DB-BASELINE | Existing postgres container accepted connections. |
| 2026-05-31 09:51 +07 | `docker compose exec -T gateway python -m alembic -c alembic.ini heads` | fail | H1-DB-MIGRATION-RUNTIME | Existing gateway image does not include the `alembic` module. |
| 2026-05-31 09:51 +07 | `Invoke-WebRequest http://127.0.0.1:9000/ready` | pass | RUNTIME-BASELINE | Existing gateway reported pipeline healthy; not accepted as current rebuild proof. |
| 2026-05-31 09:58 +07 | `.\.venv\Scripts\python.exe -m py_compile scripts\debug\selenium_full_audit.py` | pass | BROWSER-AUDIT | Selenium audit harness compiled. |
| 2026-05-31 10:02 +07 | `python scripts\debug\selenium_full_audit.py --base-url http://127.0.0.1:3001 ...` | pass | BROWSER-AUDIT | Production cross-check loaded 9 routes with 0 console errors, 0 network failures, 0 blank pages; login failed due origin/API mismatch. |
| 2026-05-31 10:03 +07 | `python scripts\debug\selenium_full_audit.py --base-url http://localhost:3000 --api-base http://localhost:9000 ...` | pass | BROWSER-AUDIT | Authenticated dev-origin audit loaded 9 routes with 0 console errors, 0 network failures, 0 blank pages. |
| 2026-05-31 10:05 +07 | `python scripts\debug\selenium_full_audit.py --output reports\debug\browser --settle-seconds 7 ...` | fail | BROWSER-FEEDBACK-500 | Longer authenticated audit found `POST /api/recommendations/feedback` returning HTTP 500 during recommendation impression tracking. |
| 2026-05-31 10:12 +07 | `.\.venv\Scripts\python.exe -m pytest tests\test_recommendation_feedback_slate.py -q` | fail | H4-API-FEEDBACK-SLATE-FK | Focused pre-fix regression reproduced the missing served-slate persistence: `served_slates` count was 0 after `/api/recommendations`. |
| 2026-05-31 10:16 +07 | `.\.venv\Scripts\python.exe -m py_compile services\gateway\main.py tests\conftest.py tests\test_recommendation_feedback_slate.py` | pass | FIX-API-FEEDBACK-SLATE | Changed Python files compile. |
| 2026-05-31 10:17 +07 | `.\.venv\Scripts\python.exe -m pytest tests\test_recommendation_feedback_slate.py -q` | pass | FIX-API-FEEDBACK-SLATE | Focused regression passed: recommendation response persisted a served slate and subsequent feedback insert returned 200. |
| 2026-05-31 10:19 +07 | `.\.venv\Scripts\python.exe -m pytest tests\test_recommendation_feedback_slate.py tests\test_recommendation_reason_filters.py tests\test_feedback_outbox.py tests\test_pipeline_contracts.py -q` | pass | FIX-API-FEEDBACK-SLATE | Adjacent backend recommendation/pipeline tests passed: 6 passed, 1 warning. |
| 2026-05-31 10:27 +07 | `.\.venv\Scripts\python.exe -m pytest -q` | pass | FIX-API-FEEDBACK-SLATE | Full backend suite passed: 390 passed, 3 warnings in 223.23s. |
| 2026-05-31 10:33 +07 | `docker compose build gateway` | pass | FIX-DOCKER-RUNTIME-BUILD | Gateway image built; root context transfer dropped to 286.56KB on direct build. |
| 2026-05-31 10:34 +07 | `docker run --rm ... scpa-gateway python -c "import services.gateway.main as gateway; print(gateway.app.title)"` | pass | FIX-DOCKER-RUNTIME-BUILD | Gateway package import smoke passed inside the image. |
| 2026-05-31 10:36 +07 | `docker compose up -d --build gateway` | fail | H5-DOCKER-PIPELINE-PACKAGE | Gateway built, but pipeline became unhealthy with `ModuleNotFoundError: No module named 'services'`. |
| 2026-05-31 10:39 +07 | `docker compose up -d --build gateway` | pass | FIX-DOCKER-RUNTIME-BUILD | Gateway and dependencies built and started after pipeline package-entrypoint repair. |
| 2026-05-31 10:40 +07 | `.\.venv\Scripts\python.exe -m alembic -c alembic.ini current` | fail | H2-DB-SCHEMA-HEAD-DRIFT | Live database reported `001_initial_schema`, below repo head. |
| 2026-05-31 10:41 +07 | `.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head` | pass | DB-MIGRATION-RUNTIME | Applied migrations through `012_ab_testing_and_monitoring`. |
| 2026-05-31 10:41 +07 | `.\.venv\Scripts\python.exe -m alembic -c alembic.ini current` | pass | DB-MIGRATION-RUNTIME | Live database now reports `012_ab_testing_and_monitoring (head)`. |
| 2026-05-31 10:42 +07 | `docker compose up -d --build` | pass | FIX-DOCKER-RUNTIME-BUILD | Full project-level compose build/up passed. |
| 2026-05-31 10:43 +07 | `docker compose ps`; gateway `/health`; gateway `/ready` | pass | RUNTIME-VERIFY | All services healthy; gateway health and readiness passed on port 9000. |
| 2026-05-31 10:46 +07 | `.\.venv\Scripts\python.exe scripts\debug\selenium_full_audit.py --output reports\debug\browser --headless --email <demo-email> --password <redacted> --settle-seconds 7` | pass | BROWSER-AUDIT-FINAL | Final authenticated browser audit passed: 9 pages, 0 console errors, 0 network failures, 0 blank pages, 0 hydration errors. |
| 2026-05-31 10:47 +07 | `rg "password123|access_token|Authorization|Bearer |eyJ" reports\debug\browser scripts\debug\selenium_full_audit.py` | pass | SECRET-SCAN | No password, token, authorization header, or JWT-like strings found in browser artifacts/harness. |
| 2026-05-31 14:56 +07 | `git log --oneline -10`; `git status --short --branch`; required `docs/debug/*.md` reads | pass | STATE-RECONCILIATION | Reconciled stale debug docs: latest commit is `f77445b`, served-slate browser re-check passed, and Docker/runtime fix is already committed and verified. |
