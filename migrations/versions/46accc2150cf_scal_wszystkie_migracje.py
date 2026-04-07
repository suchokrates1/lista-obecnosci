"""scal wszystkie migracje

Revision ID: 46accc2150cf
Revises: ad54aed01398, cafe7ef48e81, e053cdc6d071
Create Date: 2025-06-16 23:30:13.914171

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '46accc2150cf'
down_revision = ('ad54aed01398', 'cafe7ef48e81', 'e053cdc6d071')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass