from flask import render_template, redirect, url_for, flash, send_file, request, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from io import BytesIO
from model import db, Prowadzacy, Uczestnik, Zajecia
from doc_generator import generuj_liste_obecnosci
from . import routes_bp
import os


@routes_bp.route('/panel')
@login_required
def panel():
    if current_user.role != 'prowadzacy':
        abort(403)

    prow = current_user.prowadzacy
    if not prow:
        abort(404)

    uczestnicy = sorted(prow.uczestnicy, key=lambda x: x.imie_nazwisko.lower())
    zajecia = Zajecia.query.filter_by(prowadzacy_id=prow.id).order_by(Zajecia.data.desc()).all()
    return render_template('panel.html', prowadzacy=prow, uczestnicy=uczestnicy, zajecia=zajecia)


@routes_bp.route('/panel/profil', methods=['POST'])
@login_required
def panel_update_profile():
    if current_user.role != 'prowadzacy':
        abort(403)

    prow = current_user.prowadzacy
    if not prow:
        abort(404)

    prow.imie = request.form.get('imie')
    prow.nazwisko = request.form.get('nazwisko')
    prow.numer_umowy = request.form.get('numer_umowy')

    podpis = request.files.get('podpis')
    if podpis and podpis.filename:
        sanitized = secure_filename(podpis.filename)
        filename = f"{prow.id}_{sanitized}"
        path = os.path.join('static', filename)
        podpis.save(path)
        prow.podpis_filename = filename

    db.session.commit()
    flash('Dane zaktualizowane', 'success')
    return redirect(url_for('routes.panel'))


@routes_bp.route('/panel/uczestnicy', methods=['POST'])
@login_required
def panel_update_participants():
    if current_user.role != 'prowadzacy':
        abort(403)

    prow = current_user.prowadzacy
    if not prow:
        abort(404)

    lista = request.form.get('uczestnicy')
    prow.uczestnicy.clear()
    if lista:
        for linia in lista.strip().splitlines():
            nazwa = linia.strip()
            if nazwa:
                prow.uczestnicy.append(Uczestnik(imie_nazwisko=nazwa))
    db.session.commit()
    flash('Lista uczestnik\u00f3w zaktualizowana', 'success')
    return redirect(url_for('routes.panel'))


@routes_bp.route('/pobierz_zajecie/<int:id>')
@login_required
def pobierz_zajecie(id):
    zaj = Zajecia.query.get(id)
    if not zaj or zaj.prowadzacy_id != current_user.prowadzacy_id:
        abort(403)

    prow = current_user.prowadzacy
    obecni = [u.imie_nazwisko for u in zaj.obecni]
    doc = generuj_liste_obecnosci(
        zaj.data.strftime('%Y-%m-%d'),
        str(zaj.czas_trwania).replace('.', ','),
        obecni,
        prow.nazwisko,
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


@routes_bp.route('/usun_moje_zajecie/<int:id>', methods=['POST'])
@login_required
def usun_moje_zajecie(id):
    zaj = Zajecia.query.get(id)
    if not zaj or zaj.prowadzacy_id != current_user.prowadzacy_id:
        abort(403)

    db.session.delete(zaj)
    db.session.commit()
    flash('Zaj\u0119cia usuni\u0119te', 'info')
    return redirect(url_for('routes.panel'))
