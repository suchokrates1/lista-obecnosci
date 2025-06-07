from flask import render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user
from datetime import datetime
from io import BytesIO
import os

from model import db, Prowadzacy, Zajecia, Uczestnik
from doc_generator import generuj_liste_obecnosci
from . import routes_bp


def _check_role():
    if not current_user.is_authenticated or current_user.rola != "prowadzacy":
        return False
    return True


@routes_bp.route("/panel")
@login_required
def panel():
    if not _check_role():
        return "Brak dostępu", 403

    prow = Prowadzacy.query.get(current_user.prowadzacy_id)
    if not prow:
        return "Nie znaleziono prowadzącego", 404

    uczestnicy = sorted(prow.uczestnicy, key=lambda u: u.imie_nazwisko.lower())
    zajecia = Zajecia.query.filter_by(prowadzacy_id=prow.id).order_by(Zajecia.data.desc()).all()

    return render_template(
        "panel.html",
        prowadzacy=prow,
        uczestnicy=uczestnicy,
        zajecia=zajecia,
    )


@routes_bp.route("/panel/edytuj_dane", methods=["POST"])
@login_required
def edytuj_dane():
    if not _check_role():
        return "Brak dostępu", 403

    prow = Prowadzacy.query.get(current_user.prowadzacy_id)
    if not prow:
        return "Nie znaleziono", 404

    prow.nazwisko = request.form.get("nazwisko")
    prow.numer_umowy = request.form.get("numer_umowy")
    db.session.commit()
    flash("Dane zostały zaktualizowane", "success")
    return redirect(url_for("routes.panel"))


@routes_bp.route("/panel/edytuj_uczestnikow", methods=["POST"])
@login_required
def edytuj_uczestnikow():
    if not _check_role():
        return "Brak dostępu", 403

    prow = Prowadzacy.query.get(current_user.prowadzacy_id)
    if not prow:
        return "Nie znaleziono", 404

    prow.uczestnicy.clear()
    lista = request.form.get("uczestnicy", "").strip().splitlines()
    for nazwisko in lista:
        if nazwisko.strip():
            prow.uczestnicy.append(Uczestnik(imie_nazwisko=nazwisko.strip()))
    db.session.commit()
    flash("Zaktualizowano listę uczestników", "success")
    return redirect(url_for("routes.panel"))


@routes_bp.route("/panel/usun_zajecie/<int:zaj_id>", methods=["POST"])
@login_required
def panel_usun_zajecie(zaj_id):
    if not _check_role():
        return "Brak dostępu", 403

    zaj = Zajecia.query.get(zaj_id)
    if not zaj or zaj.prowadzacy_id != current_user.prowadzacy_id:
        return "Brak dostępu", 404

    db.session.delete(zaj)
    db.session.commit()
    flash("Zajęcia usunięte", "info")
    return redirect(url_for("routes.panel"))


@routes_bp.route("/panel/pobierz_zajecie/<int:zaj_id>")
@login_required
def panel_pobierz_zajecie(zaj_id):
    if not _check_role():
        return "Brak dostępu", 403

    zaj = Zajecia.query.get(zaj_id)
    if not zaj or zaj.prowadzacy_id != current_user.prowadzacy_id:
        return "Brak dostępu", 404

    obecni = [u.imie_nazwisko for u in zaj.obecni]
    podpis_path = None
    if zaj.prowadzacy.podpis_filename:
        podpis_path = os.path.join("static", zaj.prowadzacy.podpis_filename)

    doc = generuj_liste_obecnosci(
        zaj.data.strftime("%Y-%m-%d"),
        zaj.czas_trwania,
        obecni,
        zaj.prowadzacy.nazwisko,
        podpis_path,
    )

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)

    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=f"lista_{zaj.id}.docx",
    )

