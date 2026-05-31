"""Replace bundled hot-path indexes with concurrent creation for deploy safety.

Revision ID: 013_hot_indexes_concurrent
Revises: 012_ab_testing_and_monitoring
Create Date: 2026-05-31 19:03:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013_hot_indexes_concurrent"
down_revision: Union[str, None] = "012_ab_testing_and_monitoring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_index_concurrently(
    index_name: str,
    table_name: str,
    columns: list[str | sa.sql.elements.TextClause],
    where: sa.sql.elements.TextClause | None = None,
) -> None:
    """Build and execute a CREATE INDEX CONCURRENTLY IF NOT EXISTS statement.

    ``op.create_index`` does not expose ``postgresql_concurrently`` in a way
    that is compatible with Alembic's transaction wrapper, so we emit the
    DDL directly under autocommit. ``IF NOT EXISTS`` makes this migration
    idempotent: if ``009_reco_hot_indexes`` already created the indexes
    synchronously, this is a safe no-op.
    """
    conn = op.get_bind()
    conn.execution_options(isolation_level="AUTOCOMMIT")
    cols_sql = ", ".join(
        f'"{c}"' if isinstance(c, str) else str(c) for c in columns
    )
    where_sql = f" WHERE {str(where)}" if where is not None else ""
    stmt = (
        f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{index_name}" '
        f'ON "{table_name}" ({cols_sql}){where_sql}'
    )
    conn.execute(sa.text(stmt))


def upgrade() -> None:
    # Recreate the hot-path jobs indexes concurrently so deployment does
    # not acquire ACCESS EXCLUSIVE for the full index build duration.
    _create_index_concurrently(
        index_name="idx_jobs_active_posted_id",
        table_name="jobs",
        columns=[sa.text("posted_at DESC"), "id"],
        where=sa.text("is_active = true"),
    )
    _create_index_concurrently(
        index_name="idx_jobs_active_source_posted",
        table_name="jobs",
        columns=["source", sa.text("posted_at DESC"), "id"],
        where=sa.text("is_active = true"),
    )
    _create_index_concurrently(
        index_name="idx_jobs_active_experience_posted",
        table_name="jobs",
        columns=["experience_level", sa.text("posted_at DESC"), "id"],
        where=sa.text("is_active = true"),
    )
    _create_index_concurrently(
        index_name="idx_applications_user_applied",
        table_name="applications",
        columns=["user_id", sa.text("applied_at DESC")],
    )


def downgrade() -> None:
    # Downgrade only drops indexes created here if they exist. If the
    # original 009 synchronous indexes still exist, dropping them would
    # break reads, so we only drop what this migration created.
    conn = op.get_bind()
    conn.execution_options(isolation_level="AUTOCOMMIT")
    for index_name in (
        "idx_applications_user_applied",
        "idx_jobs_active_experience_posted",
        "idx_jobs_active_source_posted",
        "idx_jobs_active_posted_id",
    ):
        conn.execute(
            sa.text(f'DROP INDEX IF EXISTS "{index_name}"')
        )
