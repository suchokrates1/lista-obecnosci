from app import create_app
from model import db, Uzytkownik
from werkzeug.security import generate_password_hash
import logging
import os

logger = logging.getLogger(__name__)

app = create_app()
with app.app_context():
    db.create_all()

    admin_login = os.getenv("ADMIN_LOGIN")
    admin_password = os.getenv("ADMIN_PASSWORD")

    admin_user = Uzytkownik.query.filter_by(login=admin_login).first()
    if not admin_user:
        hashed = generate_password_hash(admin_password)
        admin_user = Uzytkownik(
            login=admin_login,
            haslo_hash=hashed,
            role="admin",
            approved=True,
        )
        db.session.add(admin_user)
        db.session.commit()
        logger.debug("✔ Użytkownik administratora '%s' został dodany.", admin_login)
    else:
        admin_user.role = "admin"
        admin_user.approved = True
        db.session.commit()
        logger.debug("ℹ Użytkownik '%s' już istnieje.", admin_login)

    logger.debug("✔ Baza danych została zainicjalizowana.")
