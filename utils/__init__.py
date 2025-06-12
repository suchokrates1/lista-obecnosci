from model import db, Zajecia, Uczestnik, PasswordResetToken, Uzytkownik, Prowadzacy
from sqlalchemy.exc import OperationalError
from doc_generator import generuj_liste_obecnosci
from io import BytesIO
from datetime import datetime
from collections import defaultdict
import os
import smtplib
import logging
import threading
import queue
import atexit
from email.message import EmailMessage
import re
import json
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
import uuid
from PIL import Image
try:
    from rembg import remove as rembg_remove  # type: ignore
except Exception:  # rembg is optional
    rembg_remove = None

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Polish month names indexed by number
MONTH_NAMES_PL = {
    1: "styczeń",
    2: "luty",
    3: "marzec",
    4: "kwiecień",
    5: "maj",
    6: "czerwiec",
    7: "lipiec",
    8: "sierpień",
    9: "wrzesień",
    10: "październik",
    11: "listopad",
    12: "grudzień",
}


def month_name(value):
    """Return the Polish name of the month ``value``."""
    try:
        return MONTH_NAMES_PL[int(value)]
    except (KeyError, ValueError, TypeError):
        return ""

# simple asynchronous e-mail dispatch
_email_queue: "queue.Queue[EmailMessage | None]" = queue.Queue()
_worker: threading.Thread | None = None


def _email_worker() -> None:
    """Background thread sending messages from ``_email_queue``."""
    while True:
        msg = _email_queue.get()
        if msg is None:
            break
        try:
            _send_message(msg)
        finally:
            _email_queue.task_done()


def _ensure_worker() -> None:
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_email_worker, daemon=True)
        _worker.start()


def _dispatch(msg: EmailMessage, use_queue: bool) -> None:
    if use_queue:
        _ensure_worker()
        _email_queue.put(msg)
    else:
        _send_message(msg)


def shutdown_email_worker() -> None:
    """Stop the background email worker after processing remaining messages."""
    global _worker
    if _worker and _worker.is_alive():
        _email_queue.join()
        _email_queue.put(None)
        _worker.join()
        _worker = None


def get_smtp_settings() -> tuple[str | None, int | None, str | None, str | None]:
    """Return SMTP host, port, login and password from environment."""
    host = os.getenv("SMTP_HOST")
    port_str = os.getenv("SMTP_PORT")
    port = int(port_str) if port_str is not None else None
    login = os.getenv("EMAIL_LOGIN")
    password = os.getenv("EMAIL_PASSWORD")
    return host, port, login, password


