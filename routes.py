from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from model import db, Prowadzacy, Uzytkownik, Zajecia, Uczestnik
from utils import przetworz_liste_obecnosci, email_do_koordynatora
import os

routes_bp = Blueprint("routes", __name__)

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

        elif akcja in ["pobierz", "wyslij"]:
            result = przetworz_liste_obecnosci(request.form, wybrany)
            if isinstance(result, tuple) and result[0] == "error":
                flash(result[1], "danger")
                return redirect(url_for("routes.index"))
            elif isinstance(result, tuple):
                status, buf, data_str = result
                if akcja == "pobierz":
                    return send_file(buf,
                                     mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                     as_attachment=True,
                                     download_name=f"lista_{data_str}.docx")
                elif akcja == "wyslij":
                    email_do_koordynatora(buf, data_str, typ="lista")

    return render_template("index.html",
                           prowadzacy=prowadzacy,
                           uczestnicy=uczestnicy,
                           selected=selected_id,
                           status=status,
                           is_admin=current_user.is_authenticated and current_user.login == os.getenv("ADMIN_LOGIN"),
                           is_logged=current_user.is_authenticated)

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
            flash("Nie znaleziono prowadzącego", "danger")
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
    return redirect(url_for("routes.index", selected_id=prow.id))
