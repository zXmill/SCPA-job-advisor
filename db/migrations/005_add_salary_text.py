"""add salary_text

Revision ID: 005_add_salary_text
Revises: 004_add_company_logo
Create Date: 2026-05-25 01:00:00.000000

Adds a free-text salary column for job postings whose source page exposes a
human-readable salary string (e.g. Glints "Rp 5.000.000 - Rp 8.000.000") that
does not parse cleanly into the numeric ``min_salary``/``max_salary`` columns.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = '005_add_salary_text'
down_revision: Union[str, None] = '004_add_company_logo'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("jobs")}
    if "salary_text" not in columns:
        op.add_column('jobs', sa.Column('salary_text', sa.String(length=255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("jobs")}
    if "salary_text" in columns:
        op.drop_column('jobs', 'salary_text')
