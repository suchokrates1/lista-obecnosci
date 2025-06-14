from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from model import db, Uzytkownik, PasswordResetToken
from utils import (
    send_plain_email,
    is_valid_email,
    parse_registration_form,
    create_trainer,
    purge_expired_tokens,
)
import os
import uuid
import smtplib
from datetime import datetime, timedelta
import logging
from . import routes_bp

logger = logging.getLogger(__name__)

@routes_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_val = request.form.get("login")
        haslo = request.form.get("hasło")
        remember = bool(request.form.get("remember"))

        if not is_valid_email(login_val):
            flash("Login musi być prawidłowym adresem e-mail", "danger")
            return redirect(url_for("routes.login"))

        user = Uzytkownik.query.filter_by(login=login_val).first()
        if user and check_password_hash(user.haslo_hash, haslo):
            if user.role == "prowadzacy" and not user.approved:
                flash("Konto prowadzącego nie zostało jeszcze zatwierdzone", "danger")
                return redirect(url_for("routes.login"))

            login_user(user, remember=remember)

            if user.role == "admin":
                return redirect(url_for("routes.admin_dashboard"))
            else:
                return redirect(url_for("routes.index"))

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
        data, error = parse_registration_form(request.form, request.files)
        if error:
            flash(error, "danger")
            return redirect(url_for("routes.register"))

        user, error = create_trainer(data)
        if error:
            flash(error, "danger")
            return redirect(url_for("routes.register"))

        imie = data["imie"]
        nazwisko = data["nazwisko"]
        login_val = data["login"]

        try:
            approve_link = url_for(
                "routes.approve_user", id=user.id, _external=True
            )
            send_plain_email(
                os.getenv('EMAIL_RECIPIENT', 'kontakt@vestmedia.pl'),
                'REGISTRATION_EMAIL_SUBJECT',
                'REGISTRATION_EMAIL_BODY',
                'Nowa rejestracja prowadzącego',
                'Zarejestrował się {name} (login: {login}).\nPotwierdź konto tutaj: {link}',
                name=f"{imie} {nazwisko}",
                login=login_val,
                link=approve_link
            )
        except smtplib.SMTPException:
            logger.exception('Failed to send registration email')
            flash('Nie udało się wysłać e-maila', 'danger')

        flash("Rejestracja zakończona. Poczekaj na zatwierdzenie konta.", "success")
        return redirect(url_for("routes.login"))

    return render_template("register.html")


@routes_bp.route("/reset-request", methods=["GET", "POST"])
def reset_request():
    purge_expired_tokens()
    if request.method == "POST":
        email = request.form.get("login")
        if email and is_valid_email(email):
            user = Uzytkownik.query.filter_by(login=email).first()
            if user:
                token = uuid.uuid4().hex
                expires = datetime.utcnow() + timedelta(hours=1)
                prt = PasswordResetToken(user_id=user.id, token=token, expires_at=expires)
                db.session.add(prt)
                db.session.commit()
                try:
                    link = url_for("routes.reset_with_token", token=token, _external=True)
                    send_plain_email(
                        user.login,
                        'RESET_EMAIL_SUBJECT',
                        'RESET_EMAIL_BODY',
                        'Reset hasła w ShareOKO',
                        'Aby ustawić nowe hasło, otwórz link: {link}',
                        link=link
                    )
                    logger.info("Sent password reset email to %s", user.login)
                except smtplib.SMTPException:
                    logger.exception("Failed to send password reset email")
        flash("Jeśli konto istnieje, wysłaliśmy instrukcje resetu hasła", "info")
        return redirect(url_for("routes.login"))
    return render_template("reset_request.html")


@routes_bp.route("/reset/<token>", methods=["GET", "POST"])
def reset_with_token(token):
    purge_expired_tokens()
    prt = PasswordResetToken.query.filter_by(token=token).first()
    if not prt or prt.expires_at < datetime.utcnow():
        if prt:
            db.session.delete(prt)
            db.session.commit()
        logger.info("Invalid or expired reset token used: %s", token)
        flash("Link do resetu jest nieprawidłowy lub wygasł", "danger")
        return redirect(url_for("routes.login"))

    if request.method == "POST":
        new_password = request.form.get("password")
        if not new_password:
            flash("Hasło jest wymagane", "danger")
            return render_template("reset_form.html")
        prt.user.haslo_hash = generate_password_hash(new_password)
        db.session.delete(prt)
        db.session.commit()
        logger.info("Password reset for user %s", prt.user.login)
        flash("Hasło zostało zmienione", "success")
        return redirect(url_for("routes.login"))

    return render_template("reset_form.html")
