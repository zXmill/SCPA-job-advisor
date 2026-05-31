# Compact Recovery

Updated: 2026-05-31 19:03 +07

## Current Task
CODE-REVIEW-REMEDIATION-001: deploy-safety and data-signal integrity remediation pass.

## Current Branch
agent-run

## Latest Commit Hash
8121725

## Active Phase
CODE REVIEW REMEDIATION PASS (P0/P1 findings only).

## Accepted Findings (P0/P1)
1. tests/security/token_manager.py fabricates refresh tokens — bypasses jti/Redis rotation test coverage (P0 auth test gap)
2. db/migrations/009_reco_hot_indexes.py — non-concurrent index creation on hot jobs table causes deploy-time lock (P0 deploy safety)
3. docker-compose.yml — cascading service_healthy chain blocks gateway startup (P0 deploy safety)
4. .env.example — POSTGRES_PASSWORD and GATEWAY_DATABASE_URL placeholder mismatch (P0 deploy safety)
5. docker-compose.yml — named volume mounts on ncf/dqn shadow baked-in model weights (P0 deploy safety)
6. services/gateway/main.py:2415-2425 — _set_job_interaction_state hardcodes clicked/applied=false (P1 business logic)
7. services/gateway/main.py:3091-3094 — feedback handler OR semantics preserve stale contradictory flags (P1 business logic)
8. services/pipeline/main.py:56 — market-demand job_count formula multiplies by total skills (P1 business logic)

## Deferred / Not in Scope
- P2: outbox batching performance, trigram index, JSONB expression index, N+1 skill inserts, duplicate datetime parsing, duplicate Indonesia constants, duplicate job-payload mapping, dead-code cleanup

## Dirty Files
- Pre-existing: README.md, SCPAv2, notebooks/01+02, many untracked project files/directories.
- Nested frontend/ repository is dirty and must be handled separately.
- No frontend code changes planned for this remediation pass.
- No new product features, no ML training, no scraper redesign.

## Next Exact Action
Phase 1: Triage each P0/P1 finding against current source to confirm validity before writing lines in Phase 2–8.

## Expected Commits
1. docs: record code review remediation plan
2. test: exercise refresh token rotation through token manager
3. db: make recommendation hot indexes deploy safe
4. deploy: allow gateway startup with degraded ml services
5. docs: align database password placeholders in env example
6. deploy: prevent model weight volumes from shadowing artifacts
7. fix: preserve user interaction state transitions
8. fix: correct market demand job count calculation
9. docs: record code review remediation evidence
