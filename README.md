# Lista Obecnosci

This is a small Flask application for managing attendance.

## Environment variables

The application expects several settings to be provided through environment variables.
Copy `.env.example` to `.env` and adjust the values, or export them manually:

- `SECRET_KEY` – secret used by Flask for sessions. The application will fail to start if this variable is not set.
- `ADMIN_LOGIN` – e-mail address of the administrator account created by `init_db.py`.
- `ADMIN_PASSWORD` – password for the administrator account.
- `DATABASE_URL` – optional database URI (default `sqlite:///obecnosc.db`).
- Mail configuration used when sending attendance lists and reports:
  - `EMAIL_RECIPIENT` – address of the coordinator receiving emails.
  - `SMTP_HOST` – SMTP server hostname.
  - `SMTP_PORT` – port of the SMTP server (465 enables SSL).
  - `EMAIL_LOGIN` – SMTP user name.
  - `EMAIL_PASSWORD` – SMTP password.
  - `EMAIL_SENDER_NAME` – name used in the *From* header.
  - `EMAIL_FOOTER` – text appended to every outgoing message.
  - `MAX_SIGNATURE_SIZE` – optional limit for uploaded signature images in bytes (default `1048576`).
  - `REG_EMAIL_SUBJECT` / `REG_EMAIL_BODY` – templates for the account activation e-mail.
  - `RESET_EMAIL_SUBJECT` / `RESET_EMAIL_BODY` – templates for password reset messages.

You can export them in your shell or copy `.env.example` to `.env` when using docker-compose.

A `.dockerignore` file keeps the image small by skipping development files like `.git` and the `migrations` directory when building.

## Database setup

Install the required packages first:

```bash
pip install -r requirements.txt
```

To create the database and initial admin user, run:

```bash
python init_db.py
```

If migrations are used, apply them with:

```bash
flask db upgrade
```

Remember to set `FLASK_APP=app:create_app` before running Flask commands.

## Templates

The files `szablon.docx` (attendance template) and `rejestr.docx` (monthly report template) must be present in the project root. They are ignored by Git so provide your own copies.

## Signature images

Only PNG and JPG files are accepted when uploading signature images in the admin
or trainer panels. Files with other extensions or MIME types will be rejected.
Uploads larger than the value of `MAX_SIGNATURE_SIZE` (default 1 MB) will also be refused.

## Login format

All user logins are e-mail addresses. The administrator login specified by
`ADMIN_LOGIN` and the login provided during trainer registration must be valid
e-mail addresses. The application will reject invalid addresses during
registration and login.

## Admin settings

The administrator can change mail-related options from `/admin/settings`.
Values for `SMTP_HOST`, `SMTP_PORT`, `EMAIL_RECIPIENT`, `EMAIL_SENDER_NAME`,
`EMAIL_LOGIN`, `EMAIL_PASSWORD`, `EMAIL_FOOTER` and the e-mail templates are
saved in the database and override environment variables on the next start.
The same form allows changing the admin login and password.
