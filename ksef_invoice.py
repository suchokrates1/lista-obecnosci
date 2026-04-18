"""KSeF invoice domain model and FA(3) XML generator."""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import logging
import os
from typing import Dict, Optional
import uuid
import xml.etree.ElementTree as ET
from xml.dom import minidom

logger = logging.getLogger(__name__)

KSEF_FA3_NS = "http://crd.gov.pl/wzor/2025/06/25/13775/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
XSD_NS = "http://www.w3.org/2001/XMLSchema"
ETD_NS = "http://crd.gov.pl/xml/schematy/dziedzinowe/mf/2022/01/05/eD/DefinicjeTypy/"

MONTH_NAMES = {
    1: "styczeń",
    2: "luty",
    3: "marzec",
    4: "kwiecień",
    5: "maj",
    6: "czerwiec",
    7: "lipiec",
    8: "sierpień",
    9: "wrzesień",
    10: "październik",
    11: "listopad",
    12: "grudzień",
}

PAYMENT_METHOD_LABELS = {
    "1": "Przelew",
    "2": "Gotówka",
    "6": "Karta płatnicza",
    "7": "Inna",
}


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _format_decimal(value: Decimal) -> str:
    return f"{_quantize(value):.2f}"


def _address_line(postal_code: str, city: str) -> str:
    return " ".join(part for part in (postal_code, city) if part).strip()


def _append_text(parent: ET.Element, name: str, value: Optional[str]) -> Optional[ET.Element]:
    if value in (None, ""):
        return None
    child = ET.SubElement(parent, name)
    child.text = value
    return child


def prettify_xml(elem: ET.Element) -> str:
    rough_string = ET.tostring(elem, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


@dataclass
class InvoiceData:
    issuer_name: str = ""
    issuer_nip: str = ""
    issuer_address: str = ""
    issuer_postal: str = ""
    issuer_city: str = ""
    issuer_country: str = "PL"
    issuer_email: str = ""
    issuer_phone: str = ""
    issuer_bank_account: str = ""
    issuer_bank_name: str = ""

    recipient_name: str = ""
    recipient_nip: str = ""
    recipient_address: str = ""
    recipient_postal: str = ""
    recipient_city: str = ""
    recipient_country: str = "PL"
    recipient_email: str = ""
    recipient_phone: str = ""

    invoice_number: str = ""
    issue_date: datetime = field(default_factory=datetime.now)
    sale_date: datetime = field(default_factory=datetime.now)
    payment_deadline: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=14))
    payment_method: str = "1"
    issue_place: str = ""

    service_name: str = ""
    service_unit: str = "godz."
    hours: Decimal = field(default_factory=lambda: Decimal("0"))
    hourly_rate: Decimal = field(default_factory=lambda: Decimal("0"))
    currency: str = "PLN"
    vat_rate: str = "zw"
    vat_exemption_reason: str = "Zwolnienie na podstawie art. 113 ust. 1 lub 9 Ustawy o VAT"
    pkwiu: str = "85.59.19.0"
    payment_description: str = ""

    net_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    vat_amount: Decimal = field(default_factory=lambda: Decimal("0"))
    gross_amount: Decimal = field(default_factory=lambda: Decimal("0"))

    def calculate_amounts(self) -> None:
        self.net_amount = _quantize(self.hours * self.hourly_rate)
        if self.is_vat_exempt:
            self.vat_amount = Decimal("0.00")
        else:
            rate = Decimal(self.vat_rate)
            self.vat_amount = _quantize(self.net_amount * rate / Decimal("100"))
        self.gross_amount = _quantize(self.net_amount + self.vat_amount)

    @property
    def is_vat_exempt(self) -> bool:
        return self.vat_rate.strip().lower() in {"zw", "exempt"}

    @property
    def payment_method_label(self) -> str:
        return PAYMENT_METHOD_LABELS.get(self.payment_method, self.payment_method)


