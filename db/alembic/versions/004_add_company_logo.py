"""add company_logo

Revision ID: 004_add_company_logo
Revises: 003_hybrid_mode_schema
Create Date: 2026-05-18 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004_add_company_logo'
down_revision: Union[str, None] = '003_hybrid_mode_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Column already created directly via psql, but keeping it for schema completeness.
    # We will just catch the exception if it already exists.
    try:
        op.add_column('jobs', sa.Column('company_logo', sa.String(length=1000), nullable=True))
    except Exception:
        pass

def downgrade() -> None:
    op.drop_column('jobs', 'company_logo')
