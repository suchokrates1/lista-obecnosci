"""add settings table

Revision ID: f2d704bc9b34
Revises: 24f8fe5b09bb
Create Date: 2025-06-09 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = 'f2d704bc9b34'
down_revision = '24f8fe5b09bb'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'setting',
        sa.Column('key', sa.String(), primary_key=True),
        sa.Column('value', sa.String(), nullable=True)
    )


def downgrade():
    op.drop_table('setting')

