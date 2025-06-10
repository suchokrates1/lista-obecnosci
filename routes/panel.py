from flask import render_template, redirect, url_for, flash, send_file, request, abort
from flask_login import current_user
from utils.auth import role_required
from io import BytesIO
from model import db, Uczestnik, Zajecia
from doc_generator import generuj_liste_obecnosci, generuj_raport_miesieczny
from datetime import datetime
from . import routes_bp
import os
import smtplib
import logging
from utils import (
    validate_signature,
    SignatureValidationError,
    process_signature,
    email_do_koordynatora,
    get_participant_stats,
    get_monthly_summary,
)

logger = logging.getLogger(__name__)


@routes_bp.route('/panel')
@role_required('prowadzacy')
def panel():

    prow = current_user.prowadzacy
    if not prow:
        abort(404)

    uczestnicy, zajecia, stats, total_sessions = get_participant_stats(prow)
    ostatnie = zajecia[0] if zajecia else None
    domyslny_czas = (
        str(prow.domyslny_czas).replace('.', ',').rstrip('0').rstrip(',')
        if prow.domyslny_czas is not None
        else ''
    )
    podsumowanie = get_monthly_summary(zajecia)
    return render_template(
        'panel.html',
        prowadzacy=prow,
        uczestnicy=uczestnicy,
        zajecia=zajecia,
        ostatnie=ostatnie,
        domyslny_czas=domyslny_czas,
        podsumowanie=podsumowanie,
        stats=stats,
        total_sessions=total_sessions,
    )


@routes_bp.route('/panel/profil', methods=['POST'])
@role_required('prowadzacy')
def panel_update_profile():

    prow = current_user.prowadzacy
    if not prow:
        abort(404)

    prow.imie = request.form.get('imie')
    prow.nazwisko = request.form.get('nazwisko')
    prow.numer_umowy = request.form.get('numer_umowy')
    czas_val = request.form.get('domyslny_czas', '').strip()
    if czas_val:
        try:
            prow.domyslny_czas = float(czas_val.replace(',', '.'))
        except ValueError:
            prow.domyslny_czas = None
    else:
        prow.domyslny_czas = None

    podpis = request.files.get('podpis')
    sanitized = None
    if podpis and podpis.filename:
        try:
            sanitized, error = validate_signature(podpis)
        except SignatureValidationError:
            flash('Nie udało się przetworzyć obrazu podpisu', 'danger')
            return redirect(url_for('routes.panel'))
        if error:
            flash(error, 'danger')
            return redirect(url_for('routes.panel'))

    if podpis and sanitized:
        try:
            filename = process_signature(podpis.stream)
        except Exception:
            flash('Nie udało się przetworzyć obrazu podpisu', 'danger')
            return redirect(url_for('routes.panel'))
        prow.podpis_filename = filename

    db.session.commit()
    flash('Dane zaktualizowane', 'success')
    return redirect(url_for('routes.panel'))


@routes_bp.route('/panel/dodaj_uczestnika', methods=['POST'])
@role_required('prowadzacy')
def dodaj_uczestnika():
    """Add a participant for the logged in trainer."""

    prow = current_user.prowadzacy
    if not prow:
        abort(404)

    name = request.form.get('new_participant', '').strip()
    if name:
        prow.uczestnicy.append(Uczestnik(imie_nazwisko=name))
        db.session.commit()
        flash('Uczestnik dodany', 'success')
    else:
        flash('Brak nazwy uczestnika', 'danger')

    return redirect(url_for('routes.panel'))


@routes_bp.route('/panel/zmien_uczestnika/<int:id>', methods=['POST'])
@role_required('prowadzacy')
def zmien_uczestnika(id):
    """Rename a participant belonging to the logged in trainer."""

    uczestnik = db.session.get(Uczestnik, id)
    if not uczestnik or uczestnik.prowadzacy_id != current_user.prowadzacy_id:
        abort(403)

    new_name = request.form.get('new_name', '').strip()
    if new_name:
        uczestnik.imie_nazwisko = new_name
        db.session.commit()
        flash('Uczestnik zaktualizowany', 'success')
    else:
        flash('Brak nazwy uczestnika', 'danger')

    return redirect(url_for('routes.panel'))


@routes_bp.route('/usun_uczestnika/<int:id>', methods=['POST'])
@role_required('prowadzacy')
def usun_uczestnika(id):
    """Delete a participant belonging to the logged in trainer."""

    uczestnik = db.session.get(Uczestnik, id)
    if not uczestnik or uczestnik.prowadzacy_id != current_user.prowadzacy_id:
        abort(403)

    db.session.delete(uczestnik)
    db.session.commit()
    flash('Uczestnik usunięty', 'info')
    return redirect(url_for('routes.panel'))


@routes_bp.route('/pobierz_zajecie/<int:id>')
@role_required('prowadzacy')
def pobierz_zajecie(id):
    zaj = db.session.get(Zajecia, id)
    if not zaj or zaj.prowadzacy_id != current_user.prowadzacy_id:
        abort(403)

    prow = current_user.prowadzacy
    obecni = [u.imie_nazwisko for u in zaj.obecni]
    doc = generuj_liste_obecnosci(
        zaj.data.strftime('%Y-%m-%d'),
        str(zaj.czas_trwania).replace('.', ','),
        obecni,
        f"{prow.imie} {prow.nazwisko}",
        os.path.join('static', prow.podpis_filename)
    )

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    data_str = zaj.data.strftime('%Y-%m-%d')
    return send_file(buf,
                     mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                     as_attachment=True,
                     download_name=f'lista_{data_str}.docx')


