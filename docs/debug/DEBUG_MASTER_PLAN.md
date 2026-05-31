# Ultimate Debugging Master Plan

Updated: 2026-05-31 20:29 +07

## Session
- Task ID: CODE-REVIEW-REMEDIATION-001
- Branch: agent-run
- Active Phase: Code Review Remediation Pass — deploy safety and data-signal integrity.

## Active Task
Repair the reopened R-2 deploy-safe index migration finding. Current source uses concurrent index DDL, but the migration fails because it changes isolation level after Alembic has opened a transaction.

## Next Exact Action
Patch `db/migrations/013_hot_indexes_concurrent.py` to use Alembic `autocommit_block()` for `CREATE INDEX CONCURRENTLY` and concurrent downgrade drops, then run migration validation.

## Guardrails
- Do not fix P2 suggestions (performance, duplication, dead code) unless they are a prerequisite for a P0/P1 fix.
- Do not commit unrelated dirty files.
- Keep commits scoped by finding.
- No `git add .`.
- Do not start ML training, scraper redesign, taxonomy work, or feature work.

## Previous Work
- FIX-API-FEEDBACK-SLATE, FIX-DOCKER-RUNTIME-BUILD, FIX-API-RUNTIME-GUARDS are all committed (342edb0, b747954, 6366b67).
- API runtime probe passed 83/83 with 0 HTTP 5xx after gateway rebuild.
- Full backend suite passed 390 tests.
- Final Selenium audit passed 9 pages with 0 errors/blank/hydration failures.
