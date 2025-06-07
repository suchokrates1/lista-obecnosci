"""add email related settings

Revision ID: 7f3407e19bf7
Revises: f2d704bc9b34
Create Date: 2025-06-10 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '7f3407e19bf7'
down_revision = 'f2d704bc9b34'
branch_labels = None
depends_on = None


def upgrade():
    setting = sa.table('setting', sa.column('key', sa.String), sa.column('value', sa.String))
    op.bulk_insert(setting, [
        {'key': 'email_sender_name', 'value': 'Vest Media'},
        {'key': 'email_login', 'value': ''},
        {'key': 'email_password', 'value': ''},
        {'key': 'email_footer', 'value': ''},
        {'key': 'reg_email_subject', 'value': 'Aktywacja konta w ShareOKO'},
        {'key': 'reg_email_body', 'value': 'Twoje konto zosta\u0142o zatwierdzone i jest ju\u017c aktywne.'},
        {'key': 'reset_email_subject', 'value': 'Reset has\u0142a w ShareOKO'},
        {'key': 'reset_email_body', 'value': 'Aby ustawi\u0107 nowe has\u0142o, otw\u00f3rz link: {link}'}
    ])


def downgrade():
    conn = op.get_bind()
    for key in ['email_sender_name', 'email_login', 'email_password', 'email_footer', 'reg_email_subject', 'reg_email_body', 'reset_email_subject', 'reset_email_body']:
        conn.execute(sa.text('DELETE FROM setting WHERE key=:k'), {'k': key})