@routes_bp.route('/wyslij_zajecie/<int:id>')
@role_required('prowadzacy')
def wyslij_zajecie(id):
    """Send the attendance list for the given session via e-mail."""
    zaj = db.session.get(Zajecia, id)
    if not zaj or zaj.prowadzacy_id != current_user.prowadzacy_id:
        abort(403)

    prow = current_user.prowadzacy
    obecni = [u.imie_nazwisko for u in zaj.obecni]
    doc = generuj_liste_obecnosci(
        zaj.data.strftime('%Y-%m-%d'),
        str(zaj.czas_trwania).replace('.', ','),
        obecni,
        f"{prow.imie} {prow.nazwisko}",
        os.path.join('static', prow.podpis_filename),
    )

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    data_str = zaj.data.strftime('%Y-%m-%d')

    try:
        email_do_koordynatora(buf, data_str, typ='lista')
        zaj.wyslano = True
        db.session.commit()
        flash('Lista została wysłana e-mailem', 'success')
    except smtplib.SMTPException:
        logger.exception('Failed to send attendance email')
        flash('Nie udało się wysłać e-maila', 'danger')

    return redirect(url_for('routes.panel'))


@routes_bp.route('/usun_moje_zajecie/<int:id>', methods=['POST'])
@role_required('prowadzacy')
def usun_moje_zajecie(id):
    zaj = db.session.get(Zajecia, id)
    if not zaj or zaj.prowadzacy_id != current_user.prowadzacy_id:
        abort(403)

    db.session.delete(zaj)
    db.session.commit()
    flash('Zaj\u0119cia usuni\u0119te', 'info')
    return redirect(url_for('routes.panel'))


@routes_bp.route('/panel/edytuj_zajecie/<int:id>', methods=['GET', 'POST'])
@role_required('prowadzacy')
def panel_edytuj_zajecie(id):
    zaj = db.session.get(Zajecia, id)
    if not zaj or zaj.prowadzacy_id != current_user.prowadzacy_id:
        abort(403)

    prow = current_user.prowadzacy
    uczestnicy = sorted(prow.uczestnicy, key=lambda x: x.imie_nazwisko.lower())

    if request.method == 'POST':
        data_str = request.form.get('data')
        czas = request.form.get('czas')
        obecni_ids = request.form.getlist('obecny')

        if not data_str or not czas:
            flash('Brakuje wymaganych danych', 'danger')
            return redirect(url_for('routes.panel_edytuj_zajecie', id=id))

        zaj.data = datetime.strptime(data_str, '%Y-%m-%d')
        try:
            zaj.czas_trwania = float(czas.replace(',', '.'))
        except ValueError:
            zaj.czas_trwania = 0
        zaj.obecni = Uczestnik.query.filter(Uczestnik.id.in_(obecni_ids)).all()
        db.session.commit()
        flash('Zajęcia zaktualizowane', 'success')
        return redirect(url_for('routes.panel'))

    obecni_ids = [u.id for u in zaj.obecni]
    czas = str(zaj.czas_trwania).replace('.', ',')
    return render_template(
        'edit_zajecie.html',
        zajecie=zaj,
        uczestnicy=uczestnicy,
        obecni_ids=obecni_ids,
        czas=czas,
        back_url=url_for('routes.panel'),
    )


@routes_bp.route('/panel/raport', methods=['GET'])
@role_required('prowadzacy')
def panel_raport():
    """Generate or send a monthly report for the logged in trainer."""

    prow = current_user.prowadzacy
    if not prow:
        abort(404)

    ostatnie = (
        Zajecia.query.filter_by(prowadzacy_id=prow.id)
        .order_by(Zajecia.data.desc())
        .first()
    )
    if not ostatnie:
        abort(404)

    try:
        miesiac = int(request.args.get('miesiac', ostatnie.data.month))
        rok = int(request.args.get('rok', ostatnie.data.year))
    except (TypeError, ValueError):
        flash('Niepoprawny miesiąc lub rok', 'danger')
        return redirect(url_for('routes.panel'))
    if not 1 <= miesiac <= 12 or rok < 2000:
        flash('Niepoprawny miesiąc lub rok', 'danger')
        return redirect(url_for('routes.panel'))
    wyslij = request.args.get('wyslij') == '1'

    wszystkie = Zajecia.query.filter_by(prowadzacy_id=prow.id).all()
    doc = generuj_raport_miesieczny(prow, wszystkie, 'rejestr.docx', 'static', miesiac, rok)

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)

    if wyslij:
        try:
            email_do_koordynatora(buf, f'{miesiac}_{rok}', typ='raport')
            flash('Raport został wysłany e-mailem', 'success')
        except smtplib.SMTPException:
            logger.exception('Failed to send report email')
            flash('Nie udało się wysłać e-maila', 'danger')
        return redirect(url_for('routes.panel'))

    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=f'raport_{miesiac}_{rok}.docx',
    )


@routes_bp.route('/panel/statystyki')
@role_required('prowadzacy')
def panel_statystyki():
    """Show attendance statistics for the logged in trainer."""

    prow = current_user.prowadzacy
    if not prow:
        abort(404)

    uczestnicy, _zajecia, stats_map, total = get_participant_stats(prow)
    stats = [
        {
            'uczestnik': val['uczestnik'],
            'present': val['present'],
            'percent': val['percent'],
        }
        for val in stats_map.values()
    ]

    return render_template(
        'statystyki.html',
        prowadzacy=prow,
        stats=stats,
        total_sessions=total,
    )
