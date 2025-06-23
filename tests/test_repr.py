import os
from datetime import datetime
from pathlib import Path

import pytest

from app import create_app
from model import db, Prowadzacy, Uczestnik, Zajecia, Uzytkownik
from werkzeug.security import generate_password_hash


@pytest.fixture
def app(tmp_path):
    os.environ['SECRET_KEY'] = 'testsecret'
    os.environ['DATABASE_URL'] = 'sqlite:///' + str(tmp_path / 'test.db')
    os.environ['MAX_SIGNATURE_SIZE'] = '10'
    os.environ['SMTP_HOST'] = 'smtp'
    os.environ['SMTP_PORT'] = '25'
    os.environ['EMAIL_LOGIN'] = 'user'
    os.environ['EMAIL_PASSWORD'] = 'pass'
    Path('szablon.docx').touch()
    Path('rejestr.docx').touch()
    application = create_app()
    application.config['WTF_CSRF_ENABLED'] = False
    try:
        with application.app_context():
            db.create_all()
            yield application
            db.session.remove()
            db.drop_all()
    finally:
        Path('szablon.docx').unlink(missing_ok=True)
        Path('rejestr.docx').unlink(missing_ok=True)


def test_model_repr(app):
    with app.app_context():
        prow = Prowadzacy(imie='Jan', nazwisko='Kowalski')
        db.session.add(prow)
        db.session.flush()

        uc = Uczestnik(imie_nazwisko='Anna', prowadzacy_id=prow.id)
        zaj = Zajecia(prowadzacy_id=prow.id, data=datetime(2023, 1, 1), czas_trwania=1.0)
        user = Uzytkownik(login='jan@example.com', haslo_hash=generate_password_hash('x'), role='admin')
        db.session.add_all([uc, zaj, user])
        db.session.commit()

        assert repr(prow) == f"<Prowadzacy id={prow.id} imie='Jan'>"
        assert f"imie_nazwisko='Anna'" in repr(uc)
        assert "data=2023-01-01" in repr(zaj)
        assert "login='jan@example.com'" in repr(user)
