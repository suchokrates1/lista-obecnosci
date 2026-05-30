"""add assistant signature to trainer

Revision ID: c3d4e5f6a7b8
Revises: b7c8d9e0f1a2
Create Date: 2026-05-11 18:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b7c8d9e0f1a2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('prowadzacy', sa.Column('assistant_signature_filename', sa.String(), nullable=True))


def downgrade():
    op.drop_column('prowadzacy', 'assistant_signature_filename')