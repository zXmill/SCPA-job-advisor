# Debug Database Report

Updated: 2026-05-31 10:45 +07

Status: live migration validation completed against the running local PostgreSQL container.

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

## Open Validation
- Container-local Alembic is still not part of the gateway runtime image by design; migration validation was run from the repo-local `.venv` against the local PostgreSQL container.

## Feedback/Slate Relationship Finding
- The `feedback_events.slate_id` FK correctly rejects feedback for unknown served slates.
- Browser evidence showed the gateway violated the application-side contract by returning an unpersisted slate ID.
- Current-source regression verifies `/api/recommendations` now creates the `served_slates` row before `/api/recommendations/feedback` writes `feedback_events`.
- Test cleanup now truncates `feedback_events`, `served_slate_items`, and `served_slates` to keep DB tests isolated.
