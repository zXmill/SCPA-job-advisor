"""Add durable model feedback outbox.

Revision ID: 010_feedback_outbox
Revises: 009_reco_hot_indexes
Create Date: 2026-05-25 21:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "010_feedback_outbox"
down_revision: Union[str, None] = "009_reco_hot_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "model_feedback_outbox",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
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
    op.create_index(
        "idx_model_feedback_outbox_status_next",
        "model_feedback_outbox",
        ["status", "next_attempt_at"],
    )
    op.create_index(
        "idx_model_feedback_outbox_user_time",
        "model_feedback_outbox",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_model_feedback_outbox_job_time",
        "model_feedback_outbox",
        ["job_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_model_feedback_outbox_job_time",
        table_name="model_feedback_outbox",
    )
    op.drop_index(
        "idx_model_feedback_outbox_user_time",
        table_name="model_feedback_outbox",
    )
    op.drop_index(
        "idx_model_feedback_outbox_status_next",
        table_name="model_feedback_outbox",
    )
    op.drop_table("model_feedback_outbox")
