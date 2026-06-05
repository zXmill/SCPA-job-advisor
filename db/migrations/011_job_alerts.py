"""Add durable job alerts.

Revision ID: 011_job_alerts
Revises: 010_feedback_outbox
Create Date: 2026-05-25 22:58:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "011_job_alerts"
down_revision: Union[str, None] = "010_feedback_outbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_alerts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("query", sa.String(length=200), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column(
            "min_match_percent",
            sa.Integer(),
            server_default=sa.text("60"),
            nullable=False,
        ),
        sa.Column(
            "frequency",
            sa.String(length=20),
            server_default=sa.text("'daily'"),
            nullable=False,
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "criteria",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("last_notified_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("idx_job_alerts_user_active", "job_alerts", ["user_id", "active"])
    op.create_index(
        "idx_job_alerts_user_created",
        "job_alerts",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_job_alerts_frequency_active",
        "job_alerts",
        ["frequency", "active"],
    )


def downgrade() -> None:
    op.drop_index("idx_job_alerts_frequency_active", table_name="job_alerts")
    op.drop_index("idx_job_alerts_user_created", table_name="job_alerts")
    op.drop_index("idx_job_alerts_user_active", table_name="job_alerts")
    op.drop_table("job_alerts")
