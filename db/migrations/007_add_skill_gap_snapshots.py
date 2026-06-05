"""Add skill_gap_snapshots table.

Revision ID: 007_add_skill_gap_snapshots
Revises: 006_reco_db_contracts
Create Date: 2026-05-25 14:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "007_add_skill_gap_snapshots"
down_revision: Union[str, None] = "006_reco_db_contracts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skill_gap_snapshots",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("missing_skills", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("matched_skills", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("explanation", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_skill_gap_user_time", "skill_gap_snapshots", ["user_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("idx_skill_gap_user_time", table_name="skill_gap_snapshots")
    op.drop_table("skill_gap_snapshots")
