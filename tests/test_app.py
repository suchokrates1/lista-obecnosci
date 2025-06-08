import os
import io
from PIL import Image
import pytest
from app import create_app
from model import db, Uzytkownik, Prowadzacy, Zajecia
from docx import Document
from datetime import datetime
import utils
from werkzeug.security import generate_password_hash

@pytest.fixture
def app(tmp_path):
    os.environ['SECRET_KEY'] = 'testsecret'
    os.environ['DATABASE_URL'] = 'sqlite:///' + str(tmp_path / 'test.db')
    os.environ['MAX_SIGNATURE_SIZE'] = '10'
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()


def test_routes_accessible(client):
    assert client.get('/login').status_code == 200
    assert client.get('/register').status_code == 200
    resp = client.get('/')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_register_missing_fields(client, app):
    resp = client.post('/register', data={}, follow_redirects=False)
    assert resp.status_code == 302
    with app.app_context():
        assert Uzytkownik.query.count() == 0


def test_register_invalid_email(client, app):
    data = {
        'imie': 'A',
        'nazwisko': 'B',
        'numer_umowy': '1',
        'lista_uczestnikow': 'X',
        'login': 'invalid',
        'haslo': 'pass'
    }
    resp = client.post('/register', data=data, follow_redirects=False)
    assert resp.status_code == 302
    with app.app_context():
        assert Uzytkownik.query.count() == 0


def test_register_bad_signature(client, app):
    data = {
        'imie': 'A',
        'nazwisko': 'B',
        'numer_umowy': '1',
        'lista_uczestnikow': 'X',
        'login': 'a@example.com',
        'haslo': 'pass',
        'podpis': (io.BytesIO(b'data'), 'sig.txt', 'text/plain')
    }
    resp = client.post('/register', data=data, content_type='multipart/form-data', follow_redirects=False)
    assert resp.status_code == 302
    with app.app_context():
        assert Uzytkownik.query.count() == 0


def test_register_too_large_signature(client, app):
    big = io.BytesIO(b'0123456789ABCDEF')
    data = {
        'imie': 'A',
        'nazwisko': 'B',
        'numer_umowy': '1',
        'lista_uczestnikow': 'X',
        'login': 'b@example.com',
        'haslo': 'pass',
        'podpis': (big, 'sig.png', 'image/png')
    }
    resp = client.post('/register', data=data, content_type='multipart/form-data', follow_redirects=False)
    assert resp.status_code == 302
    with app.app_context():
        assert Uzytkownik.query.count() == 0


def test_successful_register(client, app, monkeypatch):
    monkeypatch.setattr('routes.auth.send_plain_email', lambda *a, **k: None)
    monkeypatch.setattr(utils, 'SIGNATURE_MAX_SIZE', 1000)
    buf = io.BytesIO()
    Image.new('RGB', (1, 1), (255, 0, 0)).save(buf, format='PNG')
    buf.seek(0)
    data = {
        'imie': 'A',
        'nazwisko': 'B',
        'numer_umowy': '1',
        'lista_uczestnikow': 'X',
        'login': 'ok@example.com',
        'haslo': 'pass',
        'podpis': (buf, 'sig.png', 'image/png')
    }
    resp = client.post('/register', data=data, content_type='multipart/form-data', follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/login')
    with app.app_context():
        assert Uzytkownik.query.count() == 1



def test_login_success(client, app):
    with app.app_context():
        user = Uzytkownik(login='adm@example.com',
                           haslo_hash=generate_password_hash('secret'),
                           role='admin', approved=True)
        db.session.add(user)
        db.session.commit()
    resp = client.post('/login', data={'login': 'adm@example.com', 'hasło': 'secret'}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/admin')


def test_login_failure(client, app):
    with app.app_context():
        user = Uzytkownik(login='adm2@example.com',
                           haslo_hash=generate_password_hash('secret'),
                           role='admin', approved=True)
        db.session.add(user)
        db.session.commit()
    resp = client.post('/login', data={'login': 'adm2@example.com', 'hasło': 'bad'}, follow_redirects=False)
    assert resp.status_code == 200
    assert b'Nieprawid' in resp.data


def test_panel_requires_login(client):
    resp = client.get('/panel')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_panel_raport_requires_login(client):
    resp = client.get('/panel/raport')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def _create_trainer(app):
    """Create a trainer account with one session and return the login."""
    with app.app_context():
        prow = Prowadzacy(imie='T', nazwisko='T', numer_umowy='1', podpis_filename='sig.png')
        db.session.add(prow)
        db.session.flush()
        user = Uzytkownik(
            login='t@example.com',
            haslo_hash=generate_password_hash('pass'),
            role='prowadzacy',
            approved=True,
            prowadzacy_id=prow.id,
        )
        db.session.add(user)
        zaj = Zajecia(
            prowadzacy_id=prow.id,
            data=datetime(2023, 5, 1),
            czas_trwania=1.0,
        )
        db.session.add(zaj)
        db.session.commit()
        return user.login


def test_panel_raport_access_control(client, app):
    with app.app_context():
        user = Uzytkownik(
            login='a@example.com',
            haslo_hash=generate_password_hash('x'),
            role='admin',
            approved=True,
        )
        db.session.add(user)
        db.session.commit()
    client.post('/login', data={'login': 'a@example.com', 'hasło': 'x'}, follow_redirects=False)
    resp = client.get('/panel/raport')
    assert resp.status_code == 403


def test_panel_raport_download(client, app, monkeypatch):
    login_val = _create_trainer(app)

    def dummy_report(*_a, **_k):
        doc = Document()
        doc.add_paragraph('test')
        return doc

    monkeypatch.setattr('routes.panel.generuj_raport_miesieczny', dummy_report)

    client.post('/login', data={'login': login_val, 'hasło': 'pass'}, follow_redirects=False)
    resp = client.get('/panel/raport')
    assert resp.status_code == 200
    assert resp.mimetype == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    assert 'attachment' in resp.headers.get('Content-Disposition', '')
    assert 'raport_' in resp.headers.get('Content-Disposition', '')
    assert len(resp.data) > 0


def test_panel_raport_email_sending(client, app, monkeypatch):
    login_val = _create_trainer(app)

    def dummy_report(*_a, **_k):
        doc = Document()
        doc.add_paragraph('test')
        return doc

    sent = {}

    def fake_email(buf, data, typ=None):
        sent['called'] = True

    monkeypatch.setattr('routes.panel.generuj_raport_miesieczny', dummy_report)
    monkeypatch.setattr('routes.panel.email_do_koordynatora', fake_email)

    client.post('/login', data={'login': login_val, 'hasło': 'pass'}, follow_redirects=False)
    resp = client.get('/panel/raport?wyslij=1')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/panel')
    assert sent.get('called')
