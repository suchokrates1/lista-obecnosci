"""add HTML email template settings

Revision ID: cf3def3a39c4
Revises: cafe7ef48e81
Create Date: 2025-09-01 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = 'cf3def3a39c4'
down_revision = 'cafe7ef48e81'
branch_labels = None
depends_on = None


def upgrade():
    setting = sa.table('setting', sa.column('key', sa.String), sa.column('value', sa.String))
    op.bulk_insert(setting, [
        {'key': 'email_list_html_body', 'value': ''},
        {'key': 'email_report_html_body', 'value': ''},
        {'key': 'registration_email_html_body', 'value': ''},
        {'key': 'reg_email_html_body', 'value': ''},
        {'key': 'reset_email_html_body', 'value': ''},
    ])


def downgrade():
    conn = op.get_bind()
    for key in [
        'email_list_html_body',
        'email_report_html_body',
        'registration_email_html_body',
        'reg_email_html_body',
        'reset_email_html_body',
    ]:
        conn.execute(sa.text('DELETE FROM setting WHERE key=:k'), {'k': key})
