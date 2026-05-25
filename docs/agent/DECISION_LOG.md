# Decision Log

## 2026-05-25 19:33 +07 - Initializer operating mode
- Decision: Create permanent lightweight instructions in `AGENTS.md` and durable task/state files under `docs/agent/` before product changes.
- Reason: The user requested a long-running workflow that survives compaction and interruption.
- Trade-off: This duplicates some information from existing docs, but keeps agent state in one predictable location.
- Skipped option: Storing the full task plan in `AGENTS.md`; it belongs in `TASK_QUEUE.json`.
- Risk and mitigation: Repo was already dirty. Stage only the new initializer files and record pre-existing dirty state.

## 2026-05-25 19:33 +07 - Worktree and subagent constraints
- Decision: Work in the current `agent-run` checkout for the initializer and do not create a new git worktree.
- Reason: The user explicitly instructed this repository to be the source of truth and requested commits here. Superpowers worktree guidance requires consent before creating a new worktree when none exists.
- Skipped option: Spawn subagents for parallel reconnaissance.
- Reason skipped: Subagent tooling is available, but this environment only permits spawning when the user explicitly asks for sub-agents, delegation, or parallel agent work.
- Risk and mitigation: Keep tasks narrow, commit frequently, and update `COMPACT_SNAPSHOT.md` before larger work.

## 2026-05-25 19:33 +07 - Initial task ordering
- Decision: Use `reports/full_code_review_research_potential_report.md` as guidance only, then verify each claim against current files before product changes.
- Reason: The user named the report as a reference and also said repository files are source of truth.
- Next: Complete `INIT-001`, then start `P0-001` cleanup audit.

## 2026-05-25 19:48 +07 - P0-001 cleanup audit mini plan
- Decision: Perform a read-only repository cleanup audit before any safe cleanup.
- Expected files to touch: `docs/agent/CLEANUP_AUDIT.md`, `docs/agent/TASK_QUEUE.json`, `docs/agent/DECISION_LOG.md`, `docs/agent/SESSION_REPORT.md`, `docs/agent/COMPACT_SNAPSHOT.md`, `docs/agent/VALIDATION_LEDGER.md`, and `docs/agent/PROJECT_STATE.md` if findings change known state.
- Validation commands: `git status --short --branch`, plus JSON parse for `TASK_QUEUE.json`.
- Skipped option: Moving or deleting files during the audit.
- Risk and mitigation: The repo is mostly untracked, so classify conservatively and put ambiguous items under `Unsure`.

## 2026-05-25 20:02 +07 - P0-002 safe cleanup mini plan
- Decision: Limit safe cleanup to small root-level manual debug artifacts: `browser_e2e.py`, `check_overflow.py`, `check_scrape.py`, `insert_scraped.py`, and `scrape_1000.json`.
- Expected files to touch: `testing/archive/manual-debug/`, `docs/agent/TASK_QUEUE.json`, `docs/agent/SESSION_REPORT.md`, `docs/agent/COMPACT_SNAPSHOT.md`, `docs/agent/VALIDATION_LEDGER.md`, and `docs/agent/FAILURE_LEDGER.md` if validation fails.
- Validation commands: `.\.venv\Scripts\python.exe -m pytest -q`, `npm run lint` in `frontend/`, `npm run build` in `frontend/`, `docker compose config --quiet`, `python -m json.tool docs/agent/TASK_QUEUE.json`, and `git status --short --branch`.
- Skipped option: Moving `SCPAv2/`, notebooks, reports, screenshots, PDFs, service scripts, migrations, or source directories in the first cleanup pass.
- Risk and mitigation: Frontend lint is already known to fail on a hook-order issue. If it fails, record the failure and treat the hook fix as the validation blocker.

## 2026-05-25 20:12 +07 - Promote P0-FE-001 to unblock cleanup validation
- Decision: Pause `P0-002` as blocked and promote `P0-FE-001` to active.
- Reason: `npm run lint` failed during P0-002 validation on the known hook-order issue in `frontend/src/app/recommendations/page.tsx`.
- Root cause: `markImpressed = useCallback(...)` is declared after the auth early return, so React hook order changes across renders.
- Test-first evidence: `npm run lint` failed with `react-hooks/rules-of-hooks` at `recommendations/page.tsx:329`.
- Mitigation: Make the minimal hook-order move, run `npm run lint` and `npm run build`, commit the frontend fix, then return to P0-002 validation.

