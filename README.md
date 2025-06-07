# Lista Obecnosci

This is a small Flask application for managing attendance.

## Environment variables

The application expects several settings to be provided through environment variables.
Copy `.env.example` to `.env` and adjust the values, or export them manually:

- `SECRET_KEY` – secret used by Flask for sessions.
- `ADMIN_LOGIN` – e-mail address of the administrator account created by `init_db.py`.
- `ADMIN_PASSWORD` – password for the administrator account.
- `DATABASE_URL` – optional database URI (default `sqlite:///obecnosc.db`).
- Mail configuration used when sending attendance lists and reports:
  - `EMAIL_RECIPIENT` – address of the coordinator receiving emails.
  - `SMTP_HOST` – SMTP server hostname.
  - `SMTP_PORT` – port of the SMTP server (465 enables SSL).
  - `EMAIL_LOGIN` – SMTP user name.
  - `EMAIL_PASSWORD` – SMTP password.

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

## Login format

All user logins are e-mail addresses. The administrator login specified by
`ADMIN_LOGIN` and the login provided during trainer registration must be valid
e-mail addresses. The application will reject invalid addresses during
registration and login.
