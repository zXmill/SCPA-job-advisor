"""Verify hot-path indexes are present with deploy-safe concurrent DDL.

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
    """Build and execute a concurrent index statement outside a transaction."""
    cols_sql = ", ".join(
        f'"{c}"' if isinstance(c, str) else str(c) for c in columns
    )
    where_sql = f" WHERE {str(where)}" if where is not None else ""
    stmt = (
        f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{index_name}" '
        f'ON "{table_name}" ({cols_sql}){where_sql}'
    )
    op.execute(sa.text(stmt))


def upgrade() -> None:
    # This is an idempotent repair migration for databases that reached 012
    # before 009 was changed to use concurrent index creation.
    with op.get_context().autocommit_block():
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
    # 009 owns these indexes. Downgrading this idempotent repair migration
    # must not remove indexes that earlier revisions expect to exist.
    pass
