"""
PDF stub for transfer notes between technicians.
"""
from typing import Any
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO


class TransferPDFService:
    @staticmethod
    def create_transfer_pdf(from_technician: Any, to_technician: Any, article: Any, quantity, performed_by: Any) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph("Transfer Note", styles['Title']))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"From: {from_technician.display_name}", styles['Normal']))
        story.append(Paragraph(f"To: {to_technician.display_name}", styles['Normal']))
        story.append(Paragraph(f"Article: {article.reference} - {article.name}", styles['Normal']))
        story.append(Paragraph(f"Quantity: {quantity}", styles['Normal']))
        story.append(Paragraph(f"Performed by: {performed_by.username}", styles['Normal']))
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()


