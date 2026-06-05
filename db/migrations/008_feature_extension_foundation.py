"""Add feature extension taxonomy, certification, and CV schema.

Revision ID: 008_feature_extension_foundation
Revises: 007_add_skill_gap_snapshots
Create Date: 2026-05-25 18:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "008_feature_extension_foundation"
down_revision: Union[str, None] = "007_add_skill_gap_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("category", sa.String(length=32), server_default=sa.text("'technical'"), nullable=False),
        sa.Column("frequency", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_skills_name", "skills", ["name"])
    op.create_index("idx_skills_category", "skills", ["category"])

    op.create_table(
        "job_required_skills",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_id", sa.BigInteger(), nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("importance", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("job_id", "skill_id", name="uq_job_required_skills_job_skill"),
    )
    op.create_index("idx_jrs_job", "job_required_skills", ["job_id"])
    op.create_index("idx_jrs_skill", "job_required_skills", ["skill_id"])

    op.create_table(
        "certification_skills",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("cert_name_regex", sa.String(length=255), nullable=False),
        sa.Column("issuer", sa.String(length=255), nullable=True),
        sa.Column(
            "mapped_skills",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "user_certifications",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("cert_name", sa.String(length=255), nullable=True),
        sa.Column("issuer", sa.String(length=255), nullable=True),
        sa.Column("ocr_confidence", sa.String(length=20), server_default=sa.text("'medium'"), nullable=False),
        sa.Column(
            "mapped_skills",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'confirmed'"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_uc_user", "user_certifications", ["user_id"])

    op.add_column("users", sa.Column("cv_embedding", postgresql.ARRAY(sa.Float()), nullable=True))
    op.add_column("users", sa.Column("cv_uploaded_at", sa.DateTime(), nullable=True))
    op.add_column("jobs", sa.Column("skills_extracted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "skills_extracted_at")
    op.drop_column("users", "cv_uploaded_at")
    op.drop_column("users", "cv_embedding")

    op.drop_index("idx_uc_user", table_name="user_certifications")
    op.drop_table("user_certifications")
    op.drop_table("certification_skills")

    op.drop_index("idx_jrs_skill", table_name="job_required_skills")
    op.drop_index("idx_jrs_job", table_name="job_required_skills")
    op.drop_table("job_required_skills")

    op.drop_index("idx_skills_category", table_name="skills")
    op.drop_index("idx_skills_name", table_name="skills")
    op.drop_table("skills")
