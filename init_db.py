from app import create_app
from model import db, Uzytkownik
from werkzeug.security import generate_password_hash
import os

app = create_app()
with app.app_context():
    db.create_all()

    admin_login = os.getenv("ADMIN_LOGIN")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not Uzytkownik.query.filter_by(login=admin_login).first():
        hashed = generate_password_hash(admin_password)
        admin = Uzytkownik(login=admin_login, haslo_hash=hashed, rola="admin")
        db.session.add(admin)
        db.session.commit()
        print(f"✔ Użytkownik administratora '{admin_login}' został dodany.")
    else:
        print(f"ℹ Użytkownik '{admin_login}' już istnieje.")

    print("✔ Baza danych została zainicjalizowana.")
