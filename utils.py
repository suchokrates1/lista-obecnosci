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
from werkzeug.utils import secure_filename
import uuid
from PIL import Image
try:
    from rembg import remove as rembg_remove  # type: ignore
except Exception:  # rembg is optional
    rembg_remove = None

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


class SignatureValidationError(Exception):
    """Raised when validating an uploaded signature fails."""


def validate_signature(file):
    """Validate an uploaded signature file.

    Returns ``(sanitized_filename, error_message)`` when validation succeeds or
    fails with a user-facing error. Unexpected problems raise
    :class:`SignatureValidationError`.
    """

    if not file or not getattr(file, "filename", None):
        return None, None

    try:
        filename = secure_filename(file.filename)
        if not filename:
            return None, "Niepoprawna nazwa pliku"

        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS or file.mimetype not in ALLOWED_MIME_TYPES:
            return None, "Nieobsługiwany format pliku podpisu. Dozwolone są PNG i JPG."

        file.stream.seek(0, os.SEEK_END)
        if file.stream.tell() > SIGNATURE_MAX_SIZE:
            return None, "Plik podpisu jest zbyt duży."
        file.stream.seek(0)
    except Exception as exc:
        logger.exception("Failed to validate signature")
        raise SignatureValidationError(str(exc)) from exc

    return filename, None

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


def process_signature(file):
    """Process an uploaded signature image and save it to ``static/`` as PNG.

    ``file`` should be a file-like object positioned at the start. A random
    filename is generated and returned. When ``REMOVE_SIGNATURE_BG`` is enabled,
    white background is removed using ``rembg`` when available.
    """

    filename = f"{uuid.uuid4().hex}.png"
    path = os.path.join("static", filename)
    try:
        file.seek(0)
        img = Image.open(file)
        if REMOVE_SIGNATURE_BG:
            if rembg_remove:
                img = rembg_remove(img)
            img = img.convert("RGBA")
            datas = img.getdata()
            new_data = []
            for item in datas:
                if item[0] > 250 and item[1] > 250 and item[2] > 250:
                    new_data.append((255, 255, 255, 0))
                else:
                    new_data.append(item)
            img.putdata(new_data)
        img.save(path, format="PNG")
    except Exception:
        logger.exception("Failed to process signature image")
        raise
    return filename
