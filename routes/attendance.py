from flask import render_template, request, redirect, url_for, flash, send_file
from flask_login import current_user, login_required
from model import Prowadzacy
from utils import przetworz_liste_obecnosci, email_do_koordynatora
from . import routes_bp

@routes_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    is_admin = current_user.role == 'admin'
    status = None
    akcja = None
    if is_admin:
        prowadzacy = Prowadzacy.query.all()
        try:
            selected_id = int(request.form.get('prowadzący'))
        except (TypeError, ValueError):
            selected_id = prowadzacy[0].id if prowadzacy else None
        wybrany = Prowadzacy.query.get(selected_id)
    else:
        wybrany = Prowadzacy.query.get(current_user.prowadzacy_id)
        prowadzacy = [wybrany] if wybrany else []
        selected_id = wybrany.id if wybrany else None

    uczestnicy = sorted(wybrany.uczestnicy, key=lambda x: x.imie_nazwisko.lower()) if wybrany else []

    if request.method == 'POST':
        akcja = request.form.get('akcja')

        if akcja == 'zmien_prowadzacego' and is_admin:
            return render_template('index.html',
                                   prowadzacy=prowadzacy,
                                   uczestnicy=uczestnicy,
                                   selected=selected_id,
                                   status=status,
                                   is_admin=is_admin,
                                   is_logged=current_user.is_authenticated)
        elif akcja in ['pobierz', 'wyslij']:
            result = przetworz_liste_obecnosci(request.form, wybrany)
            if isinstance(result, tuple) and result[0] == 'error':
                flash(result[1], 'danger')
                return redirect(url_for('routes.index'))
            elif isinstance(result, tuple):
                status, buf, data_str = result
                if akcja == 'pobierz':
                    return send_file(buf,
                                     mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                     as_attachment=True,
                                     download_name=f'lista_{data_str}.docx')
                elif akcja == 'wyslij':
                    email_do_koordynatora(buf, data_str, typ='lista')
                    flash('Lista została wysłana e-mailem', 'success')
                    return redirect(url_for('routes.index'))

    return render_template('index.html',
                           prowadzacy=prowadzacy,
                           uczestnicy=uczestnicy,
                           selected=selected_id,
                           status=status,
                           is_admin=is_admin,
                           is_logged=current_user.is_authenticated)
