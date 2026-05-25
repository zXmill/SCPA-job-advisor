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
