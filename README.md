# Lista Obecnosci

This is a small Flask application for managing attendance.

## Environment variables

The application expects several settings to be provided through environment variables:

- `SECRET_KEY` – secret used by Flask for sessions.
- `ADMIN_LOGIN` – login of the administrator account created by `init_db.py`.
- `ADMIN_PASSWORD` – password for the administrator account.
- Mail configuration used when sending attendance lists and reports:
  - `EMAIL_RECIPIENT` – address of the coordinator receiving emails.
  - `SMTP_HOST` – SMTP server hostname.
  - `SMTP_PORT` – port of the SMTP server (465 enables SSL).
  - `EMAIL_LOGIN` – SMTP user name.
  - `EMAIL_PASSWORD` – SMTP password.

You can export them in your shell or put them in an `.env` file when using docker-compose.

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
