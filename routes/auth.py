from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash
from model import Uzytkownik
from . import routes_bp

@routes_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_val = request.form.get("login")
        haslo = request.form.get("hasło")
        user = Uzytkownik.query.filter_by(login=login_val).first()
        if user and check_password_hash(user.haslo_hash, haslo):
            if user.role == "prowadzacy" and not user.approved:
                flash("Konto oczekuje na zatwierdzenie", "warning")
                return render_template("login.html")
            login_user(user)
            if user.role == "admin":
                return redirect(url_for("routes.admin_dashboard"))
            return redirect(url_for("routes.index"))
        flash("Nieprawidłowe dane logowania", "danger")
    return render_template("login.html")

@routes_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("routes.index"))
