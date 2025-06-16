from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    abort,
    current_app,
)
from flask_login import current_user
from utils.auth import role_required
from model import db, Prowadzacy, Zajecia, Uczestnik, Uzytkownik, Setting
from utils import (
    email_do_koordynatora,
    send_plain_email,
    send_attendance_list,
    validate_signature,
    SignatureValidationError,
    load_db_settings,
    process_signature,
)
from doc_generator import generuj_raport_miesieczny, generuj_liste_obecnosci
from io import BytesIO
from werkzeug.security import generate_password_hash
import os
from datetime import datetime
import smtplib
import logging
import json
from . import routes_bp

logger = logging.getLogger(__name__)


@routes_bp.route("/admin")
@role_required("admin")
def admin_dashboard():

    prowadzacy = Prowadzacy.query.all()
    new_users = Uzytkownik.query.filter_by(role="prowadzacy", approved=False).all()

    for p in prowadzacy:
        p.uczestnicy = sorted(p.uczestnicy, key=lambda x: x.imie_nazwisko.lower())

    p_id = request.args.get("p_id", type=int)
    page = request.args.get("page", 1, type=int)
    edit_mode = request.args.get("edit") == "1"
    query = Zajecia.query.order_by(Zajecia.data.desc())
    if p_id:
        query = query.filter_by(prowadzacy_id=p_id)
    pagination = query.paginate(page=page, per_page=10, error_out=False)
    zajecia = pagination.items
    ostatnie = {}
    for p in prowadzacy:
        ostatnie_zajecia = (
            Zajecia.query.filter_by(prowadzacy_id=p.id)
            .order_by(Zajecia.data.desc())
            .first()
        )
        if ostatnie_zajecia:
            ostatnie[p.id] = ostatnie_zajecia.data
    return render_template(
        "admin.html",
        prowadzacy=prowadzacy,
        zajecia=zajecia,
        pagination=pagination,
        ostatnie=ostatnie,
        new_users=new_users,
        selected_p_id=p_id,
        edit_mode=edit_mode,
    )


