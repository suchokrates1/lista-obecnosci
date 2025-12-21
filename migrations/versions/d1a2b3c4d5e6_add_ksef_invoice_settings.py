"""add ksef invoice settings

Revision ID: d1a2b3c4d5e6
Revises: cafe7ef48e81
Create Date: 2025-12-21 10:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = 'd1a2b3c4d5e6'
down_revision = 'cafe7ef48e81'
branch_labels = None
depends_on = None


def upgrade():
    setting = sa.table('setting', sa.column('key', sa.String), sa.column('value', sa.String))
    op.bulk_insert(setting, [
        # KSeF configuration
        {'key': 'ksef_enabled', 'value': '0'},
        {'key': 'ksef_environment', 'value': 'test'},  # test, demo, production
        {'key': 'ksef_nip', 'value': ''},
        {'key': 'ksef_token', 'value': ''},
        
        # Invoice issuer data
        {'key': 'invoice_issuer_name', 'value': ''},
        {'key': 'invoice_issuer_nip', 'value': ''},
        {'key': 'invoice_issuer_address', 'value': ''},
        {'key': 'invoice_issuer_postal', 'value': ''},
        {'key': 'invoice_issuer_city', 'value': ''},
        {'key': 'invoice_issuer_country', 'value': 'PL'},
        {'key': 'invoice_issuer_email', 'value': ''},
        {'key': 'invoice_issuer_phone', 'value': ''},
        
        # Invoice recipient (contractor) data
        {'key': 'invoice_recipient_name', 'value': ''},
        {'key': 'invoice_recipient_nip', 'value': ''},
        {'key': 'invoice_recipient_address', 'value': ''},
        {'key': 'invoice_recipient_postal', 'value': ''},
        {'key': 'invoice_recipient_city', 'value': ''},
        {'key': 'invoice_recipient_country', 'value': 'PL'},
        
        # Service configuration
        {'key': 'invoice_service_name', 'value': 'Prowadzenie zajęć z tworzenia podcastów w ramach projektu ShareOko III'},
        {'key': 'invoice_hourly_rate', 'value': '0.00'},
        {'key': 'invoice_currency', 'value': 'PLN'},
        {'key': 'invoice_vat_rate', 'value': '23'},  # VAT percentage
        {'key': 'invoice_payment_deadline_days', 'value': '14'},
        {'key': 'invoice_payment_method', 'value': '1'},  # 1 = przelew
        
        # Invoice numbering
        {'key': 'invoice_number_prefix', 'value': 'FV'},
        {'key': 'invoice_number_counter', 'value': '1'},
    ])


def downgrade():
    conn = op.get_bind()
    keys = [
        'ksef_enabled', 'ksef_environment', 'ksef_nip', 'ksef_token',
        'invoice_issuer_name', 'invoice_issuer_nip', 'invoice_issuer_address',
        'invoice_issuer_postal', 'invoice_issuer_city', 'invoice_issuer_country',
        'invoice_issuer_email', 'invoice_issuer_phone',
        'invoice_recipient_name', 'invoice_recipient_nip', 'invoice_recipient_address',
        'invoice_recipient_postal', 'invoice_recipient_city', 'invoice_recipient_country',
        'invoice_service_name', 'invoice_hourly_rate', 'invoice_currency',
        'invoice_vat_rate', 'invoice_payment_deadline_days', 'invoice_payment_method',
        'invoice_number_prefix', 'invoice_number_counter',
    ]
    for key in keys:
        conn.execute(sa.text('DELETE FROM setting WHERE key=:k'), {'k': key})
