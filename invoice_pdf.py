"""PDF invoice generator."""
import importlib
import os
import re
from decimal import Decimal
from io import BytesIO
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from ksef_invoice import InvoiceData

PDF_FONT_NAME = "InvoiceSans"
PDF_FONT_BOLD_NAME = "InvoiceSans-Bold"
LOGO_PATH = os.path.join(os.path.dirname(__file__), "static", "vestmedia-logo.png")


def _register_pdf_fonts() -> tuple[str, str]:
    candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ),
        (
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ),
        (
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ),
    ]

    for regular_path, bold_path in candidates:
        if not (os.path.exists(regular_path) and os.path.exists(bold_path)):
            continue
        if PDF_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(PDF_FONT_NAME, regular_path))
        if PDF_FONT_BOLD_NAME not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(PDF_FONT_BOLD_NAME, bold_path))
        return PDF_FONT_NAME, PDF_FONT_BOLD_NAME

    return "Helvetica", "Helvetica-Bold"


def number_to_words_pl(amount: Decimal) -> str:
    """
    Prosta funkcja konwertująca kwotę na słownie (uproszczona wersja).
    W produkcji lepiej użyć biblioteki num2words.
    """
    try:
        num2words = importlib.import_module("num2words").num2words
        zlote = int(amount)
        grosze = int((amount - zlote) * 100)

        zlote_str = num2words(zlote, lang='pl')
        if zlote >= 1000 and zlote_str.startswith('tysiąc'):
            zlote_str = f"jeden {zlote_str}"

        return f"{zlote_str} {grosze:02d}/100 PLN"
    except ImportError:
        # Fallback jeśli num2words nie jest zainstalowane
        return f"{amount:.2f} PLN".replace(".", ",")


def _money(value: Decimal, currency: str) -> str:
    return f"{value:.2f} {currency}"


def _format_decimal_pl(value: Decimal) -> str:
    return f"{value:.2f}".replace(".", ",")