@routes_bp.route("/admin/settings", methods=["GET", "POST"])
@role_required("admin")
def admin_settings():

    keys = [
        "smtp_host",
        "smtp_port",
        "email_recipient",
        "max_signature_size",
        "remove_signature_bg",
        "email_sender_name",
        "email_use_trainer_name",
        "email_login",
        "email_password",
        "email_footer",
        "email_list_subject",
        "email_list_body",
        "email_report_subject",
        "email_report_body",
        "registration_email_subject",
        "registration_email_body",
        "reg_email_subject",
        "reg_email_body",
        "reset_email_subject",
        "reset_email_body",
        "table_admin_new_users_widths",
        "table_admin_trainers_widths",
        "table_admin_sessions_widths",
        "table_admin_stats_widths",
        "table_panel_history_widths",
        "table_panel_profile_data_widths",
        "table_panel_participants_widths",
        "table_panel_monthly_reports_widths",
    ]

    if request.method == "POST":
        for key in keys:
            if key in ("remove_signature_bg", "email_use_trainer_name"):
                val = "1" if request.form.get(key) else "0"
            else:
                val = request.form.get(key)
            if val is None:
                continue
            setting = db.session.get(Setting, key)
            if setting:
                setting.value = val
            else:
                db.session.add(Setting(key=key, value=val))
            os.environ[key.upper()] = val

        widths: dict[str, dict[str, float]] = {}
        for form_key, form_val in request.form.items():
            if not form_key.startswith("width_"):
                continue
            rest = form_key[len("width_") :]
            table, column = rest.rsplit("_", 1)
            try:
                num = float(form_val)
            except (TypeError, ValueError):
                continue
            widths.setdefault(table, {})[column] = num

        invalid = []
        for table, cols in widths.items():
            total = sum(cols.values())
            if abs(total - 100.0) > 0.1:
                invalid.append(table)

        if invalid:
            for table in invalid:
                flash(
                    f"Suma szerokości w tabeli {table.replace('_', ' ')} musi wynosić 100%",
                    "danger",
                )

            values = {}
            for key in keys:
                setting = db.session.get(Setting, key)
                values[key] = os.getenv(key.upper(), setting.value if setting else "")
                if key in ("remove_signature_bg", "email_use_trainer_name"):
                    if request.form.get(key) is not None:
                        values[key] = "1"
                elif key in request.form:
                    values[key] = request.form.get(key)

            admin_user = Uzytkownik.query.filter_by(role="admin").first()
            admin_login = request.form.get(
                "admin_login", admin_user.login if admin_user else ""
            )
            return render_template(
                "settings.html", values=values, widths=widths, admin_login=admin_login
            )

        for key in keys:
            if key in ("remove_signature_bg", "email_use_trainer_name"):
                val = "1" if request.form.get(key) else "0"
            else:
                val = request.form.get(key)
            if val is None:
                continue
            setting = db.session.get(Setting, key)
            if setting:
                setting.value = val
            else:
                db.session.add(Setting(key=key, value=val))
            os.environ[key.upper()] = val

        for table, cols in widths.items():
            parts = [f"{col}={num}" for col, num in cols.items()]
            val = ",".join(parts)
            key = f"table_{table}_widths"
            setting = db.session.get(Setting, key)
            if setting:
                setting.value = val
            else:
                db.session.add(Setting(key=key, value=val))
            os.environ[key.upper()] = val

        admin_login = request.form.get("admin_login")
        admin_password = request.form.get("admin_password")
        admin_user = Uzytkownik.query.filter_by(role="admin").first()
        if admin_user:
            if admin_login and admin_login != admin_user.login:
                admin_user.login = admin_login
            if admin_password:
                admin_user.haslo_hash = generate_password_hash(admin_password)
        db.session.commit()
        load_db_settings(current_app)
        flash("Ustawienia zostały zapisane", "success")
        return redirect(url_for("routes.admin_settings"))

    values = {}
    for key in keys:
        setting = db.session.get(Setting, key)
        values[key] = os.getenv(key.upper(), setting.value if setting else "")

    widths: dict[str, dict[str, float]] = {}
    for key, val in values.items():
        if not key.startswith("table_") or not key.endswith("_widths"):
            continue
        table = key[len("table_") : -len("_widths")]
        cols: dict[str, float] = {}
        for item in (val or "").split(","):
            if not item:
                continue
            if "=" in item:
                col, num_str = item.split("=", 1)
                try:
                    cols[col] = float(num_str)
                except ValueError:
                    continue
        if cols:
            widths[table] = cols

    admin_user = Uzytkownik.query.filter_by(role="admin").first()
    admin_login = admin_user.login if admin_user else ""
    return render_template(
        "settings.html", values=values, widths=widths, admin_login=admin_login
    )


@routes_bp.route("/usun_zajecie/<int:id>", methods=["POST"])
@role_required("admin")
def usun_zajecie(id):

    zaj = db.session.get(Zajecia, id)
    if not zaj:
        abort(404)

    db.session.delete(zaj)
    db.session.commit()
    flash("Zajęcia zostały usunięte", "info")
    return redirect(url_for("routes.admin_dashboard"))


@routes_bp.route("/raport/<int:prowadzacy_id>", methods=["GET"])
@role_required("admin")
def raport(prowadzacy_id):

    prow = db.session.get(Prowadzacy, prowadzacy_id)
    if not prow:
        abort(404)

    ostatnie = (
        Zajecia.query.filter_by(prowadzacy_id=prowadzacy_id)
        .order_by(Zajecia.data.desc())
        .first()
    )
    if not ostatnie:
        abort(404)

    try:
        miesiac = int(request.args.get("miesiac", ostatnie.data.month))
        rok = int(request.args.get("rok", ostatnie.data.year))
    except (TypeError, ValueError):
        abort(400)
    if not 1 <= miesiac <= 12 or rok < 2000:
        abort(400)
    wyslij = request.args.get("wyslij") == "1"

    wszystkie = Zajecia.query.filter_by(prowadzacy_id=prowadzacy_id).all()
    doc = generuj_raport_miesieczny(
        prow, wszystkie, "rejestr.docx", "static", miesiac, rok
    )

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)

    if wyslij:
        try:
            email_do_koordynatora(buf, f"{miesiac}_{rok}", typ="raport", trainer=prow)
            flash("Raport został wysłany e-mailem", "success")
        except smtplib.SMTPException:
            logger.exception("Failed to send report email")
            flash("Nie udało się wysłać e-maila", "danger")
        return redirect(url_for("routes.admin_dashboard"))

    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=f"raport_{miesiac}_{rok}.docx",
    )


