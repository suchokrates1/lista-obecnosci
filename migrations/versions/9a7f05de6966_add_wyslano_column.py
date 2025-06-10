"""add wyslano flag to sessions

Revision ID: 9a7f05de6966
Revises: e203a8fa7c0d
Create Date: 2025-07-10 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '9a7f05de6966'
down_revision = 'e203a8fa7c0d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('zajecia', sa.Column('wyslano', sa.Boolean(), nullable=True, server_default=sa.text('0')))
    conn = op.get_bind()
    conn.execute(sa.text('UPDATE zajecia SET wyslano=1'))
    op.alter_column('zajecia', 'wyslano', server_default=None, nullable=False)


def downgrade():
    op.drop_column('zajecia', 'wyslano')
