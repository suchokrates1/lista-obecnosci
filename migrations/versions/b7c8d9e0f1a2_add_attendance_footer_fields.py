"""add attendance footer fields to trainer

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-05-11 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = 'b7c8d9e0f1a2'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('prowadzacy', sa.Column('trainer_display_name', sa.String(), nullable=True))
    op.add_column('prowadzacy', sa.Column('assistant_name', sa.String(), nullable=True))


def downgrade():
    op.drop_column('prowadzacy', 'assistant_name')
    op.drop_column('prowadzacy', 'trainer_display_name')