"""insert default templates for additional emails

Revision ID: e203a8fa7c0d
Revises: 7f3407e19bf7
Create Date: 2025-07-01 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = 'e203a8fa7c0d'
down_revision = '7f3407e19bf7'
branch_labels = None
depends_on = None


def upgrade():
    setting = sa.table('setting', sa.column('key', sa.String), sa.column('value', sa.String))
    op.bulk_insert(setting, [
        {'key': 'email_list_subject', 'value': 'Lista obecności – {date}'},
        {'key': 'email_list_body', 'value': 'W załączniku lista obecności z zajęć.'},
        {'key': 'email_report_subject', 'value': 'Raport miesięczny – {date}'},
        {'key': 'email_report_body', 'value': 'W załączniku raport miesięczny do umowy.'},
        {'key': 'registration_email_subject', 'value': 'Nowa rejestracja prowadzącego'},
        {
            'key': 'registration_email_body',
            'value': 'Zarejestrował się {name} (login: {login}).\nPotwierdź konto tutaj: {link}'
        },
    ])


def downgrade():
    conn = op.get_bind()
    for key in [
        'email_list_subject', 'email_list_body',
        'email_report_subject', 'email_report_body',
        'registration_email_subject', 'registration_email_body'
    ]:
        conn.execute(sa.text('DELETE FROM setting WHERE key=:k'), {'k': key})

