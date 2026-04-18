"""add archive tables and shareoko iv project

Revision ID: a1b2c3d4e5f6
Revises: d1a2b3c4d5e6
Create Date: 2026-04-18 09:22:00
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

revision = 'a1b2c3d4e5f6'
down_revision = 'd1a2b3c4d5e6'
branch_labels = None
depends_on = None

NEW_PARTICIPANTS = [
    "Zbigniew Haftka",
    "Stanisław Zarzecki",
    "Klaudia Nowak",
    "Aleksandra Bohusz",
    "Justyna Stysz",
    "Marcin Stysz",
    "Katarzyna Noack",
    "Katarzyna Głowacka",
]


def upgrade():
    # 1. Create archive tables
    op.create_table(
        'archived_project',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('archived_at', sa.DateTime, default=datetime.utcnow),
    )
    op.create_table(
        'archived_participant',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('project_id', sa.Integer, sa.ForeignKey('archived_project.id'), nullable=False),
        sa.Column('participant_name', sa.String, nullable=False),
        sa.Column('trainer_name', sa.String),
        sa.Column('sessions_present', sa.Integer, default=0),
        sa.Column('total_sessions', sa.Integer, default=0),
        sa.Column('percent', sa.Float, default=0),
    )

    # 2. Archive current participants under "ShareOko III"
    conn = op.get_bind()

    # Create archive project
    conn.execute(
        sa.text("INSERT INTO archived_project (name, archived_at) VALUES (:name, :ts)"),
        {"name": "ShareOko III", "ts": datetime.utcnow()},
    )
    project_row = conn.execute(
        sa.text("SELECT id FROM archived_project WHERE name = 'ShareOko III' ORDER BY id DESC LIMIT 1")
    ).fetchone()
    project_id = project_row[0]

    # Get all trainers
    trainers = conn.execute(
        sa.text("SELECT id, imie, nazwisko FROM prowadzacy")
    ).fetchall()

    for trainer in trainers:
        trainer_id, imie, nazwisko = trainer[0], trainer[1], trainer[2]
        trainer_name = f"{imie} {nazwisko}"

        # Count total sessions for this trainer
        total_row = conn.execute(
            sa.text("SELECT COUNT(*) FROM zajecia WHERE prowadzacy_id = :tid"),
            {"tid": trainer_id},
        ).fetchone()
        total_sessions = total_row[0] if total_row else 0

        # Get participants with their attendance stats
        participants = conn.execute(
            sa.text("SELECT id, imie_nazwisko FROM uczestnik WHERE prowadzacy_id = :tid"),
            {"tid": trainer_id},
        ).fetchall()

        for participant in participants:
            p_id, p_name = participant[0], participant[1]

            # Count sessions where this participant was present for this trainer
            present_row = conn.execute(
                sa.text(
                    "SELECT COUNT(*) FROM obecnosci o "
                    "JOIN zajecia z ON z.id = o.zajecia_id "
                    "WHERE o.uczestnik_id = :pid AND z.prowadzacy_id = :tid"
                ),
                {"pid": p_id, "tid": trainer_id},
            ).fetchone()
            sessions_present = present_row[0] if present_row else 0
            percent = (sessions_present / total_sessions * 100) if total_sessions else 0

            conn.execute(
                sa.text(
                    "INSERT INTO archived_participant "
                    "(project_id, participant_name, trainer_name, sessions_present, total_sessions, percent) "
                    "VALUES (:proj_id, :name, :trainer, :present, :total, :pct)"
                ),
                {
                    "proj_id": project_id,
                    "name": p_name,
                    "trainer": trainer_name,
                    "present": sessions_present,
                    "total": total_sessions,
                    "pct": round(percent, 1),
                },
            )

    # 3. Clear current participants (delete attendance links first, then participants)
    conn.execute(sa.text("DELETE FROM obecnosci"))
    conn.execute(sa.text("DELETE FROM uczestnik"))

    # 4. Add new participants to all existing trainers
    for trainer in trainers:
        trainer_id = trainer[0]
        for name in NEW_PARTICIPANTS:
            conn.execute(
                sa.text("INSERT INTO uczestnik (imie_nazwisko, prowadzacy_id) VALUES (:name, :tid)"),
                {"name": name, "tid": trainer_id},
            )

    # 5. Set project settings
    settings = [
        ("course_name", "ShareOKO IV"),
        ("project_total_hours", "60"),
        ("project_hourly_rate", "170"),
        ("project_start_date", datetime.utcnow().strftime("%Y-%m-%d")),
    ]
    for key, value in settings:
        existing = conn.execute(
            sa.text("SELECT key FROM setting WHERE key = :k"), {"k": key}
        ).fetchone()
        if existing:
            conn.execute(
                sa.text("UPDATE setting SET value = :v WHERE key = :k"),
                {"k": key, "v": value},
            )
        else:
            conn.execute(
                sa.text("INSERT INTO setting (key, value) VALUES (:k, :v)"),
                {"k": key, "v": value},
            )

    # 6. Update invoice settings for new project
    invoice_updates = [
        ("invoice_service_name", "Prowadzenie zajęć z tworzenia podcastów w ramach projektu ShareOKO IV"),
        ("invoice_hourly_rate", "170"),
    ]
    for key, value in invoice_updates:
        existing = conn.execute(
            sa.text("SELECT key FROM setting WHERE key = :k"), {"k": key}
        ).fetchone()
        if existing:
            conn.execute(
                sa.text("UPDATE setting SET value = :v WHERE key = :k"),
                {"k": key, "v": value},
            )
        else:
            conn.execute(
                sa.text("INSERT INTO setting (key, value) VALUES (:k, :v)"),
                {"k": key, "v": value},
            )


def downgrade():
    conn = op.get_bind()

    # Remove project settings
    for key in ("course_name", "project_total_hours", "project_hourly_rate", "project_start_date"):
        conn.execute(sa.text("DELETE FROM setting WHERE key = :k"), {"k": key})

    op.drop_table('archived_participant')
    op.drop_table('archived_project')
