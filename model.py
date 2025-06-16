from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime







db = SQLAlchemy()

# Tabela pośrednia
obecnosci = db.Table('obecnosci',
    db.Column('zajecia_id', db.Integer, db.ForeignKey('zajecia.id')),
    db.Column('uczestnik_id', db.Integer, db.ForeignKey('uczestnik.id'))
)

class Prowadzacy(db.Model):
    __tablename__ = "prowadzacy"
    id = db.Column(db.Integer, primary_key=True)
    imie = db.Column(db.String)
    nazwisko = db.Column(db.String)
    numer_umowy = db.Column(db.String)  # Dodane pole
    nazwa_zajec = db.Column(db.String)
    podpis_filename = db.Column(db.String)
    domyslny_czas = db.Column(db.Float)

    uczestnicy = db.relationship("Uczestnik", back_populates="prowadzacy", cascade="all, delete-orphan")
    zajecia = db.relationship("Zajecia", back_populates="prowadzacy", cascade="all, delete-orphan")
    user = db.relationship("Uzytkownik", back_populates="prowadzacy", uselist=False)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Prowadzacy id={self.id} imie='{self.imie}'>"

class Uczestnik(db.Model):
    __tablename__ = "uczestnik"
    id = db.Column(db.Integer, primary_key=True)
    imie_nazwisko = db.Column(db.String)
    prowadzacy_id = db.Column(db.Integer, db.ForeignKey("prowadzacy.id"))

    prowadzacy = db.relationship("Prowadzacy", back_populates="uczestnicy")
    zajecia = db.relationship("Zajecia", secondary=obecnosci, back_populates="obecni")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Uczestnik id={self.id} imie_nazwisko='{self.imie_nazwisko}'>"

class Zajecia(db.Model):
    __tablename__ = "zajecia"
    id = db.Column(db.Integer, primary_key=True)
    prowadzacy_id = db.Column(db.Integer, db.ForeignKey("prowadzacy.id"))
    data = db.Column(db.DateTime)
    czas_trwania = db.Column(db.Float)
    wyslano = db.Column(db.Boolean, default=False)

    prowadzacy = db.relationship("Prowadzacy", back_populates="zajecia")
    obecni = db.relationship("Uczestnik", secondary=obecnosci, back_populates="zajecia")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        dt = self.data.strftime('%Y-%m-%d') if isinstance(self.data, datetime) else self.data
        return f"<Zajecia id={self.id} data={dt}>"

class Uzytkownik(UserMixin, db.Model):
    __tablename__ = "uzytkownik"
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String, unique=True, nullable=False)
    haslo_hash = db.Column(db.String, nullable=False)
    role = db.Column(db.String, nullable=False)
    approved = db.Column(db.Boolean, default=False)
    prowadzacy_id = db.Column(db.Integer, db.ForeignKey("prowadzacy.id"))

    prowadzacy = db.relationship("Prowadzacy", back_populates="user")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Uzytkownik id={self.id} login='{self.login}'>"


class Setting(db.Model):
    """Arbitrary key/value configuration setting.

    Known keys include SMTP and e-mail options such as ``smtp_host``,
    ``smtp_port`` and ``email_recipient`` as well as message templates:
    ``email_sender_name``, ``email_login``, ``email_password``, ``email_footer``
    and individual subjects/bodies for outgoing messages.  These include
    ``email_list_subject``/``email_list_body``,
    ``email_report_subject``/``email_report_body``,
    ``registration_email_subject``/``registration_email_body``,
    ``reg_email_subject``/``reg_email_body`` and
    ``reset_email_subject``/``reset_email_body``.
    """

    __tablename__ = "setting"
    key = db.Column(db.String, primary_key=True)
    value = db.Column(db.String)


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_token"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("uzytkownik.id"), nullable=False)
    token = db.Column(db.String, unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    user = db.relationship("Uzytkownik")

def init_db(app):
    with app.app_context():
        db.create_all()

def get_all_prowadzacych():
    return Prowadzacy.query.all()

def get_prowadzacy_by_id(id):
    return Prowadzacy.query.filter_by(id=id).first()

def get_uczestnicy_by_prowadzacy(prowadzacy_id):
    return Uczestnik.query.filter_by(prowadzacy_id=prowadzacy_id).all()

def get_zajecia_for_prowadzacy(prowadzacy_id):
    return Zajecia.query.filter_by(prowadzacy_id=prowadzacy_id).all()

def add_zajecie(prowadzacy_id, data, czas, obecni_uczestnicy):
    zajecie = Zajecia(prowadzacy_id=prowadzacy_id, data=data, czas_trwania=czas)
    zajecie.obecni.extend(obecni_uczestnicy)
    db.session.add(zajecie)
    db.session.commit()

def add_or_update_prowadzacy(id=None, imie=None, nazwisko=None, podpis_filename=None, numer_umowy=None, domyslny_czas=None, uczestnicy_lista=None):
    if id:
        prowadzacy = get_prowadzacy_by_id(id)
        if not prowadzacy:
            return None
        prowadzacy.uczestnicy.clear()
    else:
        prowadzacy = Prowadzacy()

    prowadzacy.imie = imie
    prowadzacy.nazwisko = nazwisko
    prowadzacy.podpis_filename = podpis_filename
    prowadzacy.numer_umowy = numer_umowy
    if domyslny_czas is not None:
        try:
            prowadzacy.domyslny_czas = float(str(domyslny_czas).replace(',', '.'))
        except ValueError:
            prowadzacy.domyslny_czas = None
    else:
        prowadzacy.domyslny_czas = domyslny_czas

    if uczestnicy_lista:
        for u in uczestnicy_lista:
            uczestnik = Uczestnik(imie_nazwisko=u)
            prowadzacy.uczestnicy.append(uczestnik)

    db.session.add(prowadzacy)
    db.session.commit()
    return prowadzacy

def delete_prowadzacy(id):
    prowadzacy = get_prowadzacy_by_id(id)
    if prowadzacy:
        db.session.delete(prowadzacy)
        db.session.commit()
        return True
    return False
