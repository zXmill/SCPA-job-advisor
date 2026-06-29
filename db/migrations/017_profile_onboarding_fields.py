"""Add onboarding profile fields: location, education_level, graduation_year, interests.

These back the redesigned /onboarding flow. `location` lights up the
existing `location_fit` reason channel (the pipeline already reads
profile.location, it was just always null). `interests` feed the SBERT
profile_text so they genuinely shape recommendations. `education_level`
is a free string (not an enum) to stay flexible.

Revision ID: 017_profile_onboarding_fields
Revises: 016_embedding_platform_v2
Create Date: 2026-06-29 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "017_profile_onboarding_fields"
down_revision: Union[str, None] = "016_embedding_platform_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("location", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("education_level", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("graduation_year", sa.SmallInteger(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "interests",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "interests")
    op.drop_column("users", "graduation_year")
    op.drop_column("users", "education_level")
    op.drop_column("users", "location")
