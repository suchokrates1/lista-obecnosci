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
  - `REMOVE_SIGNATURE_BG` – when set to `1`, white background is removed from uploaded signatures.
  - `EMAIL_LIST_SUBJECT` / `EMAIL_LIST_BODY` – templates for attendance lists (`{date}` placeholder).
  - `EMAIL_REPORT_SUBJECT` / `EMAIL_REPORT_BODY` – templates for monthly reports (`{date}` placeholder).
  - `REGISTRATION_EMAIL_SUBJECT` / `REGISTRATION_EMAIL_BODY` – templates for registration notifications (`{name}`, `{login}`, `{link}`).
  - `REG_EMAIL_SUBJECT` / `REG_EMAIL_BODY` – templates for the account activation e-mail.
  - `RESET_EMAIL_SUBJECT` / `RESET_EMAIL_BODY` – templates for password reset messages (`{link}`).

All of the above mail variables (except `EMAIL_RECIPIENT`) must be provided. `SMTP_PORT` has to be an integer and the application will refuse to start when any of these settings are missing or invalid.

The placeholders shown above are substituted automatically when the e-mails are
sent. For example, `{date}` is replaced with the list or report date and `{link}`
with the appropriate URL.

You can export them in your shell or copy `.env.example` to `.env` when using docker-compose.

A `.dockerignore` file keeps the image small by skipping development files like `.git` and the `migrations` directory when building.

### Asynchronous e-mail sending

The helper functions `send_plain_email` and `email_do_koordynatora` accept a
`queue=True` argument. When enabled, outgoing messages are queued and delivered
by a background thread instead of being sent immediately.

## Database setup

Install the required packages first:

```bash
pip install -r requirements.txt
```
The file pins exact versions of the dependencies to avoid unexpected upgrades.
The list includes `Pillow` for image handling.  Installing `rembg` is optional
but enables better signature background removal when `REMOVE_SIGNATURE_BG` is
set.

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
If `REMOVE_SIGNATURE_BG` is set, the application removes white background from
uploaded signatures and stores them as PNG files. The helper
`utils.process_signature(file)` performs this conversion and returns the saved
filename using the `Pillow` library. Installing the optional `rembg` package
allows for more advanced background removal when the option is enabled.

## Login format

All user logins are e-mail addresses. The administrator login specified by
`ADMIN_LOGIN` and the login provided during trainer registration must be valid
e-mail addresses. The application will reject invalid addresses during
registration and login.

## Admin settings

The administrator can change mail-related options from `/admin/settings`.
SMTP credentials and footer are followed by a set of tabs with message
templates for the different e-mails sent by the application (attendance list,
monthly report, registration notification, account activation and password
reset). Each tab contains inputs for the subject and body of a single e-mail.
Values entered here are stored in the database and override environment
variables on the next start.  The same form allows changing the admin login and
password.

## Password reset tokens cleanup

Expired password reset tokens are deleted automatically whenever the
`/reset-request` or `/reset/<token>` routes are accessed. For scheduled
maintenance you can also run:

```bash
flask purge-tokens
```

This command removes old entries and can be triggered from cron.

### Generating monthly reports

Use the ``generate-reports`` command to create reports for all trainers with
sessions in a given month:

```bash
flask generate-reports --month 5 --year 2025 --email
```

Reports are saved under ``reports/`` using names like
``raport_<id>_5_2025.docx``.  When ``--email`` is supplied each generated file
is also sent to the coordinator.

## Running tests

Install pytest and run the test suite with:

```bash
pip install pytest
pytest
```
The tests create a temporary SQLite database and verify route availability, registration, login, access control and helper utilities.
