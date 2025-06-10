from flask import render_template, request, redirect, url_for, flash, send_file
from flask_login import current_user, login_required
from model import Prowadzacy

from utils import przetworz_liste_obecnosci, email_do_koordynatora
from . import routes_bp
import smtplib
import logging

logger = logging.getLogger(__name__)


@routes_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    status = None
    akcja = None
    is_admin = current_user.role == 'admin'

    if is_admin:
        prowadzacy = Prowadzacy.query.all()
        try:
            selected_id = int(request.form.get('prowadzący'))
        except (TypeError, ValueError):
            selected_id = prowadzacy[0].id if prowadzacy else None
        wybrany = db.session.get(Prowadzacy, selected_id)
    else:
        wybrany = current_user.prowadzacy
        prowadzacy = [wybrany] if wybrany else []
        selected_id = current_user.prowadzacy_id

    uczestnicy = (
        sorted(wybrany.uczestnicy, key=lambda x: x.imie_nazwisko.lower())
        if wybrany
        else []
    )

    domyslny_czas = (
        str(wybrany.domyslny_czas)
        .replace('.', ',')
        .rstrip('0')
        .rstrip(',')
        if wybrany and wybrany.domyslny_czas is not None
        else "1,5"
    )

    if request.method == 'POST':
        akcja = request.form.get('akcja')

        if is_admin and akcja == 'zmien_prowadzacego':
            return render_template(
                'index.html',
                prowadzacy=prowadzacy,
                uczestnicy=uczestnicy,
                selected=selected_id,
                status=status,
                domyslny_czas=domyslny_czas,
                is_logged=True,
            )
        elif akcja in ['pobierz', 'wyslij']:
            result = przetworz_liste_obecnosci(request.form, wybrany)
            if isinstance(result, tuple) and result[0] == 'error':
                flash(result[1], 'danger')
                return redirect(url_for('routes.index'))
            elif isinstance(result, tuple):
                status, buf, data_str = result
                if akcja == 'pobierz':
                    return send_file(
                        buf,
                        mimetype=(
                            'application/vnd.openxmlformats-officedocument.'
                            'wordprocessingml.document'
                        ),
                        as_attachment=True,
                        download_name=f'lista_{data_str}.docx',
                    )
                elif akcja == 'wyslij':
                    try:
                        email_do_koordynatora(buf, data_str, typ='lista')
                        flash('Lista została wysłana e-mailem', 'success')
                    except smtplib.SMTPException:
                        logger.exception('Failed to send attendance email')
                        flash('Nie udało się wysłać e-maila', 'danger')
                    return redirect(url_for('routes.index'))

    return render_template('index.html',
                           prowadzacy=prowadzacy,
                           uczestnicy=uczestnicy,
                           selected=selected_id,
                           status=status,
                           domyslny_czas=domyslny_czas,
                           is_logged=True)