## 2026-05-25 20:28 +07 - Frontend nested repository commit
- Decision: Commit `P0-FE-001` inside the nested `frontend/` Git repository.
- Reason: `frontend/` contains its own `.git`, so the root repo cannot stage `frontend/src/app/recommendations/page.tsx` as a normal tracked file.
- Trade-off: Root durable state needs a separate docs checkpoint to preserve the frontend commit hash.
- Result: Nested frontend commit `6e76e92` with message `fix: resolve frontend hook order violation`.

## 2026-05-25 20:02 +07 - P1-SEC-001 Docker exposure mini plan
- Decision: Restrict Compose host publishing to the public gateway path and add an internal token boundary between gateway and pipeline.
- Expected files to touch: `docker-compose.yml`, `.env.example`, `services/gateway/main.py`, `services/pipeline/main.py`, focused tests if the current test structure supports them, and durable `docs/agent/` state files.
- Validation commands: `docker compose config` with required secret environment variables, focused pytest for the internal auth behavior, and broader pytest if the focused change touches shared behavior.
- Skipped option: Adding token middleware to every model and scraper service in this task.
- Reason skipped: Removing host port publishing already moves scraper/SBERT/NCF/DQN/PostgreSQL behind the Docker network; a gateway-to-pipeline token directly protects the public-to-internal orchestration boundary without expanding this task across many service files.
- Risk and mitigation: Compose may fail if the token is required but missing. Document `INTERNAL_SERVICE_TOKEN` in `.env.example` and set a test value explicitly during validation instead of committing a real secret.

## 2026-05-25 20:10 +07 - P1-SEC-002 SSRF guard mini plan
- Decision: Add an explicit SSRF validation layer for scraper URL fetches before any outbound request.
- Expected files to touch: `services/scraper/main.py`, `tests/test_ssrf_guard.py`, and durable `docs/agent/` state files.
- Validation commands: failing focused SSRF tests first, then `.\.venv\Scripts\python.exe -m pytest tests\test_ssrf_guard.py -q`, and full `.\.venv\Scripts\python.exe -m pytest -q` after implementation.
- Guard requirements: allow only approved job-board hosts; reject localhost, loopback, private IP ranges, link-local addresses, metadata IPs, non-HTTP(S) schemes, unsafe redirects, and DNS rebinding attempts.
- Skipped option: Relying only on Pydantic `HttpUrl`.
- Reason skipped: `HttpUrl` validates shape, not network safety or resolved addresses.
- Risk and mitigation: DNS lookups can be flaky in tests; isolate address resolution behind a small helper and monkeypatch it in SSRF tests.

## 2026-05-25 20:18 +07 - P1-SEC-003 pipeline execution auth mini plan
- Decision: Protect the gateway's direct `/pipeline/run` proxy instead of leaving it public.
- Expected files to touch: `services/gateway/main.py`, focused auth/security tests, and durable `docs/agent/` state files.
- Validation commands: write a failing route-auth test first, then run the focused route test and full `.\.venv\Scripts\python.exe -m pytest -q`.
- Chosen boundary: authenticated admin-only access for the direct pipeline execution route; normal user recommendations continue through `/api/recommendations`, which assembles the profile and applies existing user auth.
- Skipped option: Removing the route outright in this task.
- Reason skipped: Some local/admin scripts may still rely on direct execution; admin gating narrows exposure while preserving an intentional operator path.
- Risk and mitigation: Existing tests may call `/pipeline/run` directly. Update only tests that represent the new security contract.

## 2026-05-25 20:24 +07 - Survival checkpoint and P1-CI-001 mini plan
- Decision: Create a state-only checkpoint after three security commits, then start CI hardening.
- Expected files to touch next: `.github/workflows/ci.yml` and durable `docs/agent/` state files.
- Validation commands: inspect current CI, update workflow to install dependencies and run backend tests, Alembic head/upgrade where feasible, frontend lint, and frontend build; validate workflow YAML shape and run local equivalents already proven for backend/frontend where practical.
- Skipped option: Combining CI hardening with the previous security commits.
- Reason skipped: CI changes are infrastructure work with different validation and should remain a separate checkpoint.
- Risk and mitigation: `.github/workflows/ci.yml` is currently untracked in the root repo; stage only that workflow if it is changed.

