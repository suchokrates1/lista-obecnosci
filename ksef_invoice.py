"""
KSeF Invoice Generator Module
Generuje faktury w formacie FA(2) zgodnym z Krajowym Systemem e-Faktur
"""
from datetime import datetime, timedelta
from decimal import Decimal
import os
import logging
from typing import Dict, Optional
import xml.etree.ElementTree as ET
from xml.dom import minidom

logger = logging.getLogger(__name__)

# Namespace dla struktury FA(2)
KSEF_NS = "http://crd.gov.pl/wzor/2023/06/29/12648/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

def prettify_xml(elem: ET.Element) -> str:
    """Zwraca sformatowany XML string z odpowiednimi wcięciami."""
    rough_string = ET.tostring(elem, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')


class InvoiceData:
    """Klasa przechowująca dane faktury."""
    
    def __init__(self):
        # Dane wystawiającego
        self.issuer_name: str = ""
        self.issuer_nip: str = ""
        self.issuer_address: str = ""
        self.issuer_postal: str = ""
        self.issuer_city: str = ""
        self.issuer_country: str = "PL"
        self.issuer_email: str = ""
        self.issuer_phone: str = ""
        
        # Dane nabywcy
        self.recipient_name: str = ""
        self.recipient_nip: str = ""
        self.recipient_address: str = ""
        self.recipient_postal: str = ""
        self.recipient_city: str = ""
        self.recipient_country: str = "PL"
        
        # Dane faktury
        self.invoice_number: str = ""
        self.issue_date: datetime = datetime.now()
        self.sale_date: datetime = datetime.now()
        self.payment_deadline: datetime = datetime.now() + timedelta(days=14)
        self.payment_method: str = "1"  # 1 = przelew
        
        # Dane usługi
        self.service_name: str = ""
        self.hours: Decimal = Decimal("0")
        self.hourly_rate: Decimal = Decimal("0")
        self.currency: str = "PLN"
        self.vat_rate: int = 23
        
        # Kwoty (wyliczane automatycznie)
        self.net_amount: Decimal = Decimal("0")
        self.vat_amount: Decimal = Decimal("0")
        self.gross_amount: Decimal = Decimal("0")
    
    def calculate_amounts(self):
        """Wylicza kwoty netto, VAT i brutto."""
        self.net_amount = self.hours * self.hourly_rate
        self.net_amount = self.net_amount.quantize(Decimal("0.01"))
        
        self.vat_amount = (self.net_amount * Decimal(self.vat_rate) / Decimal(100))
        self.vat_amount = self.vat_amount.quantize(Decimal("0.01"))
        
        self.gross_amount = self.net_amount + self.vat_amount


def load_invoice_settings_from_env() -> Dict[str, str]:
    """Ładuje ustawienia faktur ze zmiennych środowiskowych."""
    return {
        'ksef_enabled': os.getenv('KSEF_ENABLED', '0'),
        'ksef_environment': os.getenv('KSEF_ENVIRONMENT', 'test'),
        'ksef_nip': os.getenv('KSEF_NIP', ''),
        'ksef_token': os.getenv('KSEF_TOKEN', ''),
        
        'invoice_issuer_name': os.getenv('INVOICE_ISSUER_NAME', ''),
        'invoice_issuer_nip': os.getenv('INVOICE_ISSUER_NIP', ''),
        'invoice_issuer_address': os.getenv('INVOICE_ISSUER_ADDRESS', ''),
        'invoice_issuer_postal': os.getenv('INVOICE_ISSUER_POSTAL', ''),
        'invoice_issuer_city': os.getenv('INVOICE_ISSUER_CITY', ''),
        'invoice_issuer_country': os.getenv('INVOICE_ISSUER_COUNTRY', 'PL'),
        'invoice_issuer_email': os.getenv('INVOICE_ISSUER_EMAIL', ''),
        'invoice_issuer_phone': os.getenv('INVOICE_ISSUER_PHONE', ''),
        
        'invoice_recipient_name': os.getenv('INVOICE_RECIPIENT_NAME', ''),
        'invoice_recipient_nip': os.getenv('INVOICE_RECIPIENT_NIP', ''),
        'invoice_recipient_address': os.getenv('INVOICE_RECIPIENT_ADDRESS', ''),
        'invoice_recipient_postal': os.getenv('INVOICE_RECIPIENT_POSTAL', ''),
        'invoice_recipient_city': os.getenv('INVOICE_RECIPIENT_CITY', ''),
        'invoice_recipient_country': os.getenv('INVOICE_RECIPIENT_COUNTRY', 'PL'),
        
        'invoice_service_name': os.getenv('INVOICE_SERVICE_NAME', ''),
        'invoice_hourly_rate': os.getenv('INVOICE_HOURLY_RATE', '0.00'),
        'invoice_currency': os.getenv('INVOICE_CURRENCY', 'PLN'),
        'invoice_vat_rate': os.getenv('INVOICE_VAT_RATE', '23'),
        'invoice_payment_deadline_days': os.getenv('INVOICE_PAYMENT_DEADLINE_DAYS', '14'),
        'invoice_payment_method': os.getenv('INVOICE_PAYMENT_METHOD', '1'),
        'invoice_number_prefix': os.getenv('INVOICE_NUMBER_PREFIX', 'FV'),
        'invoice_number_counter': os.getenv('INVOICE_NUMBER_COUNTER', '1'),
    }


def generate_invoice_number(month: int, year: int) -> str:
    """Generuje numer faktury na podstawie miesiąca i roku."""
    settings = load_invoice_settings_from_env()
    prefix = settings.get('invoice_number_prefix', 'FV')
    counter = int(settings.get('invoice_number_counter', '1'))
    
    # Format: FV/001/MM/YYYY
    return f"{prefix}/{counter:03d}/{month:02d}/{year}"


def increment_invoice_counter():
    """Zwiększa licznik faktur w bazie danych."""
    from model import db, Setting
    
    setting = Setting.query.filter_by(key='invoice_number_counter').first()
    if setting:
        current = int(setting.value)
        setting.value = str(current + 1)
        db.session.commit()


def create_invoice_from_monthly_report(
    hours: float,
    month: int,
    year: int,
    trainer_name: Optional[str] = None
) -> InvoiceData:
    """
    Tworzy dane faktury na podstawie raportu miesięcznego.
    
    Args:
        hours: Liczba godzin w miesiącu
        month: Miesiąc (1-12)
        year: Rok
        trainer_name: Opcjonalnie imię i nazwisko trenera
    
    Returns:
        InvoiceData: Obiekt z danymi faktury
    """
    settings = load_invoice_settings_from_env()
    
    invoice = InvoiceData()
    
    # Dane wystawiającego
    invoice.issuer_name = settings['invoice_issuer_name']
    invoice.issuer_nip = settings['invoice_issuer_nip']
    invoice.issuer_address = settings['invoice_issuer_address']
    invoice.issuer_postal = settings['invoice_issuer_postal']
    invoice.issuer_city = settings['invoice_issuer_city']
    invoice.issuer_country = settings['invoice_issuer_country']
    invoice.issuer_email = settings['invoice_issuer_email']
    invoice.issuer_phone = settings['invoice_issuer_phone']
    
    # Dane nabywcy
    invoice.recipient_name = settings['invoice_recipient_name']
    invoice.recipient_nip = settings['invoice_recipient_nip']
    invoice.recipient_address = settings['invoice_recipient_address']
    invoice.recipient_postal = settings['invoice_recipient_postal']
    invoice.recipient_city = settings['invoice_recipient_city']
    invoice.recipient_country = settings['invoice_recipient_country']
    
    # Numer faktury
    invoice.invoice_number = generate_invoice_number(month, year)
    
    # Daty
    invoice.issue_date = datetime.now()
    # Data sprzedaży = ostatni dzień miesiąca
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    invoice.sale_date = next_month - timedelta(days=1)
    
    # Termin płatności
    deadline_days = int(settings['invoice_payment_deadline_days'])
    invoice.payment_deadline = invoice.issue_date + timedelta(days=deadline_days)
    invoice.payment_method = settings['invoice_payment_method']
    
    # Usługa
    service_name = settings['invoice_service_name']
    # Dodaj miesiąc i rok do nazwy usługi
    month_names = {
        1: "styczeń", 2: "luty", 3: "marzec", 4: "kwiecień",
        5: "maj", 6: "czerwiec", 7: "lipiec", 8: "sierpień",
        9: "wrzesień", 10: "październik", 11: "listopad", 12: "grudzień"
    }
    invoice.service_name = f"{service_name} - {month_names[month]} {year}"
    
    invoice.hours = Decimal(str(hours))
    invoice.hourly_rate = Decimal(settings['invoice_hourly_rate'])
    invoice.currency = settings['invoice_currency']
    invoice.vat_rate = int(settings['invoice_vat_rate'])
    
    # Wylicz kwoty
    invoice.calculate_amounts()
    
    return invoice


def generate_fa2_xml(invoice: InvoiceData) -> str:
    """
    Generuje XML faktury w formacie FA(2) zgodnym z KSeF.
    
    Args:
        invoice: Dane faktury
    
    Returns:
        str: XML faktury
    """
    # Główny element
    ET.register_namespace('', KSEF_NS)
    ET.register_namespace('xsi', XSI_NS)
    
    root = ET.Element('{%s}Faktura' % KSEF_NS)
    root.set('{%s}schemaLocation' % XSI_NS, 
             'http://crd.gov.pl/wzor/2023/06/29/12648/ http://crd.gov.pl/wzor/2023/06/29/12648/schemat.xsd')
    
    # Naglowek
    naglowek = ET.SubElement(root, 'Naglowek')
    ET.SubElement(naglowek, 'KodFormularza').text = 'FA(2)'
    ET.SubElement(naglowek, 'WariantFormularza').text = '2'
    ET.SubElement(naglowek, 'DataWytworzeniaFa').text = datetime.now().strftime('%Y-%m-%d')
    ET.SubElement(naglowek, 'SystemInfo').text = 'Lista Obecności v1.0'
    
    # Podmiot1 (Sprzedawca/Wystawiający)
    podmiot1 = ET.SubElement(root, 'Podmiot1')
    
    # Dane identyfikacyjne
    dane_id = ET.SubElement(podmiot1, 'DaneIdentyfikacyjne')
    ET.SubElement(dane_id, 'NIP').text = invoice.issuer_nip
    ET.SubElement(dane_id, 'Nazwa').text = invoice.issuer_name
    
    # Adres
    adres = ET.SubElement(podmiot1, 'Adres')
    ET.SubElement(adres, 'KodKraju').text = invoice.issuer_country
    ET.SubElement(adres, 'AdresL1').text = invoice.issuer_address
    ET.SubElement(adres, 'AdresL2').text = f"{invoice.issuer_postal} {invoice.issuer_city}"
    
    # Dane kontaktowe (opcjonalne)
    if invoice.issuer_email or invoice.issuer_phone:
        dane_kontaktowe = ET.SubElement(podmiot1, 'DaneKontaktowe')
        if invoice.issuer_email:
            ET.SubElement(dane_kontaktowe, 'Email').text = invoice.issuer_email
        if invoice.issuer_phone:
            ET.SubElement(dane_kontaktowe, 'Telefon').text = invoice.issuer_phone
    
    # Podmiot2 (Nabywca)
    podmiot2 = ET.SubElement(root, 'Podmiot2')
    
    dane_id2 = ET.SubElement(podmiot2, 'DaneIdentyfikacyjne')
    ET.SubElement(dane_id2, 'NIP').text = invoice.recipient_nip
    ET.SubElement(dane_id2, 'Nazwa').text = invoice.recipient_name
    
    adres2 = ET.SubElement(podmiot2, 'Adres')
    ET.SubElement(adres2, 'KodKraju').text = invoice.recipient_country
    ET.SubElement(adres2, 'AdresL1').text = invoice.recipient_address
    ET.SubElement(adres2, 'AdresL2').text = f"{invoice.recipient_postal} {invoice.recipient_city}"
    
    # Faktura
    fa = ET.SubElement(root, 'Fa')
    ET.SubElement(fa, 'KodWaluty').text = invoice.currency
    ET.SubElement(fa, 'P_1').text = invoice.issue_date.strftime('%Y-%m-%d')
    ET.SubElement(fa, 'P_2').text = invoice.invoice_number
    ET.SubElement(fa, 'P_6').text = invoice.sale_date.strftime('%Y-%m-%d')
    
    # Sposób zapłaty
    ET.SubElement(fa, 'P_16').text = invoice.payment_method
    ET.SubElement(fa, 'P_17').text = invoice.payment_deadline.strftime('%Y-%m-%d')
    
    # Kwoty
    ET.SubElement(fa, 'P_13_1').text = str(invoice.net_amount)
    ET.SubElement(fa, 'P_14_1').text = str(invoice.vat_amount)
    ET.SubElement(fa, 'P_15').text = str(invoice.gross_amount)
    
    # Tabela pozycji faktury
    fa_wiersze = ET.SubElement(fa, 'FaWiersze')
    fa_wiersz = ET.SubElement(fa_wiersze, 'FaWiersz')
    
    ET.SubElement(fa_wiersz, 'NrWierszaFa').text = '1'
    ET.SubElement(fa_wiersz, 'P_7').text = invoice.service_name
    ET.SubElement(fa_wiersz, 'P_8A').text = 'szt'  # Jednostka miary
    ET.SubElement(fa_wiersz, 'P_8B').text = str(invoice.hours)  # Ilość
    ET.SubElement(fa_wiersz, 'P_9A').text = str(invoice.hourly_rate)  # Cena jednostkowa netto
    ET.SubElement(fa_wiersz, 'P_11').text = str(invoice.net_amount)  # Wartość netto
    ET.SubElement(fa_wiersz, 'P_12').text = str(invoice.vat_rate)  # Stawka VAT
    
    return prettify_xml(root)


def save_invoice_xml(invoice: InvoiceData, output_path: str) -> str:
    """
    Generuje i zapisuje fakturę XML do pliku.
    
    Args:
        invoice: Dane faktury
        output_path: Ścieżka do katalogu wyjściowego
    
    Returns:
        str: Ścieżka do zapisanego pliku
    """
    xml_content = generate_fa2_xml(invoice)
    
    filename = f"faktura_{invoice.invoice_number.replace('/', '_')}.xml"
    filepath = os.path.join(output_path, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(xml_content)
    
    logger.info(f"Invoice XML saved to {filepath}")
    return filepath


def is_ksef_enabled() -> bool:
    """Sprawdza czy KSeF jest włączony."""
    enabled = os.getenv('KSEF_ENABLED', '0')
    return enabled.lower() in ('1', 'true', 'yes')
