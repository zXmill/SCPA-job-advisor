"""Add A/B testing and monitoring tables.

Revision ID: 012_ab_testing_and_monitoring
Revises: 011_job_alerts
Create Date: 2026-05-26 00:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "012_ab_testing_and_monitoring"
down_revision: Union[str, None] = "011_job_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "variants",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("start_at", sa.DateTime(), nullable=True),
        sa.Column("end_at", sa.DateTime(), nullable=True),
        sa.Column("target_metric", sa.String(length=40), nullable=True),
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
    op.create_index("idx_experiments_status", "experiments", ["status"])
    op.create_index(
        "idx_experiments_created",
        "experiments",
        [sa.text("created_at DESC")],
    )

    op.create_table(
        "experiment_assignments",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("variant_name", sa.String(length=60), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_experiment_assignments_unique",
        "experiment_assignments",
        ["experiment_id", "user_id"],
        unique=True,
    )
    op.create_index(
        "idx_experiment_assignments_variant",
        "experiment_assignments",
        ["experiment_id", "variant_name"],
    )

    op.create_table(
        "experiment_metrics",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "experiment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("variant_name", sa.String(length=60), nullable=False),
        sa.Column("metric_name", sa.String(length=60), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("sample_size", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_experiment_metrics_lookup",
        "experiment_metrics",
        ["experiment_id", "variant_name", "metric_name"],
    )


def downgrade() -> None:
    op.drop_index("idx_experiment_metrics_lookup", table_name="experiment_metrics")
    op.drop_table("experiment_metrics")
    op.drop_index("idx_experiment_assignments_variant", table_name="experiment_assignments")
    op.drop_index("idx_experiment_assignments_unique", table_name="experiment_assignments")
    op.drop_table("experiment_assignments")
    op.drop_index("idx_experiments_created", table_name="experiments")
    op.drop_index("idx_experiments_status", table_name="experiments")
    op.drop_table("experiments")
