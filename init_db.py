from app import create_app
from model import db, Uzytkownik
from werkzeug.security import generate_password_hash
import os
import logging

logger = logging.getLogger(__name__)

app = create_app()
with app.app_context():
    db.create_all()

    admin_login = os.getenv("ADMIN_LOGIN")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not Uzytkownik.query.filter_by(login=admin_login).first():
        hashed = generate_password_hash(admin_password)
        admin = Uzytkownik(login=admin_login, haslo_hash=hashed)
        db.session.add(admin)
        db.session.commit()
        logger.debug("✔ Użytkownik administratora '%s' został dodany.", admin_login)
    else:
        logger.debug("ℹ Użytkownik '%s' już istnieje.", admin_login)

    logger.debug("✔ Baza danych została zainicjalizowana.")
