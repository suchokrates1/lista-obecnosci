import os

from pypdf import PdfReader

from ksef_client import resolve_ksef_token
from invoice_pdf import generate_invoice_pdf
from ksef_invoice import create_invoice_from_monthly_report, generate_fa3_xml


def test_create_invoice_matches_vest_media_numbering_and_dates(monkeypatch):
    env = {
        "INVOICE_ISSUER_NAME": "Jan Kowalski",
        "INVOICE_ISSUER_NIP": "1234567890",
        "INVOICE_ISSUER_ADDRESS": "ul. Testowa 1",
        "INVOICE_ISSUER_POSTAL": "00-001",
        "INVOICE_ISSUER_CITY": "Warszawa",
        "INVOICE_RECIPIENT_NAME": "Vest Media",
        "INVOICE_RECIPIENT_NIP": "0987654321",
        "INVOICE_RECIPIENT_ADDRESS": "ul. Klienta 2",
        "INVOICE_RECIPIENT_POSTAL": "00-002",
        "INVOICE_RECIPIENT_CITY": "Krakow",
        "INVOICE_SERVICE_NAME": "Prowadzenie zajec podcastowych",
        "INVOICE_HOURLY_RATE": "150.00",
        "INVOICE_VAT_RATE": "zw",
        "INVOICE_PAYMENT_DEADLINE_DAYS": "14",
        "INVOICE_NUMBER_PREFIX": "A1",
        "INVOICE_NUMBER_COUNTER": "1",
        "INVOICE_NUMBER_TEMPLATE": "{prefix}/{counter}/{year}",
        "INVOICE_ISSUE_DATE_MODE": "report_month_day",
        "INVOICE_ISSUE_DAY_OF_MONTH": "26",
        "INVOICE_SALE_DATE_MODE": "issue_date",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    invoice = create_invoice_from_monthly_report(hours=6.5, month=1, year=2026)

    assert invoice.invoice_number == "A1/1/2026"
    assert invoice.issue_date.strftime("%Y-%m-%d") == "2026-01-26"
    assert invoice.sale_date.strftime("%Y-%m-%d") == "2026-01-26"
    assert invoice.payment_deadline.strftime("%Y-%m-%d") == "2026-02-09"


def test_generate_fa3_xml_for_vat_exempt_invoice(monkeypatch):
    env = {
        "INVOICE_ISSUER_NAME": "Jan Kowalski",
        "INVOICE_ISSUER_NIP": "1234567890",
        "INVOICE_ISSUER_ADDRESS": "ul. Testowa 1",
        "INVOICE_ISSUER_POSTAL": "00-001",
        "INVOICE_ISSUER_CITY": "Warszawa",
        "INVOICE_RECIPIENT_NAME": "Vest Media",
        "INVOICE_RECIPIENT_NIP": "0987654321",
        "INVOICE_RECIPIENT_ADDRESS": "ul. Klienta 2",
        "INVOICE_RECIPIENT_POSTAL": "00-002",
        "INVOICE_RECIPIENT_CITY": "Krakow",
        "INVOICE_SERVICE_NAME": "Prowadzenie zajec podcastowych",
        "INVOICE_HOURLY_RATE": "150.00",
        "INVOICE_VAT_RATE": "zw",
        "INVOICE_VAT_EXEMPTION_REASON": "Zwolnienie na podstawie art. 113 ust. 1 lub 9 Ustawy o VAT",
        "INVOICE_PKWIU": "85.59.19.0",
        "INVOICE_PAYMENT_METHOD": "1",
        "INVOICE_NUMBER_PREFIX": "FV",
        "INVOICE_NUMBER_COUNTER": "1",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    invoice = create_invoice_from_monthly_report(hours=10, month=1, year=2026, trainer_name="Jan Test")
    xml = generate_fa3_xml(invoice)

    assert 'kodSystemowy="FA (3)"' in xml
    assert 'wersjaSchemy="1-0E"' in xml
    assert "<P_12>zw</P_12>" in xml
    assert "<P_19>1</P_19>" in xml
    assert "<P_19A>Zwolnienie na podstawie art. 113 ust. 1 lub 9 Ustawy o VAT</P_19A>" in xml
    assert "<JST>2</JST>" in xml
    assert "<GV>2</GV>" in xml
    assert "<P_16>2</P_16>" in xml
    assert "<P_PMarzyN>1</P_PMarzyN>" in xml
    assert "PKWiU 85.59.19.0" in xml
    assert "<DaneIdentyfikacyjne>" in xml
    assert "<AdresKoresp>" in xml


def test_resolve_ksef_token_prefers_environment_specific_value(monkeypatch):
    monkeypatch.setenv("KSEF_TOKEN", "legacy-token")
    monkeypatch.setenv("KSEF_TOKEN_DEMO", "demo-token")
    monkeypatch.setenv("KSEF_TOKEN_PRODUCTION", "production-token")

    assert resolve_ksef_token("demo") == "demo-token"
    assert resolve_ksef_token("production") == "production-token"


def test_resolve_ksef_token_falls_back_to_demo_for_test(monkeypatch):
    monkeypatch.delenv("KSEF_TOKEN_TEST", raising=False)
    monkeypatch.setenv("KSEF_TOKEN_DEMO", "demo-token")
    monkeypatch.setenv("KSEF_TOKEN", "legacy-token")

    assert resolve_ksef_token("test") == "demo-token"


def test_generate_invoice_pdf_embeds_unicode_font(monkeypatch):
    env = {
        "INVOICE_ISSUER_NAME": "Dawid Suchodolski",
        "INVOICE_ISSUER_NIP": "1234567890",
        "INVOICE_ISSUER_ADDRESS": "ul. Wrocławska 15 / 7",
        "INVOICE_ISSUER_POSTAL": "59-220",
        "INVOICE_ISSUER_CITY": "Legnica",
        "INVOICE_RECIPIENT_NAME": "FUNDACJA WIDZIMY INACZEJ",
        "INVOICE_RECIPIENT_NIP": "5242785036",
        "INVOICE_RECIPIENT_ADDRESS": "ul. Stanisława Skarżyńskiego 6A",
        "INVOICE_RECIPIENT_POSTAL": "02-377",
        "INVOICE_RECIPIENT_CITY": "Warszawa",
        "INVOICE_SERVICE_NAME": "Prowadzenie zajęć z tworzenia podcastów",
        "INVOICE_HOURLY_RATE": "160.00",
        "INVOICE_VAT_RATE": "zw",
        "INVOICE_VAT_EXEMPTION_REASON": "Zwolnienie na podstawie art. 113 ust. 1 lub 9 Ustawy o VAT",
        "INVOICE_PKWIU": "85.59.19.0",
        "INVOICE_PAYMENT_METHOD": "1",
        "INVOICE_NUMBER_PREFIX": "A1",
        "INVOICE_NUMBER_COUNTER": "1",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    invoice = create_invoice_from_monthly_report(hours=6.5, month=1, year=2026, trainer_name="Dawid Suchodolski")
    pdf_buffer = generate_invoice_pdf(invoice)
    pdf_bytes = pdf_buffer.getvalue()

    assert b"DejaVuSans" in pdf_bytes or b"Arial" in pdf_bytes

    reader = PdfReader(pdf_buffer)
    extracted_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    assert "Wrocławska" in extracted_text
    assert "Stanisława Skarżyńskiego" in extracted_text
    assert "Data wystawienia:" in extracted_text
    assert "Faktura nr" in extracted_text
    assert "Wystawca" in extracted_text
    assert "Nabywca" in extracted_text
    assert "Rozliczenie VAT (PLN)" in extracted_text
    assert "Do zapłaty" in extracted_text
    assert "jeden tysiąc czterdzieści 00/100 PLN" in extracted_text
    assert "godz." in extracted_text
    assert "mOrganizer finansów" not in extracted_text