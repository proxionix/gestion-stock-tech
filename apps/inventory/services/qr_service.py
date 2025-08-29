"""
QR Code generation and PDF printing service for Stock Management System.
"""
import io
import os
from typing import Optional, Tuple, List, Dict, Any
from decimal import Decimal
from django.core.files.base import ContentFile
from django.conf import settings
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.renderPDF import drawToFile
from apps.inventory.models import Article, ArticleQR


class QRService:
    """Service class for QR code generation and PDF printing."""
    
    @staticmethod
    def generate_qr_code(article: Article, size: int = 10, border: int = 4) -> ArticleQR:
        """
        Generate QR code for an article.
        
        Args:
            article: Article to generate QR for
            size: QR code size (box_size)
            border: QR code border size
        
        Returns:
            Created ArticleQR instance
        """
        # Generate QR code payload URL
        payload_url = f"/a/{article.reference}"
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=size,
            border=border,
        )
        qr.add_data(payload_url)
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to file-like object
        img_io = io.BytesIO()
        img.save(img_io, format='PNG')
        img_io.seek(0)
        
        # Create or update ArticleQR instance
        qr_filename = f"{article.reference}_qr.png"
        article_qr, created = ArticleQR.objects.get_or_create(
            article=article,
            defaults={'payload_url': payload_url}
        )
        
        article_qr.payload_url = payload_url
        article_qr.png_file.save(
            qr_filename,
            ContentFile(img_io.getvalue()),
            save=True
        )
        
        return article_qr
    
    @staticmethod
    def regenerate_all_qr_codes() -> int:
        """
        Regenerate QR codes for all active articles.
        
        Returns:
            Number of QR codes regenerated
        """
        count = 0
        for article in Article.objects.filter(is_active=True):
            QRService.generate_qr_code(article)
            count += 1
        return count
    
    @staticmethod
    def create_qr_labels_pdf(
        article: Article,
        cols: int = 3,
        rows: int = 8,
        margin: float = 10.0,
        count: int = 24,
        include_text: bool = True
    ) -> bytes:
        """
        Create PDF with QR code labels for printing.
        
        Args:
            article: Article to create labels for
            cols: Number of columns per page
            rows: Number of rows per page
            margin: Page margin in mm
            count: Number of labels to generate
            include_text: Include article reference text below QR
        
        Returns:
            PDF content as bytes
        """
        # Page setup
        page_width, page_height = A4
        margin_points = margin * mm
        
        # Calculate label dimensions
        label_width = (page_width - 2 * margin_points) / cols
        label_height = (page_height - 2 * margin_points) / rows
        
        # QR code size (80% of label width)
        qr_size = label_width * 0.8
        
        # Create PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=margin_points,
            rightMargin=margin_points,
            topMargin=margin_points,
            bottomMargin=margin_points
        )
        
        # Story elements
        story = []
        
        # Add title
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1  # Center alignment
        )
        
        title = Paragraph(
            f"QR Labels - {article.reference}: {article.name}",
            title_style
        )
        story.append(title)
        story.append(Spacer(1, 10))
        
        # Calculate labels per page
        labels_per_page = cols * rows
        pages_needed = (count + labels_per_page - 1) // labels_per_page
        
        for page in range(pages_needed):
            # Labels for this page
            page_labels = min(count - page * labels_per_page, labels_per_page)
            
            # Create table data
            table_data = []
            label_index = 0
            
            for row in range(rows):
                row_data = []
                for col in range(cols):
                    if label_index < page_labels:
                        # Create QR code cell content
                        cell_content = QRService._create_qr_cell_content(
                            article, qr_size, include_text
                        )
                        row_data.append(cell_content)
                        label_index += 1
                    else:
                        row_data.append("")  # Empty cell
                table_data.append(row_data)
            
            # Create table
            table = Table(
                table_data,
                colWidths=[label_width] * cols,
                rowHeights=[label_height] * rows
            )
            
            # Table style
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            
            story.append(table)
            
            # Page break if not last page
            if page < pages_needed - 1:
                story.append(Spacer(1, 20))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF content
        buffer.seek(0)
        return buffer.getvalue()
    
    @staticmethod
    def _create_qr_cell_content(article: Article, qr_size: float, include_text: bool) -> str:
        """Create HTML-like content for QR code cell."""
        # Get or generate QR code
        try:
            article_qr = article.qr_code
        except ArticleQR.DoesNotExist:
            article_qr = QRService.generate_qr_code(article)
        
        # For now, return text representation
        # In a full implementation, you'd embed the actual QR code image
        content_parts = []
        
        # QR code placeholder (in real implementation, use actual image)
        content_parts.append(f"[QR:{article.reference}]")
        
        if include_text:
            content_parts.append(f"\n{article.reference}")
            if len(article.name) <= 20:
                content_parts.append(f"\n{article.name}")
        
        return "\n".join(content_parts)
    
    @staticmethod
    def create_advanced_qr_pdf(
        articles: List[Article],
        layout: Dict[str, Any] = None
    ) -> bytes:
        """
        Create advanced QR code PDF with multiple articles.
        
        Args:
            articles: List of articles to include
            layout: Layout configuration
        
        Returns:
            PDF content as bytes
        """
        if layout is None:
            layout = {
                'cols': 3,
                'rows': 8,
                'margin': 10.0,
                'include_text': True,
                'include_description': False,
                'qr_size_ratio': 0.7
            }
        
        # Page setup
        page_width, page_height = A4
        margin_points = layout['margin'] * mm
        
        # Calculate label dimensions
        cols = layout['cols']
        rows = layout['rows']
        label_width = (page_width - 2 * margin_points) / cols
        label_height = (page_height - 2 * margin_points) / rows
        
        # Create PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=margin_points,
            rightMargin=margin_points,
            topMargin=margin_points,
            bottomMargin=margin_points
        )
        
        story = []
        
        # Add header
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=14,
            spaceAfter=15,
            alignment=1
        )
        
        title = Paragraph("Article QR Codes", title_style)
        story.append(title)
        
        # Process articles in batches
        labels_per_page = cols * rows
        total_articles = len(articles)
        
        for start_idx in range(0, total_articles, labels_per_page):
            end_idx = min(start_idx + labels_per_page, total_articles)
            page_articles = articles[start_idx:end_idx]
            
            # Create table data
            table_data = []
            article_index = 0
            
            for row in range(rows):
                row_data = []
                for col in range(cols):
                    if article_index < len(page_articles):
                        article = page_articles[article_index]
                        cell_content = QRService._create_article_cell_content(
                            article, layout
                        )
                        row_data.append(cell_content)
                        article_index += 1
                    else:
                        row_data.append("")
                table_data.append(row_data)
            
            # Create table
            table = Table(
                table_data,
                colWidths=[label_width] * cols,
                rowHeights=[label_height] * rows
            )
            
            # Apply table style
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            
            story.append(table)
            
            # Add page break if more articles
            if end_idx < total_articles:
                story.append(Spacer(1, 20))
        
        # Build PDF
        doc.build(story)
        
        buffer.seek(0)
        return buffer.getvalue()
    
    @staticmethod
    def _create_article_cell_content(article: Article, layout: Dict[str, Any]) -> str:
        """Create content for article cell in PDF."""
        content_parts = []
        
        # QR code representation
        content_parts.append(f"[QR]")
        
        # Article reference
        if layout.get('include_text', True):
            content_parts.append(article.reference)
        
        # Article name (truncated if needed)
        if layout.get('include_text', True):
            name = article.name
            if len(name) > 25:
                name = name[:22] + "..."
            content_parts.append(name)
        
        # Description (if enabled and fits)
        if layout.get('include_description', False) and article.description:
            desc = article.description
            if len(desc) > 30:
                desc = desc[:27] + "..."
            content_parts.append(desc)
        
        return "\n".join(content_parts)
    
    @staticmethod
    def get_qr_print_templates() -> List[Dict[str, Any]]:
        """Get available QR print templates."""
        return [
            {
                'name': 'Standard Labels',
                'description': 'Standard 3x8 labels for A4',
                'layout': {
                    'cols': 3,
                    'rows': 8,
                    'margin': 10.0,
                    'include_text': True,
                    'include_description': False
                }
            },
            {
                'name': 'Small Labels',
                'description': 'Small 4x10 labels for A4',
                'layout': {
                    'cols': 4,
                    'rows': 10,
                    'margin': 8.0,
                    'include_text': True,
                    'include_description': False
                }
            },
            {
                'name': 'Large Labels',
                'description': 'Large 2x6 labels with description',
                'layout': {
                    'cols': 2,
                    'rows': 6,
                    'margin': 15.0,
                    'include_text': True,
                    'include_description': True
                }
            },
            {
                'name': 'QR Only',
                'description': 'QR codes only, no text',
                'layout': {
                    'cols': 4,
                    'rows': 8,
                    'margin': 10.0,
                    'include_text': False,
                    'include_description': False
                }
            }
        ]
