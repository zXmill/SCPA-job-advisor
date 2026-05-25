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


def upgrade() -> None:
    op.create_index(
        "idx_jobs_active_posted_id",
        "jobs",
        [sa.text("posted_at DESC"), "id"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "idx_jobs_active_source_posted",
        "jobs",
        ["source", sa.text("posted_at DESC"), "id"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "idx_jobs_active_experience_posted",
        "jobs",
        ["experience_level", sa.text("posted_at DESC"), "id"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "idx_applications_user_applied",
        "applications",
        ["user_id", sa.text("applied_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_applications_user_applied", table_name="applications")
    op.drop_index("idx_jobs_active_experience_posted", table_name="jobs")
    op.drop_index("idx_jobs_active_source_posted", table_name="jobs")
    op.drop_index("idx_jobs_active_posted_id", table_name="jobs")
