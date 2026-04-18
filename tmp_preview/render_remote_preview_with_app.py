import os
from pathlib import Path

from app import create_app
from model import Setting
from invoice_pdf import generate_invoice_pdf
from ksef_invoice import create_invoice_from_monthly_report

app = create_app()

with app.app_context():
    for setting in Setting.query.all():
        os.environ[setting.key.upper()] = setting.value or ""

    invoice = create_invoice_from_monthly_report(
        hours=6.5,
        month=1,
        year=2026,
        trainer_name="Dawid Suchodolski",
    )

    output_path = Path("/tmp/remote_invoice_preview_with_app.pdf")
    output_path.write_bytes(generate_invoice_pdf(invoice).getvalue())
    print(output_path)
