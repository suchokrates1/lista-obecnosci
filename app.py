from flask import Flask, jsonify, render_template
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from flask_wtf import CSRFProtect
from dotenv import load_dotenv
from contextlib import contextmanager
import logging
import os
from model import db, Uzytkownik, Prowadzacy, Zajecia
from utils import (
    load_db_settings,
    purge_expired_tokens,
    email_do_koordynatora,
    month_name,
)
from doc_generator import generuj_raport_miesieczny
from io import BytesIO
import smtplib
import click

logger = logging.getLogger(__name__)

load_dotenv()

migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "routes.login"  # Redirect to login page when unauthorized
csrf = CSRFProtect()


def inject_is_admin():
    """Expose an ``is_admin`` flag to all templates."""
    return {"is_admin": current_user.is_authenticated and current_user.role == "admin"}


def inject_table_widths():
    from utils import TABLE_COLUMN_WIDTHS
    return {"table_widths": TABLE_COLUMN_WIDTHS}


def inject_course_name():
    """Expose the configurable project name to all templates."""
    return {"course_name": os.getenv("COURSE_NAME", "ShareOKO")}


@contextmanager
def temporary_env_var(name: str, value: str | None):
    previous = os.environ.get(name)
    if value is None:
        yield
        return
    os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def create_app():
    logging.basicConfig(level=logging.INFO)
    app = Flask(__name__)
    default_database_url = f"sqlite:///{os.path.join(app.instance_path, 'obecnosc.db')}"

    # Konfiguracja aplikacji
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY environment variable must be set")
    app.config["SECRET_KEY"] = secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", default_database_url
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Inicjalizacja rozszerzeń
    db.init_app(app)
    migrate.init_app(app, db)
    load_db_settings(app)

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    email_login = os.getenv("EMAIL_LOGIN")
    email_password = os.getenv("EMAIL_PASSWORD")

    try:
        int(smtp_port or "")
    except ValueError:
        logger.error("Invalid SMTP_PORT: %s", smtp_port)
        raise RuntimeError("Invalid SMTP_PORT")

    missing = [
        v
        for v, val in {
            "SMTP_HOST": smtp_host,
            "SMTP_PORT": smtp_port,
            "EMAIL_LOGIN": email_login,
            "EMAIL_PASSWORD": email_password,
        }.items()
        if not val
    ]
    if missing:
        logger.error("Missing mail configuration: %s", ", ".join(missing))
        raise RuntimeError("Incomplete mail configuration")

    # Ensure required document templates are available
    from doc_generator import ensure_template_exists

    for template in ("szablon.docx", "rejestr.docx"):
        ensure_template_exists(template)

    login_manager.init_app(app)
    csrf.init_app(app)

    # Rejestracja blueprintów
    from routes import routes_bp

    app.register_blueprint(routes_bp)

    app.context_processor(inject_is_admin)
    app.context_processor(inject_table_widths)
    app.context_processor(inject_course_name)
    app.add_template_filter(month_name, "month_name")

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.cli.command("purge-tokens")
    def purge_tokens_command() -> None:
        """Remove expired password reset tokens."""
        purge_expired_tokens()
        click.echo("Expired tokens removed")

    @app.cli.command("generate-reports")
    @click.option("--month", required=True, type=int, help="Month number (1-12)")
    @click.option("--year", required=True, type=int, help="Full year")
    @click.option("--email", is_flag=True, help="Send reports via e-mail")
    def generate_reports_command(month: int, year: int, email: bool) -> None:
        """Generate monthly reports for all trainers."""
        if not 1 <= month <= 12 or year < 2000:
            raise click.BadParameter("Invalid month or year")

        reports_dir = os.path.join("reports")
        os.makedirs(reports_dir, exist_ok=True)

        with app.app_context():
            trainers = (
                db.session.query(Prowadzacy)
                .join(Zajecia)
                .filter(
                    db.extract("month", Zajecia.data) == month,
                    db.extract("year", Zajecia.data) == year,
                )
                .distinct()
                .all()
            )

            for trainer in trainers:
                sessions = Zajecia.query.filter_by(prowadzacy_id=trainer.id).all()
                doc = generuj_raport_miesieczny(
                    trainer, sessions, "rejestr.docx", "static", month, year
                )

                filename = f"raport_{trainer.id}_{month}_{year}.docx"
                path = os.path.join(reports_dir, filename)
                doc.save(path)
                click.echo(f"Saved {path}")

                if email:
                    buf = BytesIO()
                    doc.save(buf)
                    buf.seek(0)

                    # Automatyczne generowanie faktury
                    invoice_pdf_buffer = None
                    from invoice_helper import generate_invoice_for_report
                    invoice_success, invoice_msg, invoice_pdf_buffer = generate_invoice_for_report(
                        month=month,
                        year=year,
                        prowadzacy_id=trainer.id,
                        trainer_name=f"{trainer.imie} {trainer.nazwisko}"
                    )

                    if invoice_success:
                        click.echo(f"Invoice: {invoice_msg}")
                    else:
                        click.echo(f"Invoice error: {invoice_msg}", err=True)

                    # Wysyłanie emaila z raportem i fakturą
                    try:
                        email_do_koordynatora(
                            buf,
                            f"{month}_{year}",
                            typ="raport",
                            trainer=trainer,
                            invoice_pdf_buf=invoice_pdf_buffer
                        )
                        click.echo(f"Sent {filename}")
                        if invoice_pdf_buffer:
                            click.echo("Invoice PDF attached to email")

                    except smtplib.SMTPException:
                        logger.exception("Failed to send report e-mail")
                        click.echo(f"Failed to send e-mail for {filename}", err=True)

    @app.cli.command("send-demo-invoice")
    @click.option("--month", required=True, type=int, help="Month number (1-12)")
    @click.option("--year", required=True, type=int, help="Full year")
    @click.option("--trainer-id", required=True, type=int, help="Trainer ID")
    @click.option("--email-to", type=str, help="Override EMAIL_RECIPIENT for this run")
    def send_demo_invoice_command(month: int, year: int, trainer_id: int, email_to: str | None) -> None:
        """Generate report, invoice PDF and run KSeF demo flow for one trainer."""
        if not 1 <= month <= 12 or year < 2000:
            raise click.BadParameter("Invalid month or year")

        with app.app_context():
            trainer = db.session.get(Prowadzacy, trainer_id)
            if trainer is None:
                raise click.BadParameter(f"Trainer {trainer_id} not found")

            sessions = Zajecia.query.filter_by(prowadzacy_id=trainer.id).all()
            doc = generuj_raport_miesieczny(
                trainer,
                sessions,
                "rejestr.docx",
                "static",
                month,
                year,
            )

            report_buffer = BytesIO()
            doc.save(report_buffer)
            report_buffer.seek(0)

            from invoice_helper import generate_invoice_for_report

            invoice_success, invoice_message, invoice_pdf_buffer = generate_invoice_for_report(
                month=month,
                year=year,
                prowadzacy_id=trainer.id,
                trainer_name=f"{trainer.imie} {trainer.nazwisko}",
            )

            if not invoice_success:
                raise click.ClickException(invoice_message)

            click.echo(invoice_message)

            with temporary_env_var("EMAIL_RECIPIENT", email_to):
                try:
                    email_do_koordynatora(
                        report_buffer,
                        f"{month}_{year}",
                        typ="raport",
                        trainer=trainer,
                        invoice_pdf_buf=invoice_pdf_buffer,
                    )
                except smtplib.SMTPException as error:
                    logger.exception("Failed to send demo invoice e-mail")
                    raise click.ClickException(str(error)) from error

            if email_to:
                click.echo(f"Email sent to {email_to}")
            else:
                click.echo("Email sent to configured coordinator address")

    @app.errorhandler(403)
    def forbidden(_):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(_):
        return render_template("404.html"), 404

    return app


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Uzytkownik, int(user_id))


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000)