## 2026-05-25 20:31 +07 - P1-PERF-001 SBERT cache mini plan
- Decision: Inspect existing SBERT encode/match paths and tests before changing cache behavior.
- Expected files to touch: `services/sbert/main.py`, focused cache tests if needed, and durable `docs/agent/` state files.
- Validation commands: focused SBERT/cache tests first, then full `.\.venv\Scripts\python.exe -m pytest -q`.
- Requirement: cache job embeddings and invalidate when job text changes.
- Skipped option: Adding a database-backed cache before inspecting existing service state.
- Reason skipped: The current SBERT service may already have in-memory or Redis cache hooks; reuse local patterns before adding schema or infrastructure.
- Risk and mitigation: Embedding cache keys must include text content and model/version dimensions so changed job text cannot return stale vectors.

## 2026-05-25 20:37 +07 - P1-PERF-002 batch scoring mini plan
- Decision: Inspect existing NCF and DQN service endpoints plus pipeline stage calls before implementing batch scoring.
- Expected files to touch: `services/pipeline/stages/stage_3_ncf_score.py`, `services/pipeline/stages/stage_4_dqn_rank.py`, service endpoints if batch routes are missing, focused tests, and durable `docs/agent/` state files.
- Validation commands: focused stage/service batch tests first, then full `.\.venv\Scripts\python.exe -m pytest -q`.
- Requirement: batch NeuMF/NCF scoring and DQN scoring where applicable.
- Skipped option: Optimizing model internals before confirming whether the pipeline already calls batch endpoints.
- Reason skipped: The largest latency win may be eliminating per-job HTTP calls, not changing model math.
- Risk and mitigation: Preserve response shape expected by downstream aggregation while adding batch summaries/counters.

## 2026-05-25 20:45 +07 - Survival checkpoint and P1-PERF-003 mini plan
- Decision: Reconcile durable state after the compact and create a state-only survival checkpoint before database index work.
- Expected files to touch next: `db/models.py`, a new Alembic migration under `db/migrations/` if indexes are missing, targeted migration/index tests if existing patterns support them, and durable `docs/agent/` state files.
- Validation commands: inspect current indexes first, then run `.\.venv\Scripts\python.exe -m alembic -c alembic.ini heads` and `.\.venv\Scripts\python.exe -m pytest -q`.
- Requirement: add indexes for hot recommendation paths while avoiding duplicate indexes.
- Skipped option: Adding broad indexes to every foreign key or score column without query evidence.
- Reason skipped: Duplicate or low-value indexes increase write overhead and migration noise.
- Risk and mitigation: Compare `db/models.py`, existing migrations, and recommendation query filters/orderings before creating a migration.

## 2026-05-25 20:57 +07 - P1-PERF-003 index selection
- Decision: Add three partial active-job indexes and one application history index: newest active jobs by `(posted_at DESC, id)`, active source-filtered jobs by `(source, posted_at DESC, id)`, active experience-filtered jobs by `(experience_level, posted_at DESC, id)`, and applications by `(user_id, applied_at DESC)`.
- Evidence: Pipeline candidate loading uses `WHERE is_active = true ORDER BY posted_at DESC LIMIT`; gateway job listing uses active jobs with optional `source`/`experience_level` filters and the same newest-first ordering; application history uses `WHERE a.user_id = :uid ORDER BY a.applied_at DESC`.
- Skipped option: JSONB GIN indexes on `jobs.match_data`.
- Reason skipped: Current hot paths parse `match_data` after primary row retrieval and do not filter JSONB in SQL.
- Skipped option: A B-tree index for leading-wildcard `location ILIKE`.
- Reason skipped: The current query uses `%term%`; B-tree would not be effective without changing the search strategy or adding a trigram extension.
- Risk and mitigation: Added focused ORM metadata assertions and a reversible Alembic migration, then validated upgrade, downgrade, re-upgrade, and full pytest.

