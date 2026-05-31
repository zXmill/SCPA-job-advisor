# Debug Database Report

Updated: 2026-05-31 09:12 +07

Status: baseline migration-head checks completed; live upgrade validation is still blocked by current Docker rebuild failure/current-image gap.

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
- Existing gateway container cannot run Alembic because `alembic` is not installed in that image.
- Full pytest, including `db/tests/test_models.py` and `db/tests/test_seed_contracts.py`, passed.

## Open Validation
- A live `alembic upgrade head` against a current-image/runtime database has not been proven in this session.
- Current Docker rebuild failure must be resolved or a deliberate local DB migration path must be used before marking live migration validation as passed.
