from io import BytesIO
from typing import Any

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from services.qrcode_service import build_animal_public_url


COLOR_PINK = colors.HexColor("#EA526F")
COLOR_PITCH_BLACK = colors.HexColor("#070600")
COLOR_FERN = colors.HexColor("#4A7856")
COLOR_MUTED = colors.HexColor("#575666")
COLOR_BORDER = colors.HexColor("#D2D2E4")


def _draw_vector_qr(
    pdf: canvas.Canvas,
    url: str,
    x_pt: float,
    y_pt: float,
    size_pt: float,
) -> None:
    """Desenha um QR Code vetorial de alta nitidez (nível Q) exatamente nas dimensões informadas."""
    widget = qr.QrCodeWidget(
        value=url,
        barLevel="Q",
        barFillColor=COLOR_PITCH_BLACK,
        barBorder=1,
    )
    bounds = widget.getBounds()
    w = bounds[2] - bounds[0]
    h = bounds[3] - bounds[1]
    drawing = Drawing(
        size_pt,
        size_pt,
        transform=[size_pt / w, 0, 0, size_pt / h, 0, 0],
    )
    drawing.add(widget)
    renderPDF.draw(drawing, pdf, x_pt, y_pt)


def _fit_font_size(text: str, font_name: str, desired_pt: float, max_width_pt: float, min_pt: float = 5.5) -> float:
    """Garante que o texto nunca ultrapasse a largura útil da etiqueta (sem cortes ou sobreposição)."""
    size = desired_pt
    while size > min_pt and stringWidth(text, font_name, size) > max_width_pt:
        size -= 0.5
    return max(min_pt, size)


def _truncate_to_width(text: str, font_name: str, font_pt: float, max_width_pt: float) -> str:
    if stringWidth(text, font_name, font_pt) <= max_width_pt:
        return text
    trimmed = text
    while len(trimmed) > 3 and stringWidth(trimmed + "…", font_name, font_pt) > max_width_pt:
        trimmed = trimmed[:-1]
    return trimmed + "…"


