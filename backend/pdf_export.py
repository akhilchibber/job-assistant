import io
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors


def generate_cover_letter_pdf(cover_letter_text: str) -> bytes:
    """Render cover letter text into a styled A4 PDF.

    Features:
    - Renders <a href="...">text</a> as clickable hyperlinks (blue, underlined)
    - Auto-shrinks font size (down to 8pt) to ensure content fits on one page
    - Falls back to reducing spacer height if still overflowing
    """

    def build_pdf(font_size: float, spacer_height: float) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=2.5 * cm,
            rightMargin=2.5 * cm,
            topMargin=2.5 * cm,
            bottomMargin=2.5 * cm,
        )

        styles = getSampleStyleSheet()
        body_style = ParagraphStyle(
            name="Body",
            parent=styles["Normal"],
            fontSize=font_size,
            leading=font_size * 1.45,
            alignment=TA_LEFT,
            spaceAfter=0,
            textColor=colors.black,
            linkUnderline=1,
        )

        story = []
        paragraphs = cover_letter_text.strip().split("\n\n")
        for para in paragraphs:
            # Preserve single line breaks within paragraph as <br/>
            clean = para.strip()
            if not clean:
                continue
            # Convert single \n to <br/> for ReportLab
            clean = clean.replace("\n", "<br/>")
            story.append(Paragraph(clean, body_style))
            story.append(Spacer(1, spacer_height * cm))

        doc.build(story)
        return buffer.getvalue()

    def fits_one_page(pdf_bytes: bytes) -> bool:
        """Check if PDF has only one page."""
        # Count occurrences of "Page" marker in PDF structure
        return pdf_bytes.count(b"/Page\n") <= 1 or pdf_bytes.count(b"endstream") <= 2

    # Try progressively smaller font sizes until it fits on one page
    for font_size in [11, 10.5, 10, 9.5, 9, 8.5, 8]:
        for spacer in [0.3, 0.2, 0.1, 0.05]:
            pdf_bytes = build_pdf(font_size, spacer)
            if fits_one_page(pdf_bytes):
                return pdf_bytes

    # Last resort — return smallest version
    return build_pdf(8, 0.05)