## 2026-05-25 20:59 +07 - P1-OBS-001 telemetry mini plan
- Decision: Add in-process pipeline stage latency telemetry for the existing recommendation stages before introducing external observability infrastructure.
- Expected files to touch: `services/pipeline/main.py`, possibly `services/pipeline/stages/` if the stage result shape requires it, `tests/test_pipeline_telemetry.py`, and durable `docs/agent/` state files.
- Validation commands: focused telemetry tests first, then full `.\.venv\Scripts\python.exe -m pytest -q`.
- Requirement: track p50 and p95 per stage for scrape, SBERT, NCF, DQN, calibrator, and aggregation.
- Skipped option: Adding Prometheus/OpenTelemetry dependencies in this task.
- Reason skipped: The code already has timing hooks around stage execution; p50/p95 summaries can be added without new infrastructure or Docker changes.
- Risk and mitigation: Preserve the existing pipeline response contract and add telemetry as additive metadata.

## 2026-05-25 21:05 +07 - P1-OBS-001 telemetry design
- Decision: Keep per-stage latency samples in bounded in-process deques and expose p50/p95 snapshots through `/health` and `stages["telemetry"]` in pipeline responses.
- Stage mapping: `scrape` stays `scrape`; `encode` reports as `sbert`; `ncf_score` reports as `ncf`; `dqn_rank` reports as `dqn`; `aggregate` reports as `aggregation`.
- Calibrator treatment: record a `calibrator` stage with `0.0 ms` and `mode=static_baseline` until the learned calibration task is implemented.
- Skipped option: Renaming existing `timings_ms` keys.
- Reason skipped: Existing clients may depend on `encode`, `ncf_score`, `dqn_rank`, and `aggregate`; telemetry aliases are additive.
- Risk and mitigation: Added a response-contract test and reran existing pipeline contracts plus full pytest.

## 2026-05-25 21:07 +07 - P2-001 JWT validation mini plan
- Decision: Validate JWT secret configuration at auth module initialization so weak or missing secrets fail before tokens are issued.
- Expected files to touch: `services/shared/auth.py`, focused security tests, and durable `docs/agent/` state files.
- Validation commands: focused JWT/security tests first, then full `.\.venv\Scripts\python.exe -m pytest -q`.
- Requirement: fail fast if `JWT_SECRET` is missing or shorter than 32 bytes; preserve testability through explicit test overrides.
- Skipped option: Only warning on weak secrets.
- Reason skipped: The task explicitly requires fail-fast behavior.
- Risk and mitigation: Existing tests intentionally use short secrets; update tests to use a valid default where they are not testing rejection and add focused checks for missing/short configuration.

## 2026-05-25 21:05 +07 - P2-001 JWT validation design
- Decision: Centralize JWT signing-secret validation in `services/shared/auth.py` and reuse it from the gateway's module-level configuration.
- Access and refresh secrets: Both must be configured and at least 32 bytes because both sign bearer credentials.
- Fail-fast point: Shared auth validates environment-derived defaults at import time, while `TokenManager` validates explicit constructor overrides immediately.
- Skipped option: Deferring validation until token creation or verification.
- Reason skipped: Runtime issuance-time failures do not catch a weak deployment configuration early enough.
- Risk and mitigation: Test modules now force deterministic 32-byte-or-longer JWT secrets in `tests/conftest.py`; focused and full pytest validation passed after the change.

## 2026-05-25 21:06 +07 - Survival checkpoint and P2-002 CORS hardening mini plan
- Decision: Create a state-only checkpoint after the third post-checkpoint commit, then start `P2-002`.
- Expected files to touch next: `services/gateway/main.py`, `.env.example`, `docker-compose.yml` if environment wiring changes, focused CORS tests, and durable `docs/agent/` state files.
- Validation commands: focused CORS tests first, then `.\.venv\Scripts\python.exe -m pytest -q` and `docker compose config` with required environment variables.
- Requirement: Restrict CORS by environment and prevent wildcard CORS in production.
- Skipped option: Hard-coding one production origin immediately.
- Reason skipped: The repo already has `CORS_ALLOW_ORIGINS` and `CORS_ALLOWED_ORIGINS` environment surfaces; inspect current parsing and Compose wiring before choosing the smallest compatible contract.
- Risk and mitigation: Preserve local development ergonomics for `localhost` while adding a production fail-fast or safe default for wildcard origins.