def _draw_single_label(
    pdf: canvas.Canvas,
    unit: dict[str, Any],
    layout: dict[str, Any],
    x_mm: float,
    y_bottom_mm: float,
    base_url: str,
) -> None:
    label_w_pt = float(layout["label_width_mm"]) * mm
    label_h_pt = float(layout["label_height_mm"]) * mm
    qr_pt = float(layout["qr_size_mm"]) * mm
    base_font_pt = float(layout["font_size_pt"])
    is_horiz = bool(layout.get("is_horizontal_card", True))

    x0 = x_mm * mm
    y0 = y_bottom_mm * mm

    tag_number = str(unit.get("tag_number") or "")
    custom_text = str(unit.get("custom_text") or "").strip()
    target_url = unit.get("public_url") or build_animal_public_url(str(unit["qr_token"]), base_url)

    pdf.saveState()

    # Clipping estrito dentro dos limites da etiqueta para evitar qualquer invasão de etiquetas vizinhas
    clip_path = pdf.beginPath()
    clip_path.rect(x0, y0, label_w_pt, label_h_pt)
    pdf.clipPath(clip_path, stroke=0, fill=0)

    # Guia de corte pontilhada opcional
    if layout.get("show_border", True):
        pdf.setStrokeColor(COLOR_BORDER)
        pdf.setLineWidth(0.5)
        pdf.setDash(2, 2)
        pdf.roundRect(x0 + 0.3, y0 + 0.3, label_w_pt - 0.6, label_h_pt - 0.6, 2.5 * mm, stroke=1, fill=0)
        pdf.setDash()

    pad_pt = 1.6 * mm

    if is_horiz:
        # Layout Horizontal: QR Code à esquerda + Identidade Animora e Numeração à direita
        qr_x = x0 + pad_pt
        qr_y = y0 + (label_h_pt - qr_pt) / 2.0
        _draw_vector_qr(pdf, target_url, qr_x, qr_y, qr_pt)

        text_x = qr_x + qr_pt + (1.8 * mm)
        max_text_w = max(8 * mm, (x0 + label_w_pt - pad_pt) - text_x)

        brand_font_pt = min(max(5.5, base_font_pt * 0.56), 8.5)
        tag_font_pt = _fit_font_size(tag_number, "Helvetica-Bold", base_font_pt, max_text_w, min_pt=6.5)
        custom_font_pt = min(max(5.5, base_font_pt * 0.62), 8.5)

        center_y = y0 + (label_h_pt / 2.0)
        total_block_h = brand_font_pt + 3 + tag_font_pt + (custom_font_pt + 3 if custom_text else 0)
        cursor_top = center_y + (total_block_h / 2.0)

        # Marca Animora em destaque Bubblegum Pink
        pdf.setFillColor(COLOR_PINK)
        pdf.rect(text_x, cursor_top - brand_font_pt, 1.8, brand_font_pt, stroke=0, fill=1)
        pdf.setFont("Helvetica-Bold", brand_font_pt)
        pdf.drawString(text_x + 3.5, cursor_top - brand_font_pt + 0.8, "ANIMORA")

        # Numeração principal da etiqueta
        cursor_tag_y = cursor_top - brand_font_pt - 3.5 - tag_font_pt
        pdf.setFillColor(COLOR_PITCH_BLACK)
        pdf.setFont("Helvetica-Bold", tag_font_pt)
        pdf.drawString(text_x, cursor_tag_y + 1.0, tag_number)

        # Linha decorativa
        pdf.setStrokeColor(COLOR_PINK)
        pdf.setLineWidth(0.7)
        line_w = min(max_text_w * 0.85, max(18.0, stringWidth(tag_number, "Helvetica-Bold", tag_font_pt)))
        pdf.line(text_x, cursor_tag_y - 1.5, text_x + line_w, cursor_tag_y - 1.5)

        # Texto personalizado opcional
        if custom_text:
            safe_custom = _truncate_to_width(custom_text, "Helvetica", custom_font_pt, max_text_w)
            pdf.setFillColor(COLOR_FERN)
            pdf.setFont("Helvetica", custom_font_pt)
            pdf.drawString(text_x, cursor_tag_y - 3.5 - custom_font_pt, safe_custom)
    else:
        # Layout Vertical: Marca no topo, QR Code centralizado, Numeração e Texto abaixo
        max_text_w = max(10 * mm, label_w_pt - (2 * pad_pt))
        center_x = x0 + (label_w_pt / 2.0)

        brand_font_pt = min(max(5.5, base_font_pt * 0.55), 8.5)
        tag_font_pt = _fit_font_size(tag_number, "Helvetica-Bold", base_font_pt, max_text_w, min_pt=6.5)
        custom_font_pt = min(max(5.5, base_font_pt * 0.6), 8.0)

        top_y = y0 + label_h_pt - pad_pt - brand_font_pt
        pdf.setFillColor(COLOR_PINK)
        pdf.setFont("Helvetica-Bold", brand_font_pt)
        pdf.drawCentredString(center_x, top_y, "ANIMORA")

        qr_x = center_x - (qr_pt / 2.0)
        qr_y = top_y - (1.0 * mm) - qr_pt
        _draw_vector_qr(pdf, target_url, qr_x, qr_y, qr_pt)

        tag_y = qr_y - tag_font_pt - 1.5
        pdf.setFillColor(COLOR_PITCH_BLACK)
        pdf.setFont("Helvetica-Bold", tag_font_pt)
        pdf.drawCentredString(center_x, max(y0 + pad_pt, tag_y), tag_number)

        if custom_text and (tag_y - custom_font_pt - 2) >= (y0 + 1.5):
            safe_custom = _truncate_to_width(custom_text, "Helvetica", custom_font_pt, max_text_w)
            pdf.setFillColor(COLOR_FERN)
            pdf.setFont("Helvetica", custom_font_pt)
            pdf.drawCentredString(center_x, tag_y - custom_font_pt - 2.0, safe_custom)

    pdf.restoreState()


def generate_labels_pdf_bytes(
    units: list[dict[str, Any]],
    layout: dict[str, Any],
    base_url: str,
    document_title: str = "Etiquetas QR Code Animora",
) -> bytes:
    """
    Gera um arquivo PDF em memória respeitando milimetricamente o tamanho da página,
    margens, colunas, linhas, espaçamentos e tamanhos de QR Code e fonte.
    """
    buffer = BytesIO()
    page_w_mm = float(layout["page_width_mm"])
    page_h_mm = float(layout["page_height_mm"])
    page_size_pt = (page_w_mm * mm, page_h_mm * mm)

    pdf = canvas.Canvas(buffer, pagesize=page_size_pt)
    pdf.setTitle(document_title)
    pdf.setAuthor("Animora")

    cols = int(layout["columns"])
    rows = int(layout["rows"])
    per_page = max(1, cols * rows)

    label_w_mm = float(layout["label_width_mm"])
    label_h_mm = float(layout["label_height_mm"])
    gap_x_mm = float(layout["gap_x_mm"])
    gap_y_mm = float(layout["gap_y_mm"])
    margin_top_mm = float(layout["margin_top_mm"])
    margin_left_mm = float(layout["margin_left_mm"])

    for page_idx in range(0, len(units), per_page):
        if page_idx > 0:
            pdf.showPage()

        page_units = units[page_idx : page_idx + per_page]
        for idx, unit in enumerate(page_units):
            r = idx // cols
            c = idx % cols
            x_mm = margin_left_mm + c * (label_w_mm + gap_x_mm)
            y_bottom_mm = page_h_mm - margin_top_mm - ((r + 1) * label_h_mm) - (r * gap_y_mm)
            _draw_single_label(pdf, unit, layout, x_mm, y_bottom_mm, base_url)

    pdf.save()
    return buffer.getvalue()
