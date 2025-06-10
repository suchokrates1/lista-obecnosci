import io
from werkzeug.datastructures import FileStorage
from PIL import Image
from datetime import datetime, timedelta
import os

import utils
import pytest
from utils import is_valid_email
from model import db, Uzytkownik, PasswordResetToken
from werkzeug.security import generate_password_hash
from app import create_app


@pytest.fixture
def app(tmp_path):
    os.environ['SECRET_KEY'] = 'testsecret'
    os.environ['DATABASE_URL'] = 'sqlite:///' + str(tmp_path / 'test.db')
    os.environ['MAX_SIGNATURE_SIZE'] = '10'
    os.environ['SMTP_HOST'] = 'smtp'
    os.environ['SMTP_PORT'] = '25'
    os.environ['EMAIL_LOGIN'] = 'user'
    os.environ['EMAIL_PASSWORD'] = 'pass'
    application = create_app()
    application.config['WTF_CSRF_ENABLED'] = False
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_is_valid_email():
    assert is_valid_email('user@example.com')
    assert not is_valid_email('invalid')
    assert not is_valid_email('a@')


def test_validate_signature_ok(monkeypatch):
    monkeypatch.setattr(utils, 'SIGNATURE_MAX_SIZE', 10)
    fs = FileStorage(io.BytesIO(b'x'), filename='sig.png', content_type='image/png')
    name, error = utils.validate_signature(fs)
    assert name == 'sig.png'
    assert error is None


def test_validate_signature_bad_extension(monkeypatch):
    monkeypatch.setattr(utils, 'SIGNATURE_MAX_SIZE', 10)
    fs = FileStorage(io.BytesIO(b'x'), filename='sig.txt', content_type='text/plain')
    name, error = utils.validate_signature(fs)
    assert name is None
    assert error


def test_validate_signature_too_big(monkeypatch):
    monkeypatch.setattr(utils, 'SIGNATURE_MAX_SIZE', 1)
    fs = FileStorage(io.BytesIO(b'ab'), filename='sig.png', content_type='image/png')
    name, error = utils.validate_signature(fs)
    assert name is None
    assert error


def test_process_signature(monkeypatch, tmp_path):
    monkeypatch.setattr(utils, 'REMOVE_SIGNATURE_BG', False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'static').mkdir()
    img = Image.new('RGB', (1, 1), (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    filename = utils.process_signature(buf)
    saved = tmp_path / 'static' / filename
    assert saved.exists()
    out = Image.open(saved)
    assert out.format == 'PNG'

def test_validate_signature_none():
    name, error = utils.validate_signature(None)
    assert name is None
    assert error is None


class FailingStream(io.BytesIO):
    def seek(self, *a, **k):
        raise IOError('fail')


def test_validate_signature_exception():
    fs = FileStorage(FailingStream(b'x'), filename='sig.png', content_type='image/png')
    with pytest.raises(utils.SignatureValidationError):
        utils.validate_signature(fs)


def test_send_plain_email_queue(monkeypatch):
    called = {}

    def fake_send(msg):
        called['to'] = msg['To']

    monkeypatch.setattr(utils, '_send_message', fake_send)
    utils.send_plain_email(
        'x@example.com',
        'SUBJ',
        'BODY',
        's',
        'b',
        queue=True,
    )
    utils.shutdown_email_worker()
    assert called.get('to') == 'x@example.com'
    assert utils._worker is None or not utils._worker.is_alive()


def test_purge_expired_tokens(app):
    with app.app_context():
        user = Uzytkownik(
            login='exp@example.com',
            haslo_hash=generate_password_hash('x'),
            role='admin',
            approved=True,
        )
        db.session.add(user)
        db.session.flush()
        past = datetime.utcnow() - timedelta(hours=2)
        future = datetime.utcnow() + timedelta(hours=1)
        t1 = PasswordResetToken(user_id=user.id, token='old', expires_at=past)
        t2 = PasswordResetToken(user_id=user.id, token='new', expires_at=future)
        db.session.add_all([t1, t2])
        db.session.commit()

        utils.purge_expired_tokens()

        assert PasswordResetToken.query.filter_by(token='old').first() is None
        assert PasswordResetToken.query.filter_by(token='new').first() is not None