def _send_message(msg: EmailMessage) -> None:
    """Send ``msg`` immediately using SMTP settings from environment."""
    host, port, login, password = get_smtp_settings()

    if port == 465:
        with smtplib.SMTP_SSL(host, port) as smtp:
            smtp.login(login, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls()
            smtp.login(login, password)
            smtp.send_message(msg)
    logger.info("Mail sent to %s", msg.get("To"))

# Allowed signature upload formats
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg"}

# Maximum allowed size of uploaded signature files in bytes
SIGNATURE_MAX_SIZE = int(os.getenv("MAX_SIGNATURE_SIZE", 1024 * 1024))
# Whether to clean white background from signatures
REMOVE_SIGNATURE_BG = os.getenv("REMOVE_SIGNATURE_BG", "0").lower() in {"1", "true", "yes"}

# Mapping of column width percentages loaded from the database
TABLE_COLUMN_WIDTHS: dict[str, list[float]] = {}


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

    global SIGNATURE_MAX_SIZE, REMOVE_SIGNATURE_BG, TABLE_COLUMN_WIDTHS
    TABLE_COLUMN_WIDTHS = {}
    for key, value in os.environ.items():
        if not key.startswith("TABLE_") or not key.endswith("_WIDTHS"):
            continue
        table = key[len("TABLE_") : -len("_WIDTHS")].lower().replace("_", "-")
        widths: list[float] = []
        for part in (value or "").split(","):
            if not part:
                continue
            if "=" in part:
                _, num = part.split("=", 1)
            else:
                num = part
            try:
                widths.append(float(num))
            except ValueError:
                continue
        if widths:
            TABLE_COLUMN_WIDTHS[table] = widths

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

def email_do_koordynatora(buf, data, typ="lista", queue: bool = False):
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
    msg["From"] = f"{sender_name} <{login}>"
    msg["To"] = odbiorca

    buf.seek(0)
    msg.add_attachment(
        buf.read(),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename
    )

    try:
        _dispatch(msg, queue)
    except smtplib.SMTPException as e:
        logger.exception("Failed to send email: %s", e)
        raise


def send_attendance_list(zajecie, queue: bool = False) -> bool:
    """Generate and e-mail the attendance list for ``zajecie``.

    Returns ``True`` on success, ``False`` when sending fails."""

    prow = zajecie.prowadzacy
    obecni = [u.imie_nazwisko for u in zajecie.obecni]
    doc = generuj_liste_obecnosci(
        zajecie.data.strftime("%Y-%m-%d"),
        str(zajecie.czas_trwania).replace(".", ","),
        obecni,
        f"{prow.imie} {prow.nazwisko}",
        os.path.join("static", prow.podpis_filename),
    )

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    data_str = zajecie.data.strftime("%Y-%m-%d")

    try:
        email_do_koordynatora(buf, data_str, typ="lista", queue=queue)
    except smtplib.SMTPException:
        logger.exception("Failed to send attendance email")
        return False

    zajecie.wyslano = True
    db.session.commit()
    return True


def send_plain_email(
    to_addr: str,
    subject_key: str,
    body_key: str,
    default_subject: str,
    default_body: str,
    queue: bool = False,
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
    msg["From"] = f"{sender_name} <{login}>"
    msg["To"] = to_addr

    try:
        _dispatch(msg, queue)
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


def purge_expired_tokens() -> None:
    """Delete expired password reset tokens from the database."""
    cutoff = datetime.utcnow()
    PasswordResetToken.query.filter(
        PasswordResetToken.expires_at < cutoff
    ).delete()
    db.session.commit()


def parse_registration_form(form, files):
    """Validate registration form data and return a dictionary on success."""
    imie = form.get("imie")
    nazwisko = form.get("nazwisko")
    numer_umowy = form.get("numer_umowy")
    lista_uczestnikow = form.get("lista_uczestnikow")
    login_val = form.get("login")
    haslo = form.get("haslo")
    podpis = files.get("podpis")

    uczestnik_values = [v for v in form.getlist("uczestnik") if v]
    if uczestnik_values:
        lista_vals = uczestnik_values
    else:
        lista_vals = [lista_uczestnikow] if lista_uczestnikow else []

    uczestnicy: list[str] = []
    for val in lista_vals:
        if not val:
            continue
        uczestnicy.extend(l.strip() for l in val.splitlines() if l.strip())

    if not all([imie, nazwisko, numer_umowy, login_val, haslo]) or not uczestnicy:
        return None, "Wszystkie pola oprócz podpisu są wymagane"

    if not is_valid_email(login_val):
        return None, "Login musi być prawidłowym adresem e-mail"

    if Uzytkownik.query.filter_by(login=login_val).first():
        return None, "Login jest już zajęty"

    valid_signature = False
    if podpis and getattr(podpis, "filename", None):
        try:
            _sanitized, error = validate_signature(podpis)
        except SignatureValidationError:
            return None, "Nie udało się przetworzyć obrazu podpisu"
        if error:
            return None, error
        valid_signature = True

    return {
        "imie": imie,
        "nazwisko": nazwisko,
        "numer_umowy": numer_umowy,
        "login": login_val,
        "haslo": haslo,
        "podpis": podpis,
        "valid_signature": valid_signature,
        "uczestnicy": uczestnicy,
    }, None


def create_trainer(data):
    """Create trainer and user records from parsed ``data``."""
    filename = None
    podpis = data.get("podpis")
    if podpis and data.get("valid_signature"):
        try:
            filename = process_signature(podpis.stream)
        except Exception:
            logger.exception("Failed to process signature image")
            return None, "Nie udało się przetworzyć obrazu podpisu"

    prow = Prowadzacy(
        imie=data["imie"],
        nazwisko=data["nazwisko"],
        numer_umowy=data["numer_umowy"],
        podpis_filename=filename,
    )
    db.session.add(prow)
    db.session.flush()

    for nazwa in data.get("uczestnicy", []):
        db.session.add(Uczestnik(imie_nazwisko=nazwa, prowadzacy_id=prow.id))

    user = Uzytkownik(
        login=data["login"],
        haslo_hash=generate_password_hash(data["haslo"]),
        role="prowadzacy",
        approved=False,
        prowadzacy_id=prow.id,
    )
    db.session.add(user)
    db.session.commit()
    return user, None


def get_participant_stats(prow):
    """Return sorted participants, sessions, stats map and total session count."""
    uczestnicy = sorted(prow.uczestnicy, key=lambda x: x.imie_nazwisko.lower())
    zajecia = (
        Zajecia.query.filter_by(prowadzacy_id=prow.id)
        .order_by(Zajecia.data.desc())
        .all()
    )
    total_sessions = len(zajecia)
    stats = {}
    for u in uczestnicy:
        present = sum(1 for z in u.zajecia if z.prowadzacy_id == prow.id)
        percent = (present / total_sessions * 100) if total_sessions else 0
        stats[u.id] = {"uczestnik": u, "present": present, "percent": percent}
    return uczestnicy, zajecia, stats, total_sessions


def get_monthly_summary(zajecia):
    """Return a dictionary summarizing hours for each (year, month)."""
    summary = defaultdict(float)
    for z in zajecia:
        key = (z.data.year, z.data.month)
        summary[key] += z.czas_trwania
    return summary


atexit.register(shutdown_email_worker)
