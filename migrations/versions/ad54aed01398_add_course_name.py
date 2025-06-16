"""add course name to Prowadzacy

Revision ID: ad54aed01398
Revises: 9a7f05de6966
Create Date: 2025-07-15 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = 'ad54aed01398'
down_revision = '9a7f05de6966'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('prowadzacy') as batch_op:
        batch_op.add_column(sa.Column('nazwa_zajec', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('prowadzacy') as batch_op:
        batch_op.drop_column('nazwa_zajec')
