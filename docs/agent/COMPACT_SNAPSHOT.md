# Compact Snapshot

Updated: 2026-05-31 09:55 +07

## Current Objective
Run `DEBUG-ULT-001`, an evidence-based full-stack debugging session covering frontend, backend/API, ML services, pipeline, database, Docker, browser flows, and security.

## Current Phase
debug hypothesis generation / browser harness setup

## Current Task ID
DEBUG-ULT-001

## Latest Commit Hash
Root: `0b55041` (`docs: initialize ultimate debugging session`).

## Current Git Branch
`agent-run`

## Dirty Files
- Pre-existing root: `README.md`, `SCPAv2`, `notebooks/01_indonesian_hybrid_dataset_eda.ipynb`, and `notebooks/02_hybrid_dataset_validation.ipynb` were modified before this session.
- Pre-existing root: many untracked project files/directories remain part of the live project and must not be bulk staged.
- Pre-existing nested `frontend/` repo is dirty and must be committed separately if frontend code changes are made.
- Current task owns only the new/updated `docs/debug/` and `docs/agent/` debug-session state until evidence justifies product changes.

## Files Changed This Session
- `docs/debug/DEBUG_MASTER_PLAN.md`
- `docs/debug/DEBUG_INVENTORY.md`
- `docs/debug/DEBUG_HYPOTHESES.md`
- `docs/debug/DEBUG_EVIDENCE.md`
- `docs/debug/DEBUG_FIX_LOG.md`
- `docs/debug/DEBUG_VALIDATION_LEDGER.md`
- `docs/debug/DEBUG_BROWSER_REPORT.md`
- `docs/debug/DEBUG_MODEL_REPORT.md`
- `docs/debug/DEBUG_API_REPORT.md`
- `docs/debug/DEBUG_FRONTEND_REPORT.md`
- `docs/debug/DEBUG_BACKEND_REPORT.md`
- `docs/debug/DEBUG_DATABASE_REPORT.md`
- `docs/debug/DEBUG_DOCKER_REPORT.md`
- `docs/debug/DEBUG_SECURITY_REPORT.md`
- `docs/debug/COMPACT_RECOVERY.md`
- `docs/agent/TASK_QUEUE.json`
- `docs/agent/COMPACT_SNAPSHOT.md`
- `docs/agent/PROJECT_STATE.md`
- `docs/agent/SESSION_REPORT.md`
- `docs/agent/DECISION_LOG.md`
- `docs/agent/VALIDATION_LEDGER.md`

## Current Implementation Status
- Debug documentation has been initialized and committed.
- Static inventory and baseline validation have been recorded in `docs/debug/`.
- No product code has been changed.
- `morph-mcp` was requested but is not exposed as a callable tool in this session.

## Commands Already Run
- `git status --short --branch`
- `tool_search morph-mcp`
- `.\.venv\Scripts\python.exe -m pytest --collect-only -q` -> 389 collected.
- `.\.venv\Scripts\python.exe -m alembic -c alembic.ini heads` -> `012_ab_testing_and_monitoring`.
- `.\.venv\Scripts\python.exe -m pytest -q` -> 389 passed, 3 warnings.
- `npm run lint` -> passed with 16 warnings.
- `npm run build` -> passed.
- `docker compose config --quiet` -> passed.
- `docker compose up -d --build` -> failed at gateway dependency layer.

## Validation Results
- Backend import/compile and pytest passed.
- Frontend lint/build passed.
- Docker compose config passed.
- Docker rebuild failed: gateway build copies root `requirements.txt`, but the referenced `requirements-db.txt` is not copied before `pip install`.

## Known Errors
- Confirmed: current Docker gateway rebuild fails at dependency install.
- Confirmed: root `.dockerignore` is missing and gateway build context transfer reached about 5.06GB.
- Confirmed: `localhost:8000/health` refused while gateway is currently reachable on `localhost:9000`.
- Confirmed: existing gateway container lacks the `alembic` module, so container-local migration validation failed.

## Do-Not-Change Constraints
- Do not stage or revert pre-existing root `README.md`, `SCPAv2`, notebooks, or broad untracked project files unless the active debug task explicitly owns them.
- Do not stage or revert unrelated nested frontend dirty files.
- Frontend code must be committed inside `frontend/` first, then mirrored in root durable state.
- Do not fix before collecting reproduction evidence and root-cause notes.
- Do not claim all validation passed unless each command actually ran in this session.

## Next Exact Action
Commit static inventory, baseline validation, and hypotheses, then add and run `scripts/debug/selenium_full_audit.py`.
