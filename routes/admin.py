from flask import render_template, request, redirect, url_for, flash, send_file, abort, current_app
from flask_login import login_required, current_user
from model import db, Prowadzacy, Zajecia, Uczestnik, Uzytkownik, Setting
from utils import (
    email_do_koordynatora,
    send_plain_email,
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    SIGNATURE_MAX_SIZE,
    REMOVE_SIGNATURE_BG,
    load_db_settings,
)
from doc_generator import generuj_raport_miesieczny, generuj_liste_obecnosci
from io import BytesIO
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
import os
from datetime import datetime
import smtplib
import logging
from PIL import Image
try:
    from rembg import remove as rembg_remove
except Exception:  # rembg optional
    rembg_remove = None
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


@routes_bp.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if current_user.role != 'admin':
        abort(403)

    keys = [
        'smtp_host', 'smtp_port', 'email_recipient', 'max_signature_size',
        'remove_signature_bg',
        'email_sender_name', 'email_login', 'email_password', 'email_footer',
        'email_list_subject', 'email_list_body',
        'email_report_subject', 'email_report_body',
        'registration_email_subject', 'registration_email_body',
        'reg_email_subject', 'reg_email_body',
        'reset_email_subject', 'reset_email_body'
    ]

    if request.method == 'POST':
        for key in keys:
            if key == 'remove_signature_bg':
                val = '1' if request.form.get(key) else '0'
            else:
                val = request.form.get(key)
            if val is None:
                continue
            setting = Setting.query.get(key)
            if setting:
                setting.value = val
            else:
                db.session.add(Setting(key=key, value=val))
            os.environ[key.upper()] = val

        admin_login = request.form.get('admin_login')
        admin_password = request.form.get('admin_password')
        admin_user = Uzytkownik.query.filter_by(role='admin').first()
        if admin_user:
            if admin_login and admin_login != admin_user.login:
                admin_user.login = admin_login
            if admin_password:
                admin_user.haslo_hash = generate_password_hash(admin_password)
        db.session.commit()
        load_db_settings(current_app)
        flash('Ustawienia zostały zapisane', 'success')
        return redirect(url_for('routes.admin_settings'))

    values = {}
    for key in keys:
        setting = Setting.query.get(key)
        values[key] = os.getenv(key.upper(), setting.value if setting else '')

    admin_user = Uzytkownik.query.filter_by(role='admin').first()
    admin_login = admin_user.login if admin_user else ''
    return render_template('settings.html', values=values, admin_login=admin_login)

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
    imie = request.form.get('nowy_imie')
    nazwisko = request.form.get('nowy_nazwisko')
    numer_umowy = request.form.get('nowy_umowa')
    uczestnicy = request.form.get('nowi_uczestnicy')
    podpis = request.files.get('nowy_podpis')

    if not imie or not nazwisko or not uczestnicy:
        flash('Wszystkie pola są wymagane', 'danger')
        return redirect(url_for('routes.admin_dashboard'))

    if id_edit:
        prow = Prowadzacy.query.get(id_edit)
        if not prow:
            flash('Nie znaleziono prowadącego', 'danger')
            return redirect(url_for('routes.admin_dashboard'))
        prow.imie = imie
        prow.nazwisko = nazwisko
        prow.numer_umowy = numer_umowy
        prow.uczestnicy.clear()
    else:
        prow = Prowadzacy(imie=imie, nazwisko=nazwisko, numer_umowy=numer_umowy)
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
        base = os.path.splitext(sanitized)[0]
        ext = sanitized.rsplit('.', 1)[-1].lower()
        if REMOVE_SIGNATURE_BG:
            ext = 'png'
        filename = f"{prow.id}_{base}.{ext}"
        path = os.path.join('static', filename)
        try:
            podpis.stream.seek(0)
            img = Image.open(podpis.stream)
            if REMOVE_SIGNATURE_BG:
                if rembg_remove:
                    img = rembg_remove(img)
                img = img.convert('RGBA')
                datas = img.getdata()
                new_data = []
                for item in datas:
                    if item[0] > 250 and item[1] > 250 and item[2] > 250:
                        new_data.append((255, 255, 255, 0))
                    else:
                        new_data.append(item)
                img.putdata(new_data)
                img.save(path, format='PNG')
            else:
                img.save(path)
        except Exception:
            flash('Nie udało się przetworzyć obrazu podpisu', 'danger')
            return redirect(url_for('routes.admin_dashboard'))
        prow.podpis_filename = filename

    for nazw in uczestnicy.strip().splitlines():
        uczestnik = Uczestnik(prowadzacy_id=prow.id, imie_nazwisko=nazw)
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
            'REG_EMAIL_SUBJECT',
            'REG_EMAIL_BODY',
            'Aktywacja konta w ShareOKO',
            'Twoje konto zostało zatwierdzone i jest już aktywne.'
        )
    except smtplib.SMTPException:
        logger.exception('Failed to send activation email')
        flash('Nie udało się wysłać e-maila do użytkownika', 'danger')

    flash('Użytkownik zatwierdzony', 'success')
    return redirect(url_for('routes.admin_dashboard'))


@routes_bp.route('/edytuj_zajecie/<int:id>', methods=['GET', 'POST'])
@login_required
def edytuj_zajecie(id):
    if current_user.role != 'admin':
        abort(403)

    zaj = Zajecia.query.get(id)
    if not zaj:
        abort(404)

    prow = zaj.prowadzacy
    uczestnicy = sorted(prow.uczestnicy, key=lambda x: x.imie_nazwisko.lower())

    if request.method == 'POST':
        data_str = request.form.get('data')
        czas = request.form.get('czas')
        obecni_ids = request.form.getlist('obecny')

        if not data_str or not czas:
            flash('Brakuje wymaganych danych', 'danger')
            return redirect(url_for('routes.edytuj_zajecie', id=id))

        zaj.data = datetime.strptime(data_str, '%Y-%m-%d')
        try:
            zaj.czas_trwania = float(czas.replace(',', '.'))
        except ValueError:
            zaj.czas_trwania = 0
        zaj.obecni = Uczestnik.query.filter(Uczestnik.id.in_(obecni_ids)).all()
        db.session.commit()
        flash('Zajęcia zaktualizowane', 'success')
        return redirect(url_for('routes.admin_dashboard'))

    obecni_ids = [u.id for u in zaj.obecni]
    czas = str(zaj.czas_trwania).replace('.', ',')
    return render_template(
        'edit_zajecie.html',
        zajecie=zaj,
        uczestnicy=uczestnicy,
        obecni_ids=obecni_ids,
        czas=czas,
        back_url=url_for('routes.admin_dashboard'),
    )


@routes_bp.route('/pobierz_zajecie_admin/<int:id>')
@login_required
def pobierz_zajecie_admin(id):
    if current_user.role != 'admin':
        abort(403)

    zaj = Zajecia.query.get(id)
    if not zaj:
        abort(404)

    prow = zaj.prowadzacy
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
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=f'lista_{data_str}.docx',
    )
