"""
PDF Invoice Generator
Generator faktur PDF dla polskich faktur VAT
"""
import os
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

from ksef_invoice import InvoiceData

# Polskie nazwy miesięcy
MONTH_NAMES_PL = {
    1: "styczeń", 2: "luty", 3: "marzec", 4: "kwiecień",
    5: "maj", 6: "czerwiec", 7: "lipiec", 8: "sierpień",
    9: "wrzesień", 10: "październik", 11: "listopad", 12: "grudzień"
}


def number_to_words_pl(amount: Decimal) -> str:
    """
    Prosta funkcja konwertująca kwotę na słownie (uproszczona wersja).
    W produkcji lepiej użyć biblioteki num2words.
    """
    try:
        from num2words import num2words
        zlote = int(amount)
        grosze = int((amount - zlote) * 100)
        
        zlote_str = num2words(zlote, lang='pl')
        grosze_str = num2words(grosze, lang='pl')
        
        return f"{zlote_str} zł {grosze_str} gr"
    except ImportError:
        # Fallback jeśli num2words nie jest zainstalowane
        return f"{amount:.2f} PLN"


def generate_invoice_pdf(invoice: InvoiceData, output: Optional[BytesIO] = None) -> BytesIO:
    """
    Generuje PDF faktury na podstawie danych InvoiceData.
    
    Args:
        invoice: Obiekt z danymi faktury
        output: Opcjonalny BytesIO buffer (jeśli None, utworzy nowy)
    
    Returns:
        BytesIO: Buffer z wygenerowanym PDF
    """
    if output is None:
        output = BytesIO()
    
    # Utwórz dokument PDF
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # Style
    styles = getSampleStyleSheet()
    
    # Niestandardowe style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#000000'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        fontName='Helvetica'
    )
    
    bold_style = ParagraphStyle(
        'CustomBold',
        parent=normal_style,
        fontName='Helvetica-Bold'
    )
    
    small_style = ParagraphStyle(
        'CustomSmall',
        parent=normal_style,
        fontSize=9,
        leading=11
    )
    
    # Elementy dokumentu
    elements = []
    
    # Tytuł - FAKTURA VAT
    title = Paragraph(f"<b>FAKTURA VAT</b><br/>Nr {invoice.invoice_number}", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.5*cm))
    
    # Tabela z danymi sprzedawcy i nabywcy
    seller_buyer_data = [
        [
            Paragraph("<b>Sprzedawca:</b>", bold_style),
            Paragraph("<b>Nabywca:</b>", bold_style)
        ],
        [
            Paragraph(f"<b>{invoice.issuer_name}</b><br/>"
                     f"NIP: {invoice.issuer_nip}<br/>"
                     f"{invoice.issuer_address}<br/>"
                     f"{invoice.issuer_postal} {invoice.issuer_city}<br/>"
                     f"Email: {invoice.issuer_email}<br/>"
                     f"Tel: {invoice.issuer_phone}", small_style),
            Paragraph(f"<b>{invoice.recipient_name}</b><br/>"
                     f"NIP: {invoice.recipient_nip}<br/>"
                     f"{invoice.recipient_address}<br/>"
                     f"{invoice.recipient_postal} {invoice.recipient_city}", small_style)
        ]
    ]
    
    seller_buyer_table = Table(seller_buyer_data, colWidths=[9*cm, 9*cm])
    seller_buyer_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(seller_buyer_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # Daty i informacje o fakturze
    info_data = [
        ["Data wystawienia:", invoice.issue_date.strftime('%Y-%m-%d')],
        ["Data sprzedaży:", invoice.sale_date.strftime('%Y-%m-%d')],
        ["Termin płatności:", invoice.payment_deadline.strftime('%Y-%m-%d')],
        ["Sposób płatności:", "Przelew" if invoice.payment_method == "1" else "Gotówka"],
    ]
    
    info_table = Table(info_data, colWidths=[5*cm, 5*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 0.7*cm))
    
    # Tabela pozycji faktury
    items_data = [
        ["Lp.", "Nazwa usługi", "Ilość", "J.m.", "Cena netto", "Wartość netto", "VAT %", "Kwota VAT", "Wartość brutto"]
    ]
    
    items_data.append([
        "1",
        invoice.service_name,
        str(invoice.hours),
        "godz.",
        f"{invoice.hourly_rate:.2f}",
        f"{invoice.net_amount:.2f}",
        f"{invoice.vat_rate}%",
        f"{invoice.vat_amount:.2f}",
        f"{invoice.gross_amount:.2f}"
    ])
    
    items_table = Table(items_data, colWidths=[1*cm, 6*cm, 1.5*cm, 1.2*cm, 2*cm, 2.2*cm, 1.5*cm, 2*cm, 2.6*cm])
    items_table.setStyle(TableStyle([
        # Nagłówek
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        
        # Zawartość
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Lp
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Liczby
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Obramowanie
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    
    elements.append(items_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # Podsumowanie
    summary_data = [
        ["Razem netto:", f"{invoice.net_amount:.2f} {invoice.currency}"],
        ["VAT:", f"{invoice.vat_amount:.2f} {invoice.currency}"],
        ["", ""],
        ["DO ZAPŁATY:", f"{invoice.gross_amount:.2f} {invoice.currency}"]
    ]
    
    summary_table = Table(summary_data, colWidths=[12*cm, 5*cm])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -2), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -2), 10),
        
        # Ostatni wiersz (DO ZAPŁATY)
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e0e0e0')),
        
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        
        # Linie
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3*cm))
    
    # Słownie
    amount_in_words = number_to_words_pl(invoice.gross_amount)
    elements.append(Paragraph(f"<b>Słownie:</b> {amount_in_words}", small_style))
    
    elements.append(Spacer(1, 1.5*cm))
    
    # Podpisy
    signatures_data = [
        ["", ""],
        [".................................", "................................."],
        ["Podpis osoby upoważnionej", "Podpis osoby upoważnionej"],
        ["do wystawienia faktury", "do odbioru faktury"]
    ]
    
    signatures_table = Table(signatures_data, colWidths=[9*cm, 9*cm])
    signatures_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 2), (-1, -1), 2),
    ]))
    
    elements.append(signatures_table)
    
    # Generuj PDF
    doc.build(elements)
    output.seek(0)
    
    return output


def save_invoice_pdf(invoice: InvoiceData, output_path: str) -> str:
    """
    Generuje i zapisuje fakturę PDF do pliku.
    
    Args:
        invoice: Dane faktury
        output_path: Ścieżka do katalogu wyjściowego
    
    Returns:
        str: Ścieżka do zapisanego pliku
    """
    pdf_buffer = generate_invoice_pdf(invoice)
    
    filename = f"faktura_{invoice.invoice_number.replace('/', '_')}.pdf"
    filepath = os.path.join(output_path, filename)
    
    with open(filepath, 'wb') as f:
        f.write(pdf_buffer.getvalue())
    
    return filepath