def load_invoice_settings_from_env() -> Dict[str, str]:
    return {
        "ksef_enabled": os.getenv("KSEF_ENABLED", "0"),
        "ksef_environment": os.getenv("KSEF_ENVIRONMENT", "demo"),
        "ksef_nip": os.getenv("KSEF_NIP", ""),
        "ksef_token": os.getenv("KSEF_TOKEN", ""),
        "ksef_token_demo": os.getenv("KSEF_TOKEN_DEMO", ""),
        "ksef_token_test": os.getenv("KSEF_TOKEN_TEST", ""),
        "ksef_token_production": os.getenv("KSEF_TOKEN_PRODUCTION", ""),
        "invoice_issuer_name": os.getenv("INVOICE_ISSUER_NAME", ""),
        "invoice_issuer_nip": os.getenv("INVOICE_ISSUER_NIP", ""),
        "invoice_issuer_address": os.getenv("INVOICE_ISSUER_ADDRESS", ""),
        "invoice_issuer_postal": os.getenv("INVOICE_ISSUER_POSTAL", ""),
        "invoice_issuer_city": os.getenv("INVOICE_ISSUER_CITY", ""),
        "invoice_issuer_country": os.getenv("INVOICE_ISSUER_COUNTRY", "PL"),
        "invoice_issuer_email": os.getenv("INVOICE_ISSUER_EMAIL", ""),
        "invoice_issuer_phone": os.getenv("INVOICE_ISSUER_PHONE", ""),
        "invoice_issuer_bank_account": os.getenv("INVOICE_ISSUER_BANK_ACCOUNT", ""),
        "invoice_issuer_bank_name": os.getenv("INVOICE_ISSUER_BANK_NAME", ""),
        "invoice_recipient_name": os.getenv("INVOICE_RECIPIENT_NAME", ""),
        "invoice_recipient_nip": os.getenv("INVOICE_RECIPIENT_NIP", ""),
        "invoice_recipient_address": os.getenv("INVOICE_RECIPIENT_ADDRESS", ""),
        "invoice_recipient_postal": os.getenv("INVOICE_RECIPIENT_POSTAL", ""),
        "invoice_recipient_city": os.getenv("INVOICE_RECIPIENT_CITY", ""),
        "invoice_recipient_country": os.getenv("INVOICE_RECIPIENT_COUNTRY", "PL"),
        "invoice_service_name": os.getenv("INVOICE_SERVICE_NAME", "Prowadzenie zajęć podcastowych"),
        "invoice_hourly_rate": os.getenv("INVOICE_HOURLY_RATE", "0.00"),
        "invoice_currency": os.getenv("INVOICE_CURRENCY", "PLN"),
        "invoice_vat_rate": os.getenv("INVOICE_VAT_RATE", "zw"),
        "invoice_vat_exemption_reason": os.getenv(
            "INVOICE_VAT_EXEMPTION_REASON",
            "Zwolnienie na podstawie art. 113 ust. 1 lub 9 Ustawy o VAT",
        ),
        "invoice_pkwiu": os.getenv("INVOICE_PKWIU", "85.59.19.0"),
        "invoice_payment_deadline_days": os.getenv("INVOICE_PAYMENT_DEADLINE_DAYS", "14"),
        "invoice_payment_method": os.getenv("INVOICE_PAYMENT_METHOD", "1"),
        "invoice_payment_description": os.getenv("INVOICE_PAYMENT_DESCRIPTION", ""),
        "invoice_issue_place": os.getenv("INVOICE_ISSUE_PLACE", ""),
        "invoice_number_prefix": os.getenv("INVOICE_NUMBER_PREFIX", "FV"),
        "invoice_number_counter": os.getenv("INVOICE_NUMBER_COUNTER", "1"),
        "invoice_number_template": os.getenv(
            "INVOICE_NUMBER_TEMPLATE", "{prefix}/{counter}/{year}"
        ),
        "invoice_issue_date_mode": os.getenv("INVOICE_ISSUE_DATE_MODE", "report_month_day"),
        "invoice_issue_day_of_month": os.getenv("INVOICE_ISSUE_DAY_OF_MONTH", "26"),
        "invoice_sale_date_mode": os.getenv("INVOICE_SALE_DATE_MODE", "issue_date"),
    }


