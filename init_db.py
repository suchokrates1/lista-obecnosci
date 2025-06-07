from app import create_app
from model import db, Uzytkownik
from werkzeug.security import generate_password_hash
import os

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
        print(f"✔ Użytkownik administratora '{admin_login}' został dodany.")
    else:
        admin_user.role = "admin"
        admin_user.approved = True
        db.session.commit()
        print(f"ℹ Użytkownik '{admin_login}' już istnieje.")

    print("✔ Baza danych została zainicjalizowana.")
