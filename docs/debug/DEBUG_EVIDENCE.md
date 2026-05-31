# Debug Evidence

Updated: 2026-05-31 10:20 +07

## Bootstrap Evidence
- Repository cwd: `E:\TUGAS AKHIR\SCPA`.
- Branch: `agent-run`.
- Start commit: `79b1614`.
- Initial worktree: dirty before this session with modified `README.md`, modified `SCPAv2`, modified notebooks, many untracked project files, and a dirty nested `frontend/` repository.
- Existing debug doc found: `docs/debug/BROWSER_E2E_ARCHITECTURE_REVIEW.md`.
- `morph-mcp`: requested by prompt, but no callable morph tool was exposed by current tool discovery; normal local edit tooling is used.

## Evidence Index
- Browser artifacts: pending, target `reports/debug/browser/`.
- API artifacts: focused API/database regression evidence collected for `H4-API-FEEDBACK-SLATE-FK`.
- Model artifacts: pending.
- Database artifacts: pending.
- Docker artifacts: pending.
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
