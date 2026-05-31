"""Add rich job description and skill-source fields.

Revision ID: 014_rich_job_desc_skill_sources
Revises: 013_hot_indexes_concurrent
Create Date: 2026-06-01 02:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "014_rich_job_desc_skill_sources"
down_revision: Union[str, None] = "013_hot_indexes_concurrent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "skills",
        "category",
        existing_type=postgresql.ENUM("technical", "soft", "linguistic", name="skillcategory"),
        type_=sa.String(length=32),
        existing_nullable=False,
        existing_server_default=sa.text("'technical'::skillcategory"),
        server_default=sa.text("'technical'"),
        postgresql_using="category::text",
    )

    op.add_column("jobs", sa.Column("raw_description_html", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("description_text", sa.Text(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column(
            "description_sections",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "jobs",
        sa.Column("responsibilities", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    )
    op.add_column(
        "jobs",
        sa.Column("requirements", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    )
    op.add_column(
        "jobs",
        sa.Column("nice_to_have", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    )
    op.add_column(
        "jobs",
        sa.Column("benefits", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    )
    op.add_column("jobs", sa.Column("seniority_level", sa.String(length=128), nullable=True))
    op.add_column("jobs", sa.Column("employment_type", sa.String(length=128), nullable=True))
    op.add_column("jobs", sa.Column("job_function", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("industry", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("education_level", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("years_experience_min", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("years_experience_max", sa.Integer(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("required_skill_names", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    )
    op.add_column(
        "jobs",
        sa.Column("preferred_skill_names", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    )
    op.add_column(
        "jobs",
        sa.Column("extracted_skill_names", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    )
    op.add_column("jobs", sa.Column("source_url", sa.String(length=2000), nullable=True))
    op.add_column("jobs", sa.Column("source_updated_at", sa.DateTime(), nullable=True))
    op.create_index("idx_jobs_source_url", "jobs", ["source_url"])

    op.add_column("skills", sa.Column("source", sa.String(length=64), server_default=sa.text("'local'"), nullable=False))
    op.add_column("skills", sa.Column("confidence", sa.Float(), server_default=sa.text("1.0"), nullable=False))
    op.create_index("idx_skills_source", "skills", ["source"])


def downgrade() -> None:
    op.drop_index("idx_skills_source", table_name="skills")
    op.drop_column("skills", "confidence")
    op.drop_column("skills", "source")
    op.execute(
        "UPDATE skills SET category = 'technical' "
        "WHERE category NOT IN ('technical', 'soft', 'linguistic')"
    )
    op.alter_column(
        "skills",
        "category",
        existing_type=sa.String(length=32),
        type_=postgresql.ENUM("technical", "soft", "linguistic", name="skillcategory"),
        existing_nullable=False,
        existing_server_default=sa.text("'technical'"),
        server_default=sa.text("'technical'::skillcategory"),
        postgresql_using="category::skillcategory",
    )

    op.drop_index("idx_jobs_source_url", table_name="jobs")
    op.drop_column("jobs", "source_updated_at")
    op.drop_column("jobs", "source_url")
    op.drop_column("jobs", "extracted_skill_names")
    op.drop_column("jobs", "preferred_skill_names")
    op.drop_column("jobs", "required_skill_names")
    op.drop_column("jobs", "years_experience_max")
    op.drop_column("jobs", "years_experience_min")
    op.drop_column("jobs", "education_level")
    op.drop_column("jobs", "industry")
    op.drop_column("jobs", "job_function")
    op.drop_column("jobs", "employment_type")
    op.drop_column("jobs", "seniority_level")
    op.drop_column("jobs", "benefits")
    op.drop_column("jobs", "nice_to_have")
    op.drop_column("jobs", "requirements")
    op.drop_column("jobs", "responsibilities")
    op.drop_column("jobs", "description_sections")
    op.drop_column("jobs", "description_text")
    op.drop_column("jobs", "raw_description_html")
