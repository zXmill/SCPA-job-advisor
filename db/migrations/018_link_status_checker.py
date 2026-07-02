"""Add link-status checker columns to jobs.

Backs services/pipeline/link_status_checker.py (deferred action #5). The checker
re-checks each active job's source_url and records liveness here WITHOUT touching
is_active, so a re-scrape never resurrects a closed verdict. Phase 1 is
write-only; a later phase gates retrieval/listing on link_status.

Revision ID: 018_link_status_checker
Revises: 017_profile_onboarding_fields
Create Date: 2026-07-02 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "018_link_status_checker"
down_revision: Union[str, None] = "017_profile_onboarding_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "link_status",
            sa.String(length=16),
            server_default=sa.text("'open'"),
            nullable=False,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "consecutive_check_failures",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column("last_http_status", sa.Integer(), nullable=True),
    )
    op.create_index(
        "idx_jobs_link_status",
        "jobs",
        ["link_status"],
        unique=False,
        postgresql_where=sa.text("link_status <> 'open'"),
    )


def downgrade() -> None:
    op.drop_index("idx_jobs_link_status", table_name="jobs")
    op.drop_column("jobs", "last_http_status")
    op.drop_column("jobs", "consecutive_check_failures")
    op.drop_column("jobs", "last_checked_at")
    op.drop_column("jobs", "link_status")
