from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from model import db, Prowadzacy, Uzytkownik, Zajecia, Uczestnik
from doc_generator import generuj_liste_obecnosci, generuj_raport_miesieczny
import os
from io import BytesIO
import smtplib
from email.message import EmailMessage
from datetime import datetime

routes_bp = Blueprint("routes", __name__)

# Logowanie
@routes_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login = request.form.get("login")
        haslo = request.form.get("hasło")

        użytkownik = Uzytkownik.query.filter_by(login=login).first()
        if użytkownik and check_password_hash(użytkownik.haslo_hash, haslo):
            login_user(użytkownik)
            return redirect(url_for("routes.admin_dashboard"))
        flash("Nieprawidłowe dane logowania", "danger")
    return render_template("login.html")

@routes_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("routes.index"))

# Strona główna – lista obecności
@routes_bp.route("/", methods=["GET", "POST"])
def index():
    prowadzacy = Prowadzacy.query.all()
    status = None
    akcja = None
    try:
        selected_id = int(request.form.get("prowadzący"))
    except (TypeError, ValueError):
        selected_id = prowadzacy[0].id if prowadzacy else None

    wybrany = Prowadzacy.query.get(selected_id)
    uczestnicy = sorted(wybrany.uczestnicy, key=lambda x: x.imie_nazwisko.lower()) if wybrany else []

    if request.method == "POST":
        akcja = request.form.get("akcja")

    if akcja == "zmien_prowadzacego":
        return render_template("index.html",
                           prowadzacy=prowadzacy,
                           uczestnicy=uczestnicy,
                           selected=selected_id,
                           status=status,
                           is_admin=current_user.is_authenticated and current_user.login == os.getenv("ADMIN_LOGIN"),
                           is_logged=current_user.is_authenticated)


        data_str = request.form.get("data")
        czas = request.form.get("czas")
        obecni_ids = request.form.getlist("obecny")

        if not wybrany or not data_str or not czas:
            flash("Brakuje wymaganych danych", "danger")
            return redirect(url_for("routes.index"))

        obecni_uczestnicy = Uczestnik.query.filter(Uczestnik.id.in_(obecni_ids)).all()
        docx_obj = generuj_liste_obecnosci(
            data_str,
            czas,
            sorted([ucz.imie_nazwisko for ucz in obecni_uczestnicy], key=str.lower),
            wybrany.nazwisko,
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

        if akcja == "pobierz":
            return send_file(buf,
                             mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                             as_attachment=True,
                             download_name=f"lista_{data_str}.docx")

        if akcja == "wyslij":
            email_do_koordynatora(buf, data_str, typ="lista")
            status = "Lista została wysłana e-mailem."

    return render_template("index.html",
                           prowadzacy=prowadzacy,
                           uczestnicy=uczestnicy,
                           selected=selected_id,
                           status=status,
                           is_admin=current_user.is_authenticated and current_user.login == os.getenv("ADMIN_LOGIN"),
                           is_logged=current_user.is_authenticated)

# Wysyłka e-maila
def email_do_koordynatora(buf, data, typ="lista"):
    odbiorca = os.getenv("EMAIL_RECIPIENT")
    if not odbiorca:
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

    if port == 465:
        with smtplib.SMTP_SSL(host, port) as smtp:
            smtp.login(login, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls()
            smtp.login(login, password)
            smtp.send_message(msg)

# Panel administratora
@routes_bp.route("/admin")
@login_required
def admin_dashboard():
    if current_user.login != os.getenv("ADMIN_LOGIN"):
        return "Brak dostępu", 403

    prowadzacy = Prowadzacy.query.all()
    for p in prowadzacy:
        p.uczestnicy = sorted(p.uczestnicy, key=lambda x: x.imie_nazwisko.lower())

    zajecia = Zajecia.query.order_by(Zajecia.data.desc()).all()
    ostatnie = {}
    for p in prowadzacy:
        ostatnie_zajecia = Zajecia.query.filter_by(prowadzacy_id=p.id).order_by(Zajecia.data.desc()).first()
        if ostatnie_zajecia:
            ostatnie[p.id] = ostatnie_zajecia.data
    return render_template("admin.html", prowadzacy=prowadzacy, zajecia=zajecia, ostatnie=ostatnie)

# Usuwanie pojedynczych zajęć
@routes_bp.route("/usun_zajecie/<int:id>", methods=["POST"])
@login_required
def usun_zajecie(id):
    if current_user.login != os.getenv("ADMIN_LOGIN"):
        return "Brak dostępu", 403

    zaj = Zajecia.query.get(id)
    if not zaj:
        return "Nie znaleziono zajęć", 404

    db.session.delete(zaj)
    db.session.commit()
    flash("Zajęcia zostały usunięte", "info")
    return redirect(url_for("routes.admin_dashboard"))

# Generowanie raportu miesięcznego
@routes_bp.route("/raport/<int:prowadzacy_id>", methods=["GET"])
@login_required
def raport(prowadzacy_id):
    if current_user.login != os.getenv("ADMIN_LOGIN"):
        return "Brak dostępu", 403

    prow = Prowadzacy.query.get(prowadzacy_id)
    if not prow:
        return "Nie znaleziono prowadzącego", 404

    ostatnie = Zajecia.query.filter_by(prowadzacy_id=prowadzacy_id).order_by(Zajecia.data.desc()).first()
    if not ostatnie:
        return "Brak zajęć do raportu", 404

    miesiac = int(request.args.get("miesiac", ostatnie.data.month))
    rok = int(request.args.get("rok", ostatnie.data.year))
    wyslij = request.args.get("wyslij") == "1"

    wszystkie = Zajecia.query.filter_by(prowadzacy_id=prowadzacy_id).all()
    doc = generuj_raport_miesieczny(prow, wszystkie, "rejestr.docx", "static", miesiac, rok)

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)

    if wyslij:
        email_do_koordynatora(buf, f"{miesiac}_{rok}", typ="raport")
        flash("Raport został wysłany e-mailem", "success")
        return redirect(url_for("routes.admin_dashboard"))

    return send_file(buf,
                     mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                     as_attachment=True,
                     download_name=f"raport_{miesiac}_{rok}.docx")

# Dodawanie lub edycja prowadzącego
@routes_bp.route("/dodaj", methods=["POST"])
@login_required
def dodaj_prowadzacego():
    if current_user.login != os.getenv("ADMIN_LOGIN"):
        return "Brak dostępu", 403

    id_edit = request.form.get("edit_id")
    trener = request.form.get("nowy_trener")
    numer_umowy = request.form.get("nowy_umowa")
    uczestnicy = request.form.get("nowi_uczestnicy")
    podpis = request.files.get("nowy_podpis")

    if not trener or not uczestnicy:
        flash("Wszystkie pola są wymagane", "danger")
        return redirect(url_for("routes.admin_dashboard"))

    if id_edit:
        prow = Prowadzacy.query.get(id_edit)
        if not prow:
            flash("Nie znaleziono prowadącego", "danger")
            return redirect(url_for("routes.admin_dashboard"))
        prow.nazwisko = trener
        prow.numer_umowy = numer_umowy
        prow.uczestnicy.clear()
    else:
        prow = Prowadzacy(nazwisko=trener, numer_umowy=numer_umowy)
        db.session.add(prow)
        db.session.flush()

    if podpis:
        filename = f"{trener}.{podpis.filename.split('.')[-1]}"
        path = os.path.join("static", filename)
        podpis.save(path)
        prow.podpis_filename = filename

    for nazwisko in uczestnicy.strip().splitlines():
        uczestnik = Uczestnik(prowadzacy_id=prow.id, imie_nazwisko=nazwisko)
        db.session.add(uczestnik)

    db.session.commit()
    flash("Prowadzący zapisany", "success")
    return redirect(url_for("routes.admin_dashboard"))

# Usuwanie prowadzącego i jego uczestników
@routes_bp.route("/usun/<id>", methods=["POST"])
@login_required
def usun_prowadzacego(id):
    if current_user.login != os.getenv("ADMIN_LOGIN"):
        return "Brak dostępu", 403

    prow = Prowadzacy.query.get(id)
    if not prow:
        return "Nie znaleziono", 404

    Uczestnik.query.filter_by(prowadzacy_id=prow.id).delete()
    db.session.delete(prow)
    db.session.commit()

    flash("Prowadzący usunięty", "info")
    return redirect(url_for("routes.admin_dashboard"))
