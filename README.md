# Lista Obecnosci

This is a small Flask application for managing attendance.

## Deployment

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Apply database migrations after pulling new code:
   ```bash
   flask db upgrade
   ```

Set `FLASK_APP=app:create_app` before running Flask commands.
