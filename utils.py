from model import db, Zajecia, Uczestnik
from sqlalchemy.exc import OperationalError
from doc_generator import generuj_liste_obecnosci
from io import BytesIO
from datetime import datetime
import os
import smtplib
import logging
from email.message import EmailMessage
import re

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Allowed signature upload formats
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg"}

# Maximum allowed size of uploaded signature files in bytes
SIGNATURE_MAX_SIZE = int(os.getenv("MAX_SIGNATURE_SIZE", 1024 * 1024))
# Whether to clean white background from signatures
REMOVE_SIGNATURE_BG = os.getenv("REMOVE_SIGNATURE_BG", "0").lower() in {"1", "true", "yes"}


def load_db_settings(app) -> None:
    """Load configuration from the Setting table into ``os.environ``.

    All entries from :class:`~model.Setting` are loaded into environment
    variables named after the key in upper case, e.g. ``email_list_subject``
    becomes ``EMAIL_LIST_SUBJECT``.
    """
    from model import Setting  # imported lazily to avoid circular imports

    with app.app_context():
        try:
            settings = Setting.query.all()
        except OperationalError:
            logger.warning("Settings table missing, skipping load.")
            settings = []

        for setting in settings:
            os.environ[setting.key.upper()] = setting.value

    global SIGNATURE_MAX_SIZE, REMOVE_SIGNATURE_BG
    SIGNATURE_MAX_SIZE = int(os.getenv("MAX_SIGNATURE_SIZE", 1024 * 1024))
    REMOVE_SIGNATURE_BG = os.getenv("REMOVE_SIGNATURE_BG", "0").lower() in {"1", "true", "yes"}


def is_valid_email(value: str) -> bool:
    """Return True if ``value`` looks like a valid e-mail address."""
    if not isinstance(value, str):
        return False
    return bool(EMAIL_REGEX.match(value))

def przetworz_liste_obecnosci(form, wybrany):
    data_str = form.get("data")
    czas = form.get("czas")
    obecni_ids = form.getlist("obecny")

    if not wybrany or not data_str or not czas:
        return ("error", "Brakuje wymaganych danych")

    obecni_uczestnicy = Uczestnik.query.filter(Uczestnik.id.in_(obecni_ids)).all()
    docx_obj = generuj_liste_obecnosci(
        data_str,
        czas,
        sorted([ucz.imie_nazwisko for ucz in obecni_uczestnicy], key=str.lower),
        f"{wybrany.imie} {wybrany.nazwisko}",
        os.path.join("static", wybrany.podpis_filename)
    )

    buf = BytesIO()
    docx_obj.save(buf)
    buf.seek(0)

    data = datetime.strptime(data_str, "%Y-%m-%d").date()
    try:
        czas_float = float(czas.replace(",", "."))
    except ValueError:
        czas_float = 0

    zajecia = Zajecia(data=data, czas_trwania=czas_float, prowadzacy_id=wybrany.id)
    zajecia.obecni.extend(obecni_uczestnicy)
    db.session.add(zajecia)
    db.session.commit()

    return ("success", buf, data_str)

def email_do_koordynatora(buf, data, typ="lista"):
    odbiorca = os.getenv("EMAIL_RECIPIENT")
    if not odbiorca:
        logger.warning("EMAIL_RECIPIENT not configured, skipping mail send.")
        return

    msg = EmailMessage()

    if typ == "raport":
        subject_tmpl = os.getenv("EMAIL_REPORT_SUBJECT", "Raport miesięczny – {date}")
        body_tmpl = os.getenv("EMAIL_REPORT_BODY", "W załączniku raport miesięczny do umowy.")
        filename = f"raport_{data}.docx"
    else:
        subject_tmpl = os.getenv("EMAIL_LIST_SUBJECT", "Lista obecności – {date}")
        body_tmpl = os.getenv("EMAIL_LIST_BODY", "W załączniku lista obecności z zajęć.")
        filename = f"lista_{data}.docx"
    msg["Subject"] = subject_tmpl.format(date=data)
    body = body_tmpl.format(date=data)

    footer = os.getenv("EMAIL_FOOTER", "")
    if footer:
        body = f"{body}\n\n{footer}"
    msg.set_content(body)

    sender_name = os.getenv("EMAIL_SENDER_NAME", "Vest Media")
    login = os.getenv("EMAIL_LOGIN")
    password = os.getenv("EMAIL_PASSWORD")
    msg["From"] = f"{sender_name} <{login}>"
    msg["To"] = odbiorca

    buf.seek(0)
    msg.add_attachment(
        buf.read(),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename
    )

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT"))

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port) as smtp:
                smtp.login(login, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port) as smtp:
                smtp.starttls()
                smtp.login(login, password)
                smtp.send_message(msg)
        logger.info("Mail sent to %s", odbiorca)
    except smtplib.SMTPException as e:
        logger.exception("Failed to send email: %s", e)
        raise


def send_plain_email(
    to_addr: str,
    subject_key: str,
    body_key: str,
    default_subject: str,
    default_body: str,
    **fmt,
) -> None:
    """Send a simple text e-mail using templates from environment variables."""
    subject = os.getenv(subject_key, default_subject).format(**fmt)
    body = os.getenv(body_key, default_body).format(**fmt)
    msg = EmailMessage()
    msg["Subject"] = subject
    footer = os.getenv("EMAIL_FOOTER", "")
    if footer:
        body = f"{body}\n\n{footer}"
    msg.set_content(body)
    sender_name = os.getenv("EMAIL_SENDER_NAME", "Vest Media")
    login = os.getenv("EMAIL_LOGIN")
    password = os.getenv("EMAIL_PASSWORD")
    msg["From"] = f"{sender_name} <{login}>"
    msg["To"] = to_addr

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT"))

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port) as smtp:
                smtp.login(login, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port) as smtp:
                smtp.starttls()
                smtp.login(login, password)
                smtp.send_message(msg)
        logger.info("Mail sent to %s", to_addr)
    except smtplib.SMTPException as e:
        logger.exception("Failed to send email: %s", e)
        raise
