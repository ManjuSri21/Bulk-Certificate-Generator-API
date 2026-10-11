from pathlib import Path
from uuid import UUID

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
import reportlab


def _fit_text(text: str, font_name: str, font_size: float, max_width: float) -> str:
    if stringWidth(text, font_name, font_size) <= max_width:
        return text
    suffix = "..."
    while text and stringWidth(text + suffix, font_name, font_size) > max_width:
        text = text[:-1]
    return text + suffix


def generate_certificate(
    output_dir: Path,
    job_id: UUID,
    recipient_id: UUID,
    recipient_name: str,
    event_name: str,
    completion_date: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{job_id}_{recipient_id}.pdf"
    font_path = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    if "CertificateVera" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("CertificateVera", str(font_path)))

    page_width, page_height = landscape(A4)
    canvas = Canvas(str(output_path), pagesize=(page_width, page_height))
    canvas.setTitle(f"Certificate - {recipient_name}")

    canvas.setStrokeColorRGB(0.14, 0.29, 0.43)
    canvas.setLineWidth(2)
    canvas.roundRect(16 * mm, 16 * mm, page_width - 32 * mm, page_height - 32 * mm, 5 * mm)
    canvas.setStrokeColorRGB(0.72, 0.59, 0.31)
    canvas.setLineWidth(0.8)
    canvas.roundRect(20 * mm, 20 * mm, page_width - 40 * mm, page_height - 40 * mm, 4 * mm)

    center_x = page_width / 2
    canvas.setFillColorRGB(0.14, 0.29, 0.43)
    canvas.setFont("CertificateVera", 27)
    canvas.drawCentredString(center_x, page_height - 55 * mm, "CERTIFICATE")
    canvas.setFont("CertificateVera", 13)
    canvas.drawCentredString(center_x, page_height - 66 * mm, "OF COMPLETION")

    canvas.setFillColorRGB(0.25, 0.25, 0.25)
    canvas.setFont("CertificateVera", 12)
    canvas.drawCentredString(center_x, page_height - 88 * mm, "This certificate is proudly presented to")
    canvas.setFillColorRGB(0.14, 0.29, 0.43)
    canvas.setFont("CertificateVera", 25)
    canvas.drawCentredString(
        center_x,
        page_height - 105 * mm,
        _fit_text(recipient_name, "CertificateVera", 25, page_width - 70 * mm),
    )

    canvas.setFillColorRGB(0.25, 0.25, 0.25)
    canvas.setFont("CertificateVera", 12)
    canvas.drawCentredString(center_x, page_height - 124 * mm, "for successfully completing")
    canvas.setFillColorRGB(0.14, 0.29, 0.43)
    canvas.setFont("CertificateVera", 17)
    canvas.drawCentredString(
        center_x,
        page_height - 137 * mm,
        _fit_text(event_name, "CertificateVera", 17, page_width - 70 * mm),
    )

    canvas.setFillColorRGB(0.25, 0.25, 0.25)
    canvas.setFont("CertificateVera", 10)
    canvas.drawCentredString(center_x, 32 * mm, f"Completed on {completion_date}")
    canvas.save()
    return output_path
