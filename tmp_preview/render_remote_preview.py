from pathlib import Path

from invoice_pdf import generate_invoice_pdf
from ksef_invoice import create_invoice_from_monthly_report

invoice = create_invoice_from_monthly_report(
    hours=6.5,
    month=1,
    year=2026,
    trainer_name="Dawid Suchodolski",
)

output_path = Path("/tmp/remote_invoice_preview.pdf")
output_path.write_bytes(generate_invoice_pdf(invoice).getvalue())
print(output_path)
