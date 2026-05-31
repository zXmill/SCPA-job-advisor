"""Add hot-path recommendation indexes.

Revision ID: 009_reco_hot_indexes
Revises: 008_feature_extension_foundation
Create Date: 2026-05-25 20:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "009_reco_hot_indexes"
down_revision: Union[str, None] = "008_feature_extension_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_index_concurrently(
    index_name: str,
    table_name: str,
    columns: list[str | sa.sql.elements.TextClause],
    where: sa.sql.elements.TextClause | None = None,
) -> None:
    cols_sql = ", ".join(
        f'"{c}"' if isinstance(c, str) else str(c) for c in columns
    )
    where_sql = f" WHERE {str(where)}" if where is not None else ""
    op.execute(
        sa.text(
            f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{index_name}" '
            f'ON "{table_name}" ({cols_sql}){where_sql}'
        )
    )


def _drop_index_concurrently(index_name: str) -> None:
    op.execute(sa.text(f'DROP INDEX CONCURRENTLY IF EXISTS "{index_name}"'))


def upgrade() -> None:
    # Hot jobs/application indexes can be large in production, so build them
    # outside Alembic's transaction wrapper to avoid long write-blocking locks.
    with op.get_context().autocommit_block():
        _create_index_concurrently(
            "idx_jobs_active_posted_id",
            "jobs",
            [sa.text("posted_at DESC"), "id"],
            where=sa.text("is_active = true"),
        )
        _create_index_concurrently(
            "idx_jobs_active_source_posted",
            "jobs",
            ["source", sa.text("posted_at DESC"), "id"],
            where=sa.text("is_active = true"),
        )
        _create_index_concurrently(
            "idx_jobs_active_experience_posted",
            "jobs",
            ["experience_level", sa.text("posted_at DESC"), "id"],
            where=sa.text("is_active = true"),
        )
        _create_index_concurrently(
            "idx_applications_user_applied",
            "applications",
            ["user_id", sa.text("applied_at DESC")],
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        _drop_index_concurrently("idx_applications_user_applied")
        _drop_index_concurrently("idx_jobs_active_experience_posted")
        _drop_index_concurrently("idx_jobs_active_source_posted")
        _drop_index_concurrently("idx_jobs_active_posted_id")
