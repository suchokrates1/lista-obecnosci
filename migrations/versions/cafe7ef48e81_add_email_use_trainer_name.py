"""add email_use_trainer_name setting

Revision ID: cafe7ef48e81
Revises: e203a8fa7c0d
Create Date: 2025-08-01 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = 'cafe7ef48e81'
down_revision = 'e203a8fa7c0d'
branch_labels = None
depends_on = None


def upgrade():
    setting = sa.table('setting', sa.column('key', sa.String), sa.column('value', sa.String))
    op.bulk_insert(setting, [
        {'key': 'email_use_trainer_name', 'value': '0'},
    ])


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text('DELETE FROM setting WHERE key=:k'), {'k': 'email_use_trainer_name'})