def _format_quantity(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1"))).replace(".", ",")
    return format(normalized, "f").rstrip("0").rstrip(".").replace(".", ",")


def _display_unit(service_unit: str) -> str:
    normalized = (service_unit or "").strip().lower()
    if normalized in {"godz.", "godz", "godzina", "godziny"}:
        return "godz."
    return service_unit


def _wrap_text_two_lines(text: str, target_first_line: int = 58) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if len(normalized) <= target_first_line:
        return normalized

    midpoint = max(1, len(normalized) // 2)
    split_at = normalized.rfind(" ", 0, midpoint)
    forward_split = normalized.find(" ", midpoint)
    if split_at == -1 or (
        forward_split != -1
        and abs(forward_split - midpoint) < abs(split_at - midpoint)
    ):
        split_at = forward_split
    if split_at == -1:
        return normalized

    first_line = normalized[:split_at].strip()
    second_line = normalized[split_at + 1 :].strip()
    return f"{first_line.replace(' ', '&nbsp;')}<br/>{second_line.replace(' ', '&nbsp;')}"


def _build_logo(max_width_cm: float = 4.2, max_height_cm: float = 1.6) -> Optional[Image]:
    if not os.path.exists(LOGO_PATH):
        return None

    logo = Image(LOGO_PATH)
    aspect_ratio = logo.imageWidth / float(logo.imageHeight)
    target_width = max_width_cm * cm
    target_height = target_width / aspect_ratio

    if target_height > max_height_cm * cm:
        target_height = max_height_cm * cm
        target_width = target_height * aspect_ratio

    logo.drawWidth = target_width
    logo.drawHeight = target_height
    logo.hAlign = "LEFT"
    return logo


def generate_invoice_pdf(invoice: InvoiceData, output: Optional[BytesIO] = None) -> BytesIO:
    if output is None:
        output = BytesIO()

    regular_font, bold_font = _register_pdf_fonts()

    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    styles = getSampleStyleSheet()
    normal_style = ParagraphStyle(
        'InvoiceNormal',
        parent=styles['Normal'],
        fontSize=10,
        leading=13,
        fontName=regular_font
    )

    bold_style = ParagraphStyle(
        'InvoiceBold',
        parent=normal_style,
        fontName=bold_font
    )

    small_style = ParagraphStyle(
        'InvoiceSmall',
        parent=normal_style,
        fontSize=9,
        leading=11
    )

    label_style = ParagraphStyle(
        'InvoiceLabel',
        parent=small_style,
        fontName=bold_font,
        leading=12,
    )

    value_style = ParagraphStyle(
        'InvoiceValue',
        parent=small_style,
        leading=12,
    )

    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=18,
        textColor=colors.black,
        alignment=TA_RIGHT,
        fontName=bold_font,
        spaceAfter=0,
    )

    party_header_style = ParagraphStyle(
        'InvoicePartyHeader',
        parent=small_style,
        fontName=bold_font,
        fontSize=10,
        leading=12,
    )

    item_header_style = ParagraphStyle(
        'InvoiceItemHeader',
        parent=small_style,
        fontName=bold_font,
        fontSize=7.4,
        leading=8.4,
        alignment=TA_RIGHT,
    )

    item_header_center_style = ParagraphStyle(
        'InvoiceItemHeaderCenter',
        parent=item_header_style,
        alignment=1,
    )

    item_text_style = ParagraphStyle(
        'InvoiceItemText',
        parent=small_style,
        fontSize=7.4,
        leading=8.4,
    )

    item_number_style = ParagraphStyle(
        'InvoiceItemNumber',
        parent=item_text_style,
        alignment=TA_RIGHT,
    )

    elements = []
    logo = _build_logo()
    meta_rows = [
        [Paragraph("Data wystawienia:", label_style), Paragraph(invoice.issue_date.strftime('%Y-%m-%d'), value_style)],
        [Paragraph("Data wydania towaru lub<br/>wykonania usługi:", label_style), Paragraph(invoice.sale_date.strftime('%Y-%m-%d'), value_style)],
    ]
    meta_table = Table(meta_rows, colWidths=[3.6 * cm, 2.4 * cm])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    left_header_cell = meta_table
    if logo is not None:
        left_header_cell = Table(
            [[logo], [Spacer(1, 0.18 * cm)], [meta_table]],
            colWidths=[4.4 * cm],
        )
        left_header_cell.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))

    header_table = Table(
        [[left_header_cell, Paragraph(f"Faktura nr {invoice.invoice_number}", title_style)]],
        colWidths=[7.1 * cm, 9.9 * cm],
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.45 * cm))

    seller_lines = [
        invoice.issuer_name,
        invoice.issuer_address,
        f"{invoice.issuer_postal} {invoice.issuer_city}",
        f"NIP: {invoice.issuer_nip}",
    ]
    buyer_lines = [
        invoice.recipient_name,
        invoice.recipient_address,
        f"{invoice.recipient_postal} {invoice.recipient_city}",
        f"NIP: {invoice.recipient_nip}",
    ]

    parties_table = Table(
        [
            [Paragraph("Wystawca", party_header_style), Paragraph("Nabywca", party_header_style)],
            [Paragraph("<br/>".join(seller_lines), small_style), Paragraph("<br/>".join(buyer_lines), small_style)],
        ],
        colWidths=[8.5 * cm, 8.5 * cm],
    )
    parties_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(parties_table)
    elements.append(Spacer(1, 0.35 * cm))

    vat_label = "zw" if invoice.is_vat_exempt else f"{invoice.vat_rate}%"
    item_headers = [
        Paragraph("Lp.", item_header_center_style),
        Paragraph("Pozycja", item_header_center_style),
        Paragraph("Cena netto", item_header_center_style),
        Paragraph("Ilość", item_header_center_style),
        Paragraph("Jedn.", item_header_center_style),
        Paragraph("Wartość netto", item_header_center_style),
        Paragraph("VAT%", item_header_center_style),
        Paragraph("Kwota VAT", item_header_center_style),
        Paragraph("Wartość brutto", item_header_center_style),
    ]
    item_row = [
        Paragraph("1.", item_number_style),
        Paragraph(_wrap_text_two_lines(invoice.service_name), item_text_style),
        Paragraph(_format_decimal_pl(invoice.hourly_rate), item_number_style),
        Paragraph(_format_quantity(invoice.hours), item_number_style),
        Paragraph(_display_unit(invoice.service_unit), item_text_style),
        Paragraph(_format_decimal_pl(invoice.net_amount), item_number_style),
        Paragraph(vat_label, item_number_style),
        Paragraph(_format_decimal_pl(invoice.vat_amount), item_number_style),
        Paragraph(_format_decimal_pl(invoice.gross_amount), item_number_style),
    ]
    summary_row = [
        Paragraph("", item_text_style),
        Paragraph("Razem", item_text_style),
        Paragraph(_format_decimal_pl(invoice.net_amount), item_number_style),
        Paragraph("-", item_number_style),
        Paragraph("-", item_number_style),
        Paragraph("-", item_number_style),
        Paragraph("", item_text_style),
        Paragraph(_format_decimal_pl(invoice.vat_amount), item_number_style),
        Paragraph(_format_decimal_pl(invoice.gross_amount), item_number_style),
    ]
    vat_summary_row = [
        Paragraph("", item_text_style),
        Paragraph("Rozliczenie VAT (PLN)", item_text_style),
        Paragraph(_format_decimal_pl(invoice.net_amount), item_number_style),
        Paragraph("", item_text_style),
        Paragraph("", item_text_style),
        Paragraph("", item_text_style),
        Paragraph(vat_label, item_number_style),
        Paragraph(_format_decimal_pl(invoice.vat_amount), item_number_style),
        Paragraph(_format_decimal_pl(invoice.gross_amount), item_number_style),
    ]

    items_table = Table(
        [item_headers, item_row, summary_row, vat_summary_row],
        colWidths=[0.7 * cm, 7.4 * cm, 1.6 * cm, 1.0 * cm, 1.1 * cm, 1.5 * cm, 0.8 * cm, 1.2 * cm, 1.7 * cm],
        repeatRows=1,
    )
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#efefef')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), bold_font),
        ('FONTSIZE', (0, 0), (-1, 0), 7.4),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('TOPPADDING', (0, 0), (-1, 0), 5),
        ('FONTNAME', (0, 1), (-1, -1), regular_font),
        ('FONTSIZE', (0, 1), (-1, -1), 7.4),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#777777')),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('FONTNAME', (1, 2), (1, 3), bold_font),
        ('FONTNAME', (0, 2), (-1, 2), bold_font),
        ('ALIGN', (1, 3), (1, 3), 'LEFT'),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.3 * cm))

    info_rows = [[Paragraph("Dodatkowe informacje", party_header_style), ""]]
    if invoice.vat_exemption_reason:
        info_rows.append([Paragraph(invoice.vat_exemption_reason, small_style), ""])
    if invoice.pkwiu:
        info_rows.append([Paragraph(f"PKWiU: {invoice.pkwiu}", small_style), ""])
    info_table = Table(info_rows, colWidths=[9.4 * cm, 7.6 * cm])
    info_table.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('SPAN', (0, 1), (1, 1)),
        ('SPAN', (0, 2), (1, 2)),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.25 * cm))

    amount_in_words = number_to_words_pl(invoice.gross_amount)
    payment_rows = [
        [Paragraph("Do zapłaty", label_style), Paragraph(f"{_format_decimal_pl(invoice.gross_amount)} {invoice.currency}", ParagraphStyle('DueValue', parent=label_style, alignment=TA_RIGHT, fontSize=12))],
        [Paragraph("Słownie", label_style), Paragraph(amount_in_words, ParagraphStyle('WordsValue', parent=small_style, alignment=TA_RIGHT))],
        [Paragraph("Sposób zapłaty", label_style), Paragraph(invoice.payment_method_label.lower(), ParagraphStyle('PayValue', parent=small_style, alignment=TA_RIGHT))],
        [Paragraph("Termin", label_style), Paragraph(invoice.payment_deadline.strftime('%Y-%m-%d'), ParagraphStyle('TermValue', parent=small_style, alignment=TA_RIGHT))],
    ]
    if invoice.issuer_bank_account:
        payment_rows.append([
            Paragraph("Rachunek", label_style),
            Paragraph(invoice.issuer_bank_account, ParagraphStyle('AccountValue', parent=small_style, alignment=TA_RIGHT)),
        ])

    payment_table = Table(payment_rows, colWidths=[4.2 * cm, 12.8 * cm])
    payment_table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('FONTNAME', (0, 0), (0, -1), bold_font),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEABOVE', (0, 0), (-1, 0), 0.5, colors.HexColor('#999999')),
    ]))
    elements.append(payment_table)

    doc.build(elements)
    output.seek(0)
    return output


def save_invoice_pdf(invoice: InvoiceData, output_path: str) -> str:
    pdf_buffer = generate_invoice_pdf(invoice)
    filename = f"faktura_{invoice.invoice_number.replace('/', '_')}.pdf"
    filepath = os.path.join(output_path, filename)
    with open(filepath, 'wb') as f:
        f.write(pdf_buffer.getvalue())
    return filepath
