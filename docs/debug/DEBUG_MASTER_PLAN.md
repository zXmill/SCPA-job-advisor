# Ultimate Debugging Master Plan

Updated: 2026-05-31 19:03 +07

## Session
- Task ID: CODE-REVIEW-REMEDIATION-001
- Branch: agent-run
- Active Phase: Code Review Remediation Pass — deploy safety and data-signal integrity.

## Active Task
Triage and fix 5 P0 deploy-safety finding and 3 P1 business-logic/security findings from the local branch review against `origin/master`.

## Next Exact Action
Proceed to Phase 1: confirm each P0/P1 finding against current source code, then Phases 2–8 in priority order.

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
