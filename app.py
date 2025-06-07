from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from dotenv import load_dotenv
import logging
import os
from model import db, Uzytkownik

load_dotenv()

migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "routes.login"  # Redirect to login page when unauthorized
csrf = CSRFProtect()

def create_app():
    logging.basicConfig(level=logging.INFO)
    app = Flask(__name__)

    # Konfiguracja aplikacji
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///obecnosc.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Inicjalizacja rozszerzeń
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Rejestracja blueprintów
    from routes import routes_bp
    app.register_blueprint(routes_bp)

    @app.errorhandler(403)
    def forbidden(_):
        return render_template('403.html'), 403

    @app.errorhandler(404)
    def not_found(_):
        return render_template('404.html'), 404

    return app

@login_manager.user_loader
def load_user(user_id):
    return Uzytkownik.query.get(int(user_id))

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000)
