"""split full name into first and last

Revision ID: 24f8fe5b09bb
Revises: a022a779868c
Create Date: 2025-06-07 17:30:00
"""
from alembic import op
import sqlalchemy as sa

revision = '24f8fe5b09bb'
down_revision = 'a022a779868c'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    prowadzacy = sa.table(
        'prowadzacy',
        sa.column('id', sa.Integer),
        sa.column('imie', sa.String),
        sa.column('nazwisko', sa.String),
    )
    result = conn.execute(sa.select(prowadzacy.c.id, prowadzacy.c.nazwisko))
    for row in result:
        if row.nazwisko:
            imie, _, nazwisko = row.nazwisko.partition(' ')
            conn.execute(
                prowadzacy.update()
                .where(prowadzacy.c.id == row.id)
                .values(imie=imie, nazwisko=nazwisko)
            )


def downgrade():
    conn = op.get_bind()
    prowadzacy = sa.table(
        'prowadzacy',
        sa.column('id', sa.Integer),
        sa.column('imie', sa.String),
        sa.column('nazwisko', sa.String),
    )
    result = conn.execute(sa.select(prowadzacy.c.id, prowadzacy.c.imie, prowadzacy.c.nazwisko))
    for row in result:
        full = ' '.join(filter(None, [row.imie, row.nazwisko]))
        conn.execute(
            prowadzacy.update()
            .where(prowadzacy.c.id == row.id)
            .values(imie=None, nazwisko=full)
        )

