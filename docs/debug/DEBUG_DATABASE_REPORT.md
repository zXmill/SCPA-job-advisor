# Debug Database Report

Updated: 2026-05-31 20:34 +07

Status: running Docker PostgreSQL schema reconciled to repo head after API runtime probe found drift.

## Required Checks
- Alembic heads.
- Migration apply status when a database is available.
- ORM/schema alignment.
- Important tables and relationships.
- Recommendation, feedback, skills, and job-required-skill query paths.
- Index coverage for hot paths.

## Baseline Results
- Local Alembic head command passed: `012_ab_testing_and_monitoring (head)`.
- Existing postgres container responds to `pg_isready`.
- Live database initially reported `001_initial_schema`.
- `alembic upgrade head` applied migrations through `012_ab_testing_and_monitoring`.
- `alembic current` now reports `012_ab_testing_and_monitoring (head)`.
- Full pytest, including `db/tests/test_models.py` and `db/tests/test_seed_contracts.py`, passed.
- API runtime probe reconciliation later found the running Docker PostgreSQL database at `011_job_alerts`, with `experiments`, `experiment_assignments`, and `experiment_metrics` absent.
- Applied the existing `012_ab_testing_and_monitoring` table/index DDL via `docker compose exec -T postgres psql` because the gateway image does not include Alembic and Postgres is not host-exposed.
- Post-repair checks now return `012_ab_testing_and_monitoring`, `experiments`, `experiment_assignments`, and `experiment_metrics`.

## Open Validation
- Container-local Alembic is still not part of the gateway runtime image by design. Future migration validation should explicitly target the Docker PostgreSQL database instead of assuming host Alembic and compose DB are the same target.

## Feedback/Slate Relationship Finding
- The `feedback_events.slate_id` FK correctly rejects feedback for unknown served slates.
- Browser evidence showed the gateway violated the application-side contract by returning an unpersisted slate ID.
- Current-source regression verifies `/api/recommendations` now creates the `served_slates` row before `/api/recommendations/feedback` writes `feedback_events`.
- Test cleanup now truncates `feedback_events`, `served_slate_items`, and `served_slates` to keep DB tests isolated.

## Code Review Remediation Migration Finding
- R-2 is fixed. `009_reco_hot_indexes.py` now creates/drops hot indexes with PostgreSQL concurrent DDL inside Alembic `autocommit_block()`, so fresh deployments do not create these indexes with long write-blocking index builds.
- `013_hot_indexes_concurrent.py` is retained as an idempotent repair migration for databases already at `012`; it now uses `autocommit_block()` correctly and does not drop 009-owned indexes on downgrade.
- Validation passed: `upgrade head`, `downgrade 012_ab_testing_and_monitoring`, `upgrade head`, `current`, and `heads`.