@routes_bp.route("/dodaj", methods=["POST"])
@role_required("admin")
def dodaj_prowadzacego():

    id_edit = request.form.get("edit_id")
    imie = request.form.get("nowy_imie")
    nazwisko = request.form.get("nowy_nazwisko")
    numer_umowy = request.form.get("nowy_umowa")
    nazwa_zajec = request.form.get("nazwa_zajec")
    podpis = request.files.get("nowy_podpis")

    if not imie or not nazwisko:
        flash("Wszystkie pola są wymagane", "danger")
        return redirect(url_for("routes.admin_dashboard"))

    if id_edit:
        prow = db.session.get(Prowadzacy, id_edit)
        if not prow:
            flash("Nie znaleziono prowadącego", "danger")
            return redirect(url_for("routes.admin_dashboard"))
        prow.imie = imie
        prow.nazwisko = nazwisko
        prow.numer_umowy = numer_umowy
        prow.nazwa_zajec = nazwa_zajec
    else:
        prow = Prowadzacy(
            imie=imie,
            nazwisko=nazwisko,
            numer_umowy=numer_umowy,
            nazwa_zajec=nazwa_zajec,
        )
        db.session.add(prow)
        db.session.flush()

    sanitized = None
    if podpis and podpis.filename:
        try:
            sanitized, error = validate_signature(podpis)
        except SignatureValidationError:
            flash("Nie udało się przetworzyć obrazu podpisu", "danger")
            return redirect(url_for("routes.admin_dashboard"))
        if error:
            flash(error, "danger")
            return redirect(url_for("routes.admin_dashboard"))

    if podpis and sanitized:
        try:
            filename = process_signature(podpis.stream)
        except Exception:
            flash("Nie udało się przetworzyć obrazu podpisu", "danger")
            return redirect(url_for("routes.admin_dashboard"))
        prow.podpis_filename = filename

    db.session.commit()
    flash("Prowadzący zapisany", "success")
    return redirect(url_for("routes.admin_trainer", id=prow.id))


@routes_bp.route("/usun/<int:id>", methods=["POST"])
@role_required("admin")
def usun_prowadzacego(id):

    prow = db.session.get(Prowadzacy, id)
    if not prow:
        abort(404)

    Uczestnik.query.filter_by(prowadzacy_id=prow.id).delete()
    db.session.delete(prow)
    db.session.commit()

    flash("Prowadzący usunięty", "info")
    return redirect(url_for("routes.admin_dashboard"))


@routes_bp.route("/admin/trainer/<int:id>")
@role_required("admin")
def admin_trainer(id):
    prow = db.session.get(Prowadzacy, id)
    if not prow:
        abort(404)

    uczestnicy = sorted(prow.uczestnicy, key=lambda x: x.imie_nazwisko.lower())
    zajecia = Zajecia.query.filter_by(prowadzacy_id=prow.id).all()
    total_sessions = len(zajecia)
    stats = {}
    for u in uczestnicy:
        present = sum(1 for z in u.zajecia if z.prowadzacy_id == prow.id)
        percent = (present / total_sessions * 100) if total_sessions else 0
        stats[u.id] = {"present": present, "percent": percent}
    edit_mode = request.args.get("edit") == "1"

    return render_template(
        "admin_trainer.html",
        prowadzacy=prow,
        uczestnicy=uczestnicy,
        stats=stats,
        total_sessions=total_sessions,
        edit_mode=edit_mode,
    )


