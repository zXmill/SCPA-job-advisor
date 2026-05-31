# Debug Validation Ledger

Updated: 2026-05-31 09:12 +07

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