def generate_invoice_number(month: int, year: int) -> str:
    settings = load_invoice_settings_from_env()
    prefix = settings.get("invoice_number_prefix", "FV") or "FV"
    counter = int(settings.get("invoice_number_counter", "1") or "1")
    template = settings.get("invoice_number_template", "{prefix}/{counter}/{year}")
    values = {
        "prefix": prefix,
        "counter": counter,
        "counter_padded": f"{counter:03d}",
        "month": month,
        "month_padded": f"{month:02d}",
        "year": year,
    }
    try:
        return template.format(**values)
    except (KeyError, ValueError) as exc:
        logger.warning("Invalid INVOICE_NUMBER_TEMPLATE %r: %s", template, exc)
        return f"{prefix}/{counter}/{year}"


def _resolve_issue_date(month: int, year: int, settings: Dict[str, str]) -> datetime:
    mode = (settings.get("invoice_issue_date_mode") or "report_month_day").strip().lower()
    if mode == "today":
        return datetime.now()

    last_day = monthrange(year, month)[1]
    raw_day = settings.get("invoice_issue_day_of_month", "26") or "26"
    try:
        issue_day = int(raw_day)
    except ValueError:
        logger.warning("Invalid INVOICE_ISSUE_DAY_OF_MONTH %r, falling back to 26", raw_day)
        issue_day = 26

    issue_day = min(max(issue_day, 1), last_day)
    return datetime(year, month, issue_day)


def _resolve_sale_date(issue_date: datetime, month: int, year: int, settings: Dict[str, str]) -> datetime:
    mode = (settings.get("invoice_sale_date_mode") or "issue_date").strip().lower()
    if mode == "month_end":
        return datetime(year, month, monthrange(year, month)[1])
    return issue_date


def increment_invoice_counter() -> None:
    from model import Setting, db

    setting = Setting.query.filter_by(key="invoice_number_counter").first()
    if setting:
        current = int(setting.value)
        setting.value = str(current + 1)
        db.session.commit()


def create_invoice_from_monthly_report(
    hours: float,
    month: int,
    year: int,
    trainer_name: Optional[str] = None,
) -> InvoiceData:
    settings = load_invoice_settings_from_env()
    invoice = InvoiceData()

    invoice.issuer_name = settings["invoice_issuer_name"]
    invoice.issuer_nip = settings["invoice_issuer_nip"]
    invoice.issuer_address = settings["invoice_issuer_address"]
    invoice.issuer_postal = settings["invoice_issuer_postal"]
    invoice.issuer_city = settings["invoice_issuer_city"]
    invoice.issuer_country = settings["invoice_issuer_country"]
    invoice.issuer_email = settings["invoice_issuer_email"]
    invoice.issuer_phone = settings["invoice_issuer_phone"]
    invoice.issuer_bank_account = settings["invoice_issuer_bank_account"]
    invoice.issuer_bank_name = settings["invoice_issuer_bank_name"]

    invoice.recipient_name = settings["invoice_recipient_name"]
    invoice.recipient_nip = settings["invoice_recipient_nip"]
    invoice.recipient_address = settings["invoice_recipient_address"]
    invoice.recipient_postal = settings["invoice_recipient_postal"]
    invoice.recipient_city = settings["invoice_recipient_city"]
    invoice.recipient_country = settings["invoice_recipient_country"]

    invoice.invoice_number = generate_invoice_number(month, year)
    invoice.issue_date = _resolve_issue_date(month, year, settings)
    invoice.sale_date = _resolve_sale_date(invoice.issue_date, month, year, settings)
    invoice.payment_deadline = invoice.issue_date + timedelta(
        days=int(settings["invoice_payment_deadline_days"] or "14")
    )
    invoice.payment_method = settings["invoice_payment_method"]
    invoice.issue_place = settings["invoice_issue_place"]

    base_service_name = settings["invoice_service_name"]
    service_suffix = f"{MONTH_NAMES[month]} {year}"
    trainer_suffix = f" ({trainer_name})" if trainer_name else ""
    invoice.service_name = f"{base_service_name} - {service_suffix}{trainer_suffix}"
    invoice.hours = Decimal(str(hours))
    invoice.hourly_rate = Decimal(settings["invoice_hourly_rate"] or "0.00")
    invoice.currency = settings["invoice_currency"] or "PLN"
    invoice.vat_rate = (settings["invoice_vat_rate"] or "zw").strip()
    invoice.vat_exemption_reason = settings["invoice_vat_exemption_reason"]
    invoice.pkwiu = settings["invoice_pkwiu"]
    invoice.payment_description = settings["invoice_payment_description"] or invoice.service_name
    invoice.calculate_amounts()
    return invoice


