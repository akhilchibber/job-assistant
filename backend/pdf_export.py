import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT


def generate_cover_letter_pdf(cover_letter_text: str) -> bytes:
    """Render cover letter text into a styled PDF and return raw bytes."""
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
        fontSize=11,
        leading=16,
        alignment=TA_LEFT,
        spaceAfter=10,
    )

    story = []
    # Split on double newlines to preserve paragraph breaks
    paragraphs = cover_letter_text.strip().split("\n\n")
    for para in paragraphs:
        # Replace single newlines with a space within a paragraph
        clean = para.replace("\n", " ").strip()
        if clean:
            story.append(Paragraph(clean, body_style))
            story.append(Spacer(1, 0.3 * cm))

    doc.build(story)
    return buffer.getvalue()
