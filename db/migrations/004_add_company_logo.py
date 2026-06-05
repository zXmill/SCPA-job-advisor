"""add company_logo

Revision ID: 004_add_company_logo
Revises: 003_ml_infra_tables
Create Date: 2026-05-18 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004_add_company_logo'
down_revision: Union[str, None] = '003_ml_infra_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # We will try to add the column, catching exceptions if it already exists
    try:
        op.add_column('jobs', sa.Column('company_logo', sa.String(length=1000), nullable=True))
    except Exception:
        pass

def downgrade() -> None:
    op.drop_column('jobs', 'company_logo')
