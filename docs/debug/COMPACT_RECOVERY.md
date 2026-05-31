# Compact Recovery

Updated: 2026-05-31 19:44 +07

## Current Task
CODE-REVIEW-REMEDIATION-001: deploy-safety and data-signal integrity remediation pass.

## Current Branch
agent-run

## Latest Commit Hash
8df6aef

## Active Phase
REMEDIATION COMPLETE — All 8 P0/P1 findings fixed and validated. See CODE_REVIEW_REMEDIATION_REPORT.md.

## Completion Status
- All 8 P0/P1 findings fixed:
  1. Auth refresh-token tests now exercise JTI/Redis rotation (R-1)
  2. Created 013_hot_indexes_concurrent.py with CONCURRENTLY (R-2)
  3. Removed pipeline: condition: service_healthy from gateway (R-3)
  4. Aligned GATEWAY_DATABASE_URL to POSTGRES_PASSWORD placeholder (R-4)
  5. Removed weights volume mounts from ncf/dqn (R-5)
  6. Added OR semantics for clicked/applied preservation (R-6)
  7. Added CASE transitions per event type (R-7)
  8. Fixed market demand to return raw job counts (R-8)
- 5 scoped commits pushed
- Tests: 32 passed (focused), 397 passed (full suite)
- No FAILURE_LEDGER entries required

## Deferred / Not in Scope
- P2: outbox batching performance, trigram index, JSONB expression index, N+1 skill inserts, duplicate datetime parsing, duplicate Indonesia constants, duplicate job-payload mapping, dead-code cleanup

## Dirty Files
- Pre-existing: README.md, SCPAv2, notebooks/01+02, many untracked project files/directories.
- Nested frontend/ repository is dirty and must be handled separately.
- No frontend code changes planned for this remediation pass.
- No new product features, no ML training, no scraper redesign.
