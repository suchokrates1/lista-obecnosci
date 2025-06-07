from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from model import db, Uzytkownik, Prowadzacy, Uczestnik
from utils import send_plain_email
import os
from . import routes_bp

@routes_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_val = request.form.get("login")
        haslo = request.form.get("hasło")
        user = Uzytkownik.query.filter_by(login=login_val).first()
        if user and check_password_hash(user.haslo_hash, haslo):
            login_user(user)
            return redirect(url_for("routes.admin_dashboard"))
        flash("Nieprawidłowe dane logowania", "danger")
    return render_template("login.html")

@routes_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("routes.index"))


@routes_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        imie = request.form.get("imie")
        nazwisko = request.form.get("nazwisko")
        numer_umowy = request.form.get("numer_umowy")
        lista_uczestnikow = request.form.get("lista_uczestnikow")
        login_val = request.form.get("login")
        haslo = request.form.get("haslo")
        podpis = request.files.get("podpis")

        if not all([imie, nazwisko, numer_umowy, lista_uczestnikow, login_val, haslo]):
            flash("Wszystkie pola oprócz podpisu są wymagane", "danger")
            return redirect(url_for("routes.register"))

        if Uzytkownik.query.filter_by(login=login_val).first():
            flash("Login jest już zajęty", "danger")
            return redirect(url_for("routes.register"))

        filename = None
        if podpis and podpis.filename:
            ext = podpis.filename.rsplit(".", 1)[-1]
            filename = f"{nazwisko}_{login_val}.{ext}"
            path = os.path.join("static", filename)
            podpis.save(path)

        prow = Prowadzacy(imie=imie, nazwisko=nazwisko, numer_umowy=numer_umowy, podpis_filename=filename)
        db.session.add(prow)
        db.session.flush()

        for linia in lista_uczestnikow.splitlines():
            nazwa = linia.strip()
            if nazwa:
                db.session.add(Uczestnik(imie_nazwisko=nazwa, prowadzacy_id=prow.id))

        user = Uzytkownik(login=login_val,
                          haslo_hash=generate_password_hash(haslo),
                          role="prowadzacy",
                          approved=False,
                          prowadzacy_id=prow.id)
        db.session.add(user)
        db.session.commit()

        send_plain_email(
            "kontakt@vestmedia.pl",
            "Nowa rejestracja prowadzącego",
            f"Zarejestrował się {imie} {nazwisko} (login: {login_val})."
        )

        flash("Rejestracja zakończona. Poczekaj na zatwierdzenie konta.", "success")
        return redirect(url_for("routes.login"))

    return render_template("register.html")
