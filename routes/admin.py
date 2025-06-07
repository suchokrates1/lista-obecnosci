from flask import render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import login_required, current_user
from model import db, Prowadzacy, Zajecia, Uczestnik, Uzytkownik
from utils import (
    email_do_koordynatora,
    send_plain_email,
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    SIGNATURE_MAX_SIZE,
)
from doc_generator import generuj_raport_miesieczny
from io import BytesIO
from werkzeug.utils import secure_filename
import os
import smtplib
import logging
from . import routes_bp

logger = logging.getLogger(__name__)

@routes_bp.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        abort(403)

    prowadzacy = Prowadzacy.query.all()
    new_users = (
        Uzytkownik.query.filter_by(role="prowadzacy", approved=False).all()
    )
    for p in prowadzacy:
        p.uczestnicy = sorted(p.uczestnicy, key=lambda x: x.imie_nazwisko.lower())

    zajecia = Zajecia.query.order_by(Zajecia.data.desc()).all()
    ostatnie = {}
    for p in prowadzacy:
        ostatnie_zajecia = Zajecia.query.filter_by(prowadzacy_id=p.id).order_by(Zajecia.data.desc()).first()
        if ostatnie_zajecia:
            ostatnie[p.id] = ostatnie_zajecia.data
    return render_template(
        'admin.html',
        prowadzacy=prowadzacy,
        zajecia=zajecia,
        ostatnie=ostatnie,
        new_users=new_users,
    )

@routes_bp.route('/usun_zajecie/<int:id>', methods=['POST'])
@login_required
def usun_zajecie(id):
    if current_user.role != 'admin':
        abort(403)

    zaj = Zajecia.query.get(id)
    if not zaj:
        abort(404)

    db.session.delete(zaj)
    db.session.commit()
    flash('Zajęcia zostały usunięte', 'info')
    return redirect(url_for('routes.admin_dashboard'))

@routes_bp.route('/raport/<int:prowadzacy_id>', methods=['GET'])
@login_required
def raport(prowadzacy_id):
    if current_user.role != 'admin':
        abort(403)

    prow = Prowadzacy.query.get(prowadzacy_id)
    if not prow:
        abort(404)

    ostatnie = Zajecia.query.filter_by(prowadzacy_id=prowadzacy_id).order_by(Zajecia.data.desc()).first()
    if not ostatnie:
        abort(404)

    miesiac = int(request.args.get('miesiac', ostatnie.data.month))
    rok = int(request.args.get('rok', ostatnie.data.year))
    wyslij = request.args.get('wyslij') == '1'

    wszystkie = Zajecia.query.filter_by(prowadzacy_id=prowadzacy_id).all()
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
        return redirect(url_for('routes.admin_dashboard'))

    return send_file(buf,
                     mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                     as_attachment=True,
                     download_name=f'raport_{miesiac}_{rok}.docx')

@routes_bp.route('/dodaj', methods=['POST'])
@login_required
def dodaj_prowadzacego():
    if current_user.role != 'admin':
        abort(403)

    id_edit = request.form.get('edit_id')
    trener = request.form.get('nowy_trener')
    numer_umowy = request.form.get('nowy_umowa')
    uczestnicy = request.form.get('nowi_uczestnicy')
    podpis = request.files.get('nowy_podpis')

    if not trener or not uczestnicy:
        flash('Wszystkie pola są wymagane', 'danger')
        return redirect(url_for('routes.admin_dashboard'))

    if id_edit:
        prow = Prowadzacy.query.get(id_edit)
        if not prow:
            flash('Nie znaleziono prowadącego', 'danger')
            return redirect(url_for('routes.admin_dashboard'))
        prow.nazwisko = trener
        prow.numer_umowy = numer_umowy
        prow.uczestnicy.clear()
    else:
        prow = Prowadzacy(nazwisko=trener, numer_umowy=numer_umowy)
        db.session.add(prow)
        db.session.flush()

    sanitized = None
    if podpis and podpis.filename:
        sanitized = secure_filename(podpis.filename)
        ext = sanitized.rsplit('.', 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS or podpis.mimetype not in ALLOWED_MIME_TYPES:
            flash('Nieobsługiwany format pliku podpisu. Dozwolone są PNG i JPG.', 'danger')
            return redirect(url_for('routes.admin_dashboard'))
        podpis.stream.seek(0, os.SEEK_END)
        if podpis.stream.tell() > SIGNATURE_MAX_SIZE:
            flash('Plik podpisu jest zbyt du\u017cy.', 'danger')
            return redirect(url_for('routes.admin_dashboard'))
        podpis.stream.seek(0)

    if podpis and sanitized:
        filename = f"{prow.id}_{sanitized}"
        path = os.path.join('static', filename)
        podpis.save(path)
        prow.podpis_filename = filename

    for nazwisko in uczestnicy.strip().splitlines():
        uczestnik = Uczestnik(prowadzacy_id=prow.id, imie_nazwisko=nazwisko)
        db.session.add(uczestnik)

    db.session.commit()
    flash('Prowadzący zapisany', 'success')
    return redirect(url_for('routes.admin_dashboard'))

@routes_bp.route('/usun/<int:id>', methods=['POST'])
@login_required
def usun_prowadzacego(id):
    if current_user.role != 'admin':
        abort(403)

    prow = Prowadzacy.query.get(id)
    if not prow:
        abort(404)

    Uczestnik.query.filter_by(prowadzacy_id=prow.id).delete()
    db.session.delete(prow)
    db.session.commit()

    flash('Prowadzący usunięty', 'info')
    return redirect(url_for('routes.admin_dashboard'))


@routes_bp.route('/approve_user/<int:id>', methods=['POST', 'GET'])
@login_required
def approve_user(id):
    if current_user.role != 'admin':
        abort(403)

    user = Uzytkownik.query.get(id)
    if not user:
        flash('Nie znaleziono użytkownika', 'danger')
        return redirect(url_for('routes.admin_dashboard'))

    user.approved = True
    db.session.commit()

    try:
        send_plain_email(
            user.login,
            'Aktywacja konta w ShareOKO',
            'Twoje konto zostało zatwierdzone i jest już aktywne.',
        )
    except smtplib.SMTPException:
        logger.exception('Failed to send activation email')
        flash('Nie udało się wysłać e-maila do użytkownika', 'danger')

    flash('Użytkownik zatwierdzony', 'success')
    return redirect(url_for('routes.admin_dashboard'))
