from model import db, Zajecia, Uczestnik
from doc_generator import generuj_liste_obecnosci
from io import BytesIO
from datetime import datetime
import os
import smtplib
import logging
from email.message import EmailMessage

logger = logging.getLogger(__name__)

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
        msg["Subject"] = f"Raport miesięczny – {data}"
        msg.set_content("W załączniku raport miesięczny do umowy.")
        filename = f"raport_{data}.docx"
    else:
        msg["Subject"] = f"Lista obecności – {data}"
        msg.set_content("W załączniku lista obecności z zajęć.")
        filename = f"lista_{data}.docx"

    msg["From"] = f"Vest Media <{os.getenv('EMAIL_LOGIN')}>"
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
    login = os.getenv("EMAIL_LOGIN")
    password = os.getenv("EMAIL_PASSWORD")

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


def send_plain_email(to_addr: str, subject: str, body: str) -> None:
    """Send a simple text e-mail."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg.set_content(body)
    msg["From"] = f"Vest Media <{os.getenv('EMAIL_LOGIN')}>"
    msg["To"] = to_addr

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT"))
    login = os.getenv("EMAIL_LOGIN")
    password = os.getenv("EMAIL_PASSWORD")

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