@routes_bp.route("/admin/trainer/<int:id>/add_participant", methods=["POST"])
@role_required("admin")
def admin_add_participant(id):
    prow = db.session.get(Prowadzacy, id)
    if not prow:
        abort(404)

    name = request.form.get("new_participant", "").strip()
    if name:
        prow.uczestnicy.append(Uczestnik(imie_nazwisko=name))
        db.session.commit()
        flash("Uczestnik dodany", "success")
    else:
        flash("Brak nazwy uczestnika", "danger")
    edit = request.args.get("edit") == "1"
    return redirect(url_for("routes.admin_trainer", id=id, edit="1" if edit else None))


@routes_bp.route("/admin/participant/<int:id>/rename", methods=["POST"])
@role_required("admin")
def admin_rename_participant(id):
    uczestnik = db.session.get(Uczestnik, id)
    if not uczestnik:
        abort(404)

    new_name = request.form.get("new_name", "").strip()
    if new_name:
        uczestnik.imie_nazwisko = new_name
        db.session.commit()
        flash("Uczestnik zaktualizowany", "success")
    else:
        flash("Brak nazwy uczestnika", "danger")
    edit = request.args.get("edit") == "1"
    return redirect(url_for("routes.admin_trainer", id=uczestnik.prowadzacy_id, edit="1" if edit else None))


@routes_bp.route("/admin/participant/<int:id>/delete", methods=["POST"])
@role_required("admin")
def admin_delete_participant(id):
    uczestnik = db.session.get(Uczestnik, id)
    if not uczestnik:
        abort(404)
    pid = uczestnik.prowadzacy_id
    db.session.delete(uczestnik)
    db.session.commit()
    flash("Uczestnik usunięty", "info")
    edit = request.args.get("edit") == "1"
    return redirect(url_for("routes.admin_trainer", id=pid, edit="1" if edit else None))


@routes_bp.route("/approve_user/<int:id>", methods=["POST", "GET"])
@role_required("admin")
def approve_user(id):

    user = db.session.get(Uzytkownik, id)
    if not user:
        flash("Nie znaleziono użytkownika", "danger")
        return redirect(url_for("routes.admin_dashboard"))

    user.approved = True
    db.session.commit()

    try:
        send_plain_email(
            user.login,
            "REG_EMAIL_SUBJECT",
            "REG_EMAIL_BODY",
            "Aktywacja konta w ShareOKO",
            "Twoje konto zostało zatwierdzone i jest już aktywne.",
        )
    except smtplib.SMTPException:
        logger.exception("Failed to send activation email")
        flash("Nie udało się wysłać e-maila do użytkownika", "danger")

    flash("Użytkownik zatwierdzony", "success")
    return redirect(url_for("routes.admin_dashboard"))


@routes_bp.route("/edytuj_zajecie/<int:id>", methods=["GET", "POST"])
@role_required("admin")
def edytuj_zajecie(id):

    zaj = db.session.get(Zajecia, id)
    if not zaj:
        abort(404)

    prow = zaj.prowadzacy
    uczestnicy = sorted(prow.uczestnicy, key=lambda x: x.imie_nazwisko.lower())

    if request.method == "POST":
        data_str = request.form.get("data")
        czas = request.form.get("czas")
        obecni_ids = request.form.getlist("obecny")

        if not data_str or not czas:
            flash("Brakuje wymaganych danych", "danger")
            return redirect(url_for("routes.edytuj_zajecie", id=id))

        zaj.data = datetime.strptime(data_str, "%Y-%m-%d")
        try:
            zaj.czas_trwania = float(czas.replace(",", "."))
        except ValueError:
            zaj.czas_trwania = 0
        zaj.obecni = Uczestnik.query.filter(Uczestnik.id.in_(obecni_ids)).all()
        db.session.commit()
        flash("Zajęcia zaktualizowane", "success")
        return redirect(url_for("routes.admin_dashboard"))

    obecni_ids = [u.id for u in zaj.obecni]
    czas = str(zaj.czas_trwania).replace(".", ",")
    return render_template(
        "edit_zajecie.html",
        zajecie=zaj,
        uczestnicy=uczestnicy,
        obecni_ids=obecni_ids,
        czas=czas,
        back_url=url_for("routes.admin_dashboard"),
    )


