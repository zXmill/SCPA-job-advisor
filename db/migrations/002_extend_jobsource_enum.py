#!/usr/bin/env python3
"""SCPA Migration 002 - Extend jobsource ENUM for v2 Pipeline.

Adds Indonesian local job-board sources and global aggregators so the
new pipeline (services/pipeline v2) can persist rows with a proper
typed source column instead of stuffing the source name into
match_data JSONB.

New ENUM values:
    - kalibrr        Kalibrr Indonesia (also Philippines)
    - karir          Karir.com (legacy Indonesian portal)
    - topkarir       TopKarir.com
    - kitalulus      KitaLulus
    - techinasia     Tech in Asia Jobs
    - remotive       Remotive (global remote board, public API)
    - indeed         Indeed (via JobSpy)

Forward-only per docs/adr/0001-forward-only-alembic-migrations.md.
Postgres requires ALTER TYPE ADD VALUE to be run outside a transaction
block (autocommit), so we wrap each addition with IF NOT EXISTS for
idempotency.
"""
from alembic import op


revision = "002_extend_jobsource_enum"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


# ALTER TYPE ... ADD VALUE must run outside a transaction in Postgres.
# Alembic honours this by setting transaction_per_migration=False or by
# emitting the statement with op.execute() under an explicit COMMIT
# boundary. We use the IF NOT EXISTS form (Postgres 12+) which is safe
# to re-run if a partial migration was applied.
NEW_VALUES = (
    "kalibrr",
    "karir",
    "topkarir",
    "kitalulus",
    "techinasia",
    "remotive",
    "indeed",
)


def upgrade() -> None:
    """Append new values to the jobsource ENUM.

    Uses IF NOT EXISTS so the migration is idempotent across partial
    re-runs (e.g. CI retries, manual hot-fixes). Each statement is
    committed independently to satisfy Postgres' rule that ENUM
    additions cannot share a transaction with other DDL that depends
    on the new value.
    """
    # COMMIT any pending transaction so ALTER TYPE ADD VALUE can run.
    op.execute("COMMIT")
    for value in NEW_VALUES:
        op.execute(
            f"ALTER TYPE jobsource ADD VALUE IF NOT EXISTS '{value}'"
        )


def downgrade() -> None:
    """ENUM value removal is not supported by Postgres.

    Per ADR-0001 (forward-only migrations) we do not attempt to drop
    individual ENUM values. A true downgrade would require recreating
    the type and rewriting every dependent column, which is unsafe in
    production. Operators who must revert should restore from a
    snapshot taken before this migration.
    """
    # Intentionally a no-op. See docstring.
    pass
