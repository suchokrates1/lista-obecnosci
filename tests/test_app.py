import os
import io
from PIL import Image
import pytest
from app import create_app
from datetime import datetime, timedelta
from model import db, Uzytkownik, Prowadzacy, Zajecia, Uczestnik, PasswordResetToken
from docx import Document
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


def test_login_remember_sets_cookie(client, app):
    with app.app_context():
        user = Uzytkownik(
            login='perm@example.com',
            haslo_hash=generate_password_hash('secret'),
            role='admin',
            approved=True,
        )
        db.session.add(user)
        db.session.commit()

    resp = client.post(
        '/login',
        data={'login': 'perm@example.com', 'hasło': 'secret', 'remember': '1'},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    cookie = client._cookies.get(('localhost', '/', 'remember_token'))
    assert cookie is not None
    assert cookie.expires is not None


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


def test_admin_raport_bad_params(client, app):
    """Invalid month/year should return 400 for the admin route."""
    with app.app_context():
        prow = Prowadzacy(imie='A', nazwisko='B')
        db.session.add(prow)
        user = Uzytkownik(login='adm@example.com',
                           haslo_hash=generate_password_hash('secret'),
                           role='admin', approved=True)
        db.session.add(user)
        db.session.commit()
        prow_id = prow.id
        zaj = Zajecia(prowadzacy_id=prow_id,
                      data=datetime(2023, 1, 1),
                      czas_trwania=1.0)
        db.session.add(zaj)
        db.session.commit()
    client.post('/login', data={'login': 'adm@example.com', 'hasło': 'secret'})
    resp = client.get(f'/raport/{prow_id}?miesiac=13&rok=2023')
    assert resp.status_code == 400


def test_panel_raport_bad_params(client, app):
    """Invalid month/year should redirect with an error for the trainer route."""
    with app.app_context():
        prow = Prowadzacy(imie='T', nazwisko='X')
        db.session.add(prow)
        user = Uzytkownik(login='tr@example.com',
                           haslo_hash=generate_password_hash('secret'),
                           role='prowadzacy', approved=True,
                           prowadzacy=prow)
        db.session.add(user)
        db.session.commit()
        zaj = Zajecia(prowadzacy_id=prow.id,
                      data=datetime(2023, 1, 1),
                      czas_trwania=1.0)
        db.session.add(zaj)
        db.session.commit()
    client.post('/login', data={'login': 'tr@example.com', 'hasło': 'secret'})
    resp = client.get('/panel/raport?rok=1999')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/panel')
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


def test_wyslij_zajecie_requires_login(client):
    resp = client.get('/wyslij_zajecie/1')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_wyslij_zajecie_success(client, app, monkeypatch):
    login_val = _create_trainer(app)

    with app.app_context():
        zaj_id = Zajecia.query.first().id

    def dummy_list(*_a, **_k):
        doc = Document()
        doc.add_paragraph('x')
        return doc

    called = {}

    def fake_email(buf, data, typ=None):
        called['sent'] = True

    monkeypatch.setattr('routes.panel.generuj_liste_obecnosci', dummy_list)
    monkeypatch.setattr('routes.panel.email_do_koordynatora', fake_email)

    client.post('/login', data={'login': login_val, 'hasło': 'pass'}, follow_redirects=False)
    resp = client.get(f'/wyslij_zajecie/{zaj_id}')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/panel')
    assert called.get('sent')
    with app.app_context():
        assert Zajecia.query.get(zaj_id).wyslano is True


def test_wyslij_zajecie_admin_requires_login(client):
    resp = client.get('/wyslij_zajecie_admin/1')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_wyslij_zajecie_admin_success(client, app, monkeypatch):
    _ = _create_trainer(app)

    with app.app_context():
        admin = Uzytkownik(
            login='admin@example.com',
            haslo_hash=generate_password_hash('adm'),
            role='admin',
            approved=True,
        )
        db.session.add(admin)
        db.session.commit()
        zaj_id = Zajecia.query.first().id

    def dummy_list(*_a, **_k):
        doc = Document()
        doc.add_paragraph('x')
        return doc

    called = {}

    def fake_email(buf, data, typ=None):
        called['sent'] = True

    monkeypatch.setattr('routes.admin.generuj_liste_obecnosci', dummy_list)
    monkeypatch.setattr('routes.admin.email_do_koordynatora', fake_email)

    client.post('/login', data={'login': 'admin@example.com', 'hasło': 'adm'}, follow_redirects=False)
    resp = client.get(f'/wyslij_zajecie_admin/{zaj_id}')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/admin')
    assert called.get('sent')
    with app.app_context():
        assert Zajecia.query.get(zaj_id).wyslano is True


def test_wyslij_zajecie_admin_requires_admin(client, app):
    login_val = _create_trainer(app)

    with app.app_context():
        zaj_id = Zajecia.query.first().id

    client.post('/login', data={'login': login_val, 'hasło': 'pass'}, follow_redirects=False)
    resp = client.get(f'/wyslij_zajecie_admin/{zaj_id}')
    assert resp.status_code == 403


def test_admin_dashboard_filter(client, app):
    with app.app_context():
        p1 = Prowadzacy(imie='A', nazwisko='A')
        p2 = Prowadzacy(imie='B', nazwisko='B')
        db.session.add_all([p1, p2])
        db.session.flush()
        z1 = Zajecia(prowadzacy_id=p1.id, data=datetime(2023, 1, 1), czas_trwania=1.0)
        z2 = Zajecia(prowadzacy_id=p2.id, data=datetime(2023, 1, 2), czas_trwania=2.0)
        db.session.add_all([z1, z2])
        admin = Uzytkownik(
            login='adminf@example.com',
            haslo_hash=generate_password_hash('adm'),
            role='admin',
            approved=True,
        )
        db.session.add(admin)
        db.session.commit()
        pid = p1.id

    client.post('/login', data={'login': 'adminf@example.com', 'hasło': 'adm'}, follow_redirects=False)
    resp = client.get(f'/admin?p_id={pid}')
    assert resp.status_code == 200
    data = resp.data.decode()
    assert '2023-01-01' in data
    assert '2023-01-02' not in data


def test_update_default_time(client, app):
    login_val = _create_trainer(app)
    client.post('/login', data={'login': login_val, 'hasło': 'pass'}, follow_redirects=False)
    resp = client.post('/panel/profil', data={
        'imie': 'T',
        'nazwisko': 'T',
        'numer_umowy': '1',
        'domyslny_czas': '2,5',
    }, follow_redirects=False)
    assert resp.status_code == 302
    with app.app_context():
        prow = Prowadzacy.query.first()
        assert prow.domyslny_czas == 2.5


def test_usun_uczestnika_requires_login(client, app):
    with app.app_context():
        prow = Prowadzacy(imie='A')
        db.session.add(prow)
        db.session.flush()
        u = Uczestnik(imie_nazwisko='X', prowadzacy_id=prow.id)
        db.session.add(u)
        db.session.commit()
        uid = u.id

    resp = client.post(f'/usun_uczestnika/{uid}')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_usun_uczestnika_forbidden(client, app):
    login_val = _create_trainer(app)
    with app.app_context():
        prow2 = Prowadzacy(imie='B')
        db.session.add(prow2)
        db.session.flush()
        user2 = Uzytkownik(login='t2@example.com', haslo_hash=generate_password_hash('x'), role='prowadzacy', approved=True, prowadzacy_id=prow2.id)
        db.session.add(user2)
        u = Uczestnik(imie_nazwisko='Z', prowadzacy_id=prow2.id)
        db.session.add(u)
        db.session.commit()
        uid = u.id

    client.post('/login', data={'login': login_val, 'hasło': 'pass'}, follow_redirects=False)
    resp = client.post(f'/usun_uczestnika/{uid}')
    assert resp.status_code == 403


def test_trainer_delete_participant(client, app):
    login_val = _create_trainer(app)
    with app.app_context():
        prow = Prowadzacy.query.first()
        u = Uczestnik(imie_nazwisko='P', prowadzacy_id=prow.id)
        db.session.add(u)
        db.session.commit()
        uid = u.id

    client.post('/login', data={'login': login_val, 'hasło': 'pass'}, follow_redirects=False)
    resp = client.post(f'/usun_uczestnika/{uid}', follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/panel')
    with app.app_context():
        assert Uczestnik.query.get(uid) is None


def test_reset_request_purges_expired_token(client, app, monkeypatch):
    with app.app_context():
        user = Uzytkownik(
            login='purge@example.com',
            haslo_hash=generate_password_hash('x'),
            role='admin',
            approved=True,
        )
        db.session.add(user)
        db.session.flush()
        uid = user.id
        t = PasswordResetToken(
            user_id=user.id,
            token='old',
            expires_at=datetime.utcnow() - timedelta(hours=2),
        )
        db.session.add(t)
        db.session.commit()

    monkeypatch.setattr('routes.auth.send_plain_email', lambda *a, **k: None)
    resp = client.post('/reset-request', data={'login': 'purge@example.com'})
    assert resp.status_code == 302
    with app.app_context():
        tokens = PasswordResetToken.query.filter_by(user_id=uid).all()
        assert len(tokens) == 1
        assert tokens[0].token != 'old'


def test_reset_with_token_purges_expired(client, app):
    with app.app_context():
        user = Uzytkownik(
            login='tok@example.com',
            haslo_hash=generate_password_hash('x'),
            role='admin',
            approved=True,
        )
        db.session.add(user)
        db.session.flush()
        expired = PasswordResetToken(
            user_id=user.id,
            token='old',
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        valid = PasswordResetToken(
            user_id=user.id,
            token='good',
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db.session.add_all([expired, valid])
        db.session.commit()
        token_value = valid.token

    resp = client.get(f'/reset/{token_value}')
    assert resp.status_code == 200
    with app.app_context():
        assert PasswordResetToken.query.filter_by(token='old').first() is None
        assert PasswordResetToken.query.filter_by(token=token_value).first() is not None


def test_panel_summary_table_links(client, app):
    login_val = _create_trainer(app)
    client.post('/login', data={'login': login_val, 'hasło': 'pass'}, follow_redirects=False)
    resp = client.get('/panel')
    assert resp.status_code == 200
    data = resp.data.decode()
    assert 'Raporty miesięczne' in data
    assert '/panel/raport?rok=2023&miesiac=5' in data
    assert '/panel/raport?rok=2023&miesiac=5&wyslij=1' in data


def test_panel_statystyki_requires_login(client):
    resp = client.get('/panel/statystyki')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_panel_statystyki_data(client, app):
    login_val = _create_trainer(app)
    with app.app_context():
        prow = Prowadzacy.query.first()
        u1 = Uczestnik(imie_nazwisko='A', prowadzacy_id=prow.id)
        u2 = Uczestnik(imie_nazwisko='B', prowadzacy_id=prow.id)
        db.session.add_all([u1, u2])
        zaj = Zajecia.query.first()
        zaj.obecni.append(u1)
        db.session.commit()

    client.post('/login', data={'login': login_val, 'hasło': 'pass'}, follow_redirects=False)
    resp = client.get('/panel/statystyki')
    assert resp.status_code == 200
    data = resp.data.decode()
    assert 'A' in data and '1/1' in data and '100%' in data
    assert 'B' in data and '0/1' in data and '0%' in data