def generate_fa3_xml(invoice: InvoiceData) -> str:
    ET.register_namespace("", KSEF_FA3_NS)
    ET.register_namespace("xsi", XSI_NS)
    ET.register_namespace("xsd", XSD_NS)
    ET.register_namespace("etd", ETD_NS)

    root = ET.Element(f"{{{KSEF_FA3_NS}}}Faktura")

    naglowek = ET.SubElement(root, "Naglowek")
    kod_formularza = ET.SubElement(naglowek, "KodFormularza")
    kod_formularza.set("kodSystemowy", "FA (3)")
    kod_formularza.set("wersjaSchemy", "1-0E")
    kod_formularza.text = "FA"
    ET.SubElement(naglowek, "WariantFormularza").text = "3"
    ET.SubElement(naglowek, "DataWytworzeniaFa").text = invoice.issue_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    ET.SubElement(naglowek, "SystemInfo").text = "Lista Obecnosci"

    podmiot1 = ET.SubElement(root, "Podmiot1")
    dane_id_1 = ET.SubElement(podmiot1, "DaneIdentyfikacyjne")
    ET.SubElement(dane_id_1, "NIP").text = invoice.issuer_nip
    ET.SubElement(dane_id_1, "Nazwa").text = invoice.issuer_name
    adres_1 = ET.SubElement(podmiot1, "Adres")
    ET.SubElement(adres_1, "KodKraju").text = invoice.issuer_country
    ET.SubElement(adres_1, "AdresL1").text = invoice.issuer_address
    ET.SubElement(adres_1, "AdresL2").text = _address_line(invoice.issuer_postal, invoice.issuer_city)
    if invoice.issuer_email or invoice.issuer_phone:
        kontakt_1 = ET.SubElement(podmiot1, "DaneKontaktowe")
        _append_text(kontakt_1, "Email", invoice.issuer_email)
        _append_text(kontakt_1, "Telefon", invoice.issuer_phone)

    podmiot2 = ET.SubElement(root, "Podmiot2")
    dane_id_2 = ET.SubElement(podmiot2, "DaneIdentyfikacyjne")
    ET.SubElement(dane_id_2, "NIP").text = invoice.recipient_nip
    ET.SubElement(dane_id_2, "Nazwa").text = invoice.recipient_name
    adres_2 = ET.SubElement(podmiot2, "AdresKoresp")
    ET.SubElement(adres_2, "KodKraju").text = invoice.recipient_country
    ET.SubElement(adres_2, "AdresL1").text = invoice.recipient_address
    ET.SubElement(adres_2, "AdresL2").text = _address_line(invoice.recipient_postal, invoice.recipient_city)
    ET.SubElement(podmiot2, "JST").text = "2"
    ET.SubElement(podmiot2, "GV").text = "2"

    fa = ET.SubElement(root, "Fa")
    ET.SubElement(fa, "KodWaluty").text = invoice.currency
    ET.SubElement(fa, "P_1").text = invoice.issue_date.strftime("%Y-%m-%d")
    if invoice.issue_place:
        ET.SubElement(fa, "P_1M").text = invoice.issue_place
    ET.SubElement(fa, "P_2").text = invoice.invoice_number
    ET.SubElement(fa, "P_6").text = invoice.sale_date.strftime("%Y-%m-%d")
    ET.SubElement(fa, "P_15").text = _format_decimal(invoice.gross_amount)
    if not invoice.is_vat_exempt:
        ET.SubElement(fa, "P_13_1").text = _format_decimal(invoice.net_amount)
        ET.SubElement(fa, "P_14_1").text = _format_decimal(invoice.vat_amount)

    adnotacje = ET.SubElement(fa, "Adnotacje")
    ET.SubElement(adnotacje, "P_16").text = "2"
    ET.SubElement(adnotacje, "P_17").text = "2"
    ET.SubElement(adnotacje, "P_18").text = "2"
    ET.SubElement(adnotacje, "P_18A").text = "2"
    if invoice.is_vat_exempt:
        zwolnienie = ET.SubElement(adnotacje, "Zwolnienie")
        ET.SubElement(zwolnienie, "P_19").text = "1"
        ET.SubElement(zwolnienie, "P_19A").text = invoice.vat_exemption_reason
    else:
        zwolnienie = ET.SubElement(adnotacje, "Zwolnienie")
        ET.SubElement(zwolnienie, "P_19N").text = "1"
    nowe_srodki_transportu = ET.SubElement(adnotacje, "NoweSrodkiTransportu")
    ET.SubElement(nowe_srodki_transportu, "P_22N").text = "1"
    ET.SubElement(adnotacje, "P_23").text = "2"
    p_marzy = ET.SubElement(adnotacje, "PMarzy")
    ET.SubElement(p_marzy, "P_PMarzyN").text = "1"
    ET.SubElement(fa, "RodzajFaktury").text = "VAT"

    fa_wiersz = ET.SubElement(fa, "FaWiersz")
    ET.SubElement(fa_wiersz, "NrWierszaFa").text = "1"
    ET.SubElement(fa_wiersz, "UU_ID").text = str(uuid.uuid4())
    description = invoice.service_name
    if invoice.pkwiu:
        description = f"{description} (PKWiU {invoice.pkwiu})"
    ET.SubElement(fa_wiersz, "P_7").text = description
    ET.SubElement(fa_wiersz, "P_8A").text = invoice.service_unit
    ET.SubElement(fa_wiersz, "P_8B").text = _format_decimal(invoice.hours)
    ET.SubElement(fa_wiersz, "P_9A").text = _format_decimal(invoice.hourly_rate)
    ET.SubElement(fa_wiersz, "P_11").text = _format_decimal(invoice.net_amount)
    ET.SubElement(fa_wiersz, "P_12").text = "zw" if invoice.is_vat_exempt else invoice.vat_rate

    platnosc = ET.SubElement(fa, "Platnosc")
    ET.SubElement(platnosc, "FormaPlatnosci").text = invoice.payment_method

    return prettify_xml(root)


def generate_invoice_xml(invoice: InvoiceData) -> str:
    return generate_fa3_xml(invoice)


def generate_fa2_xml(invoice: InvoiceData) -> str:
    return generate_fa3_xml(invoice)


def save_invoice_xml(invoice: InvoiceData, output_path: str) -> str:
    xml_content = generate_invoice_xml(invoice)
    filename = f"faktura_{invoice.invoice_number.replace('/', '_')}.xml"
    filepath = os.path.join(output_path, filename)
    with open(filepath, "w", encoding="utf-8") as file_handle:
        file_handle.write(xml_content)
    logger.info("Invoice XML saved to %s", filepath)
    return filepath


def is_ksef_enabled() -> bool:
    enabled = os.getenv("KSEF_ENABLED", "0")
    return enabled.lower() in {"1", "true", "yes"}
