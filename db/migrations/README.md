"""Migration script template

Revision ID: <hash>
Revises: <previous_hash>
Create Date: <date>
"""
from alembic import op
import sqlalchemy as sa

revision = '<revision_id>'
down_revision = '<down_revision_id>'
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass