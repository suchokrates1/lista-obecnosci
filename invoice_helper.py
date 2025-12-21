"""
Helper functions for invoice generation and sending
Funkcje pomocnicze do generowania i wysyłania faktur
"""
import logging
from typing import Optional, Tuple
from datetime import datetime
from io import BytesIO
from model import Zajecia
from ksef_invoice import (
    create_invoice_from_monthly_report,
    generate_fa2_xml,
    increment_invoice_counter,
    is_ksef_enabled,
    save_invoice_xml
)
from ksef_client import send_invoice_to_ksef
from invoice_pdf import generate_invoice_pdf, save_invoice_pdf

logger = logging.getLogger(__name__)


def calculate_monthly_hours(prowadzacy_id: int, month: int, year: int) -> float:
    """
    Oblicza sumę godzin w danym miesiącu dla prowadzącego.
    
    Args:
        prowadzacy_id: ID prowadzącego
        month: Miesiąc (1-12)
        year: Rok
    
    Returns:
        float: Suma godzin
    """
    from model import db
    
    zajecia = Zajecia.query.filter(
        Zajecia.prowadzacy_id == prowadzacy_id,
        db.extract('month', Zajecia.data) == month,
        db.extract('year', Zajecia.data) == year
    ).all()
    
    total_hours = sum(z.czas_trwania or 0 for z in zajecia)
    return total_hours


def generate_and_send_invoice(
    prowadzacy_id: int,
    month: int,
    year: int,
    trainer_name: Optional[str] = None,
    save_to_disk: bool = True
) -> Tuple[bool, Optional[str], Optional[str], Optional[BytesIO]]:
    """
    Generuje fakturę za dany miesiąc i wysyła do KSeF (jeśli włączony).
    
    Args:
        prowadzacy_id: ID prowadzącego
        month: Miesiąc (1-12)
        year: Rok
        trainer_name: Imię i nazwisko prowadzącego (opcjonalne)
        save_to_disk: Czy zapisać XML faktury na dysk
    
    Returns:
        Tuple[bool, Optional[str], Optional[str], Optional[BytesIO]]: 
            (sukces, numer referencyjny KSeF/ścieżka pliku, komunikat błędu, PDF buffer)
    """
    try:
        # Oblicz liczbę godzin
        hours = calculate_monthly_hours(prowadzacy_id, month, year)
        
        if hours <= 0:
            return False, None, "No hours recorded for this month", None
        
        # Utwórz dane faktury
        invoice = create_invoice_from_monthly_report(
            hours=hours,
            month=month,
            year=year,
            trainer_name=trainer_name
        )
        
        # Generuj XML
        invoice_xml = generate_fa2_xml(invoice)
        
        # Generuj PDF
        pdf_buffer = generate_invoice_pdf(invoice)
        
        # Zapisz na dysk jeśli wymagane
        saved_path = None
        if save_to_disk:
            import os
            output_dir = os.path.join("invoices", str(year), f"{month:02d}")
            os.makedirs(output_dir, exist_ok=True)
            saved_path = save_invoice_xml(invoice, output_dir)
            # Zapisz też PDF
            save_invoice_pdf(invoice, output_dir)
        
        # Jeśli KSeF jest włączony, wyślij fakturę
        if is_ksef_enabled():
            success, ref_number, error = send_invoice_to_ksef(invoice_xml)
            
            if success:
                # Zwiększ licznik faktur
                increment_invoice_counter()
                logger.info(
                    f"Invoice generated and sent to KSeF: {invoice.invoice_number}, "
                    f"Reference: {ref_number}"
                )
                return True, ref_number, None, pdf_buffer
            else:
                logger.error(f"Failed to send invoice to KSeF: {error}")
                return False, saved_path, error, pdf_buffer
        else:
            # KSeF wyłączony - tylko generuj i zapisz
            increment_invoice_counter()
            logger.info(
                f"Invoice generated (KSeF disabled): {invoice.invoice_number}, "
                f"Saved to: {saved_path}"
            )
            return True, saved_path, "KSeF disabled - invoice saved locally", pdf_buffer
            
    except Exception as e:
        logger.exception("Error generating/sending invoice")
        return False, None, str(e), None


def generate_invoice_for_report(
    month: int,
    year: int,
    prowadzacy_id: int,
    trainer_name: Optional[str] = None
) -> Tuple[bool, str, Optional[BytesIO]]:
    """
    Generuje fakturę przy wysyłaniu raportu miesięcznego.
    Funkcja wrapper dla łatwej integracji z istniejącym kodem.
    
    Args:
        month: Miesiąc (1-12)
        year: Rok
        prowadzacy_id: ID prowadzącego
        trainer_name: Imię i nazwisko prowadzącego
    
    Returns:
        Tuple[bool, str, Optional[BytesIO]]: (sukces, komunikat, PDF buffer)
    """
    success, result, error, pdf_buffer = generate_and_send_invoice(
        prowadzacy_id=prowadzacy_id,
        month=month,
        year=year,
        trainer_name=trainer_name,
        save_to_disk=True
    )
    
    if success:
        if result and result.startswith('http'):
            # Numer referencyjny KSeF
            return True, f"Faktura wysłana do KSeF. Numer referencyjny: {result}", pdf_buffer
        elif result:
            # Ścieżka do pliku
            return True, f"Faktura wygenerowana: {result}", pdf_buffer
        else:
            return True, "Faktura wygenerowana pomyślnie", pdf_buffer
    else:
        return False, f"Błąd generowania faktury: {error}", None