@routes_bp.route("/pobierz_zajecie_admin/<int:id>")
@role_required("admin")
def pobierz_zajecie_admin(id):

    zaj = db.session.get(Zajecia, id)
    if not zaj:
        abort(404)

    prow = zaj.prowadzacy
    obecni = [u.imie_nazwisko for u in zaj.obecni]
    doc = generuj_liste_obecnosci(
        zaj.data.strftime("%Y-%m-%d"),
        str(zaj.czas_trwania).replace(".", ","),
        obecni,
        f"{prow.imie} {prow.nazwisko}",
        os.path.join("static", prow.podpis_filename),
    )

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    data_str = zaj.data.strftime("%Y-%m-%d")
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=f"lista_{data_str}.docx",
    )


@routes_bp.route("/wyslij_zajecie_admin/<int:id>")
@role_required("admin")
def wyslij_zajecie_admin(id):
    """Send the attendance list for the session via e-mail."""

    zaj = db.session.get(Zajecia, id)
    if not zaj:
        abort(404)

    if send_attendance_list(zaj):
        flash("Lista została wysłana e-mailem", "success")
    else:
        flash("Nie udało się wysłać e-maila", "danger")

    return redirect(url_for("routes.admin_dashboard"))


@routes_bp.route("/admin/statystyki/<int:trainer_id>")
@role_required("admin")
def admin_statystyki(trainer_id):
    """Show attendance statistics for the selected trainer."""

    prow = db.session.get(Prowadzacy, trainer_id)
    if not prow:
        abort(404)

    total = Zajecia.query.filter_by(prowadzacy_id=trainer_id).count()
    uczestnicy = sorted(prow.uczestnicy, key=lambda x: x.imie_nazwisko.lower())
    edit_mode = request.args.get("edit") == "1"

    stats = []
    for u in uczestnicy:
        present = sum(1 for z in u.zajecia if z.prowadzacy_id == trainer_id)
        percent = (present / total * 100) if total else 0
        stats.append({"uczestnik": u, "present": present, "percent": percent})

    return render_template(
        "admin_statystyki.html",
        prowadzacy=prow,
        stats=stats,
        total_sessions=total,
        edit_mode=edit_mode,
    )


@routes_bp.route("/admin/trainer/<int:id>/update_inline", methods=["POST"])
@role_required("admin")
def admin_update_trainer_inline(id):
    """Inline update of trainer fields from the dashboard."""
    prow = db.session.get(Prowadzacy, id)
    if not prow:
        abort(404)
    prow.imie = request.form.get("imie", prow.imie)
    prow.nazwisko = request.form.get("nazwisko", prow.nazwisko)
    prow.numer_umowy = request.form.get("numer_umowy", prow.numer_umowy)
    prow.nazwa_zajec = request.form.get("nazwa_zajec", prow.nazwa_zajec)
    db.session.commit()
    flash("Prowadzący zaktualizowany", "success")
    return redirect(url_for("routes.admin_dashboard", edit=1))


@routes_bp.route("/admin/session/<int:id>/update_inline", methods=["POST"])
@role_required("admin")
def admin_update_session_inline(id):
    """Inline update of session fields from the dashboard."""
    zaj = db.session.get(Zajecia, id)
    if not zaj:
        abort(404)
    data_str = request.form.get("data")
    czas = request.form.get("czas")
    if data_str:
        try:
            zaj.data = datetime.strptime(data_str, "%Y-%m-%d")
        except ValueError:
            pass
    if czas:
        try:
            zaj.czas_trwania = float(czas.replace(",", "."))
        except ValueError:
            pass
    db.session.commit()
    flash("Zajęcia zaktualizowane", "success")
    return redirect(url_for("routes.admin_dashboard", edit=1))
