"""
QR Code and PDF generation API views for Stock Management System.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from apps.inventory.models import Article
from apps.inventory.services.qr_service import QRService
from apps.api.permissions import ArticlePermissions
from apps.api.serializers import ArticleSerializer


@api_view(['GET'])
@permission_classes([ArticlePermissions])
def get_article_qr(request, article_id):
    """
    Get QR code data for an article.
    """
    article = get_object_or_404(Article, id=article_id)
    
    try:
        qr_code = article.qr_code
        return Response({
            'article_id': str(article.id),
            'article_reference': article.reference,
            'qr_payload_url': qr_code.payload_url,
            'qr_image_url': qr_code.png_file.url if qr_code.png_file else None,
            'created_at': qr_code.created_at.isoformat(),
        })
    except:
        # Generate QR if it doesn't exist
        qr_code = QRService.generate_qr_code(article)
        return Response({
            'article_id': str(article.id),
            'article_reference': article.reference,
            'qr_payload_url': qr_code.payload_url,
            'qr_image_url': qr_code.png_file.url if qr_code.png_file else None,
            'created_at': qr_code.created_at.isoformat(),
            'message': 'QR code generated'
        })


@api_view(['POST'])
@permission_classes([ArticlePermissions])
def regenerate_article_qr(request, article_id):
    """
    Regenerate QR code for an article.
    """
    article = get_object_or_404(Article, id=article_id)
    
    # Extract parameters
    size = int(request.data.get('size', 10))
    border = int(request.data.get('border', 4))
    
    if size < 1 or size > 20:
        return Response(
            {'error': 'Size must be between 1 and 20'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if border < 0 or border > 10:
        return Response(
            {'error': 'Border must be between 0 and 10'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Regenerate QR code
    qr_code = QRService.generate_qr_code(article, size=size, border=border)
    
    return Response({
        'article_id': str(article.id),
        'article_reference': article.reference,
        'qr_payload_url': qr_code.payload_url,
        'qr_image_url': qr_code.png_file.url if qr_code.png_file else None,
        'message': 'QR code regenerated successfully'
    })


@api_view(['POST'])
@permission_classes([ArticlePermissions])
def print_qr_sheet(request, article_id):
    """
    Generate PDF sheet with QR code labels for an article.
    
    POST /api/articles/{id}/qr/print-sheet
    Parameters: cols, rows, margin, count, include_text
    """
    article = get_object_or_404(Article, id=article_id)
    
    # Extract parameters with defaults
    cols = int(request.data.get('cols', 3))
    rows = int(request.data.get('rows', 8))
    margin = float(request.data.get('margin', 10.0))
    count = int(request.data.get('count', 24))
    include_text = request.data.get('include_text', True)
    
    # Validate parameters
    if cols < 1 or cols > 10:
        return Response(
            {'error': 'Columns must be between 1 and 10'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if rows < 1 or rows > 20:
        return Response(
            {'error': 'Rows must be between 1 and 20'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if margin < 0 or margin > 50:
        return Response(
            {'error': 'Margin must be between 0 and 50mm'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if count < 1 or count > 1000:
        return Response(
            {'error': 'Count must be between 1 and 1000'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Generate PDF
        pdf_content = QRService.create_qr_labels_pdf(
            article=article,
            cols=cols,
            rows=rows,
            margin=margin,
            count=count,
            include_text=include_text
        )
        
        # Create response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"qr_labels_{article.reference}_{count}pc.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(pdf_content)
        
        return response
        
    except Exception as e:
        return Response(
            {'error': f'Failed to generate PDF: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([ArticlePermissions])
def print_multiple_qr_sheet(request):
    """
    Generate PDF sheet with QR codes for multiple articles.
    
    POST /api/articles/qr/print-multiple
    Body: {
        "article_ids": ["uuid1", "uuid2", ...],
        "layout": {
            "cols": 3,
            "rows": 8,
            "margin": 10.0,
            "include_text": true,
            "include_description": false
        }
    }
    """
    article_ids = request.data.get('article_ids', [])
    layout = request.data.get('layout', {})
    
    if not article_ids:
        return Response(
            {'error': 'article_ids is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if len(article_ids) > 100:
        return Response(
            {'error': 'Maximum 100 articles allowed'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get articles
    articles = Article.objects.filter(id__in=article_ids, is_active=True)
    
    if not articles.exists():
        return Response(
            {'error': 'No valid articles found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    try:
        # Generate PDF
        pdf_content = QRService.create_advanced_qr_pdf(
            articles=list(articles),
            layout=layout
        )
        
        # Create response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"qr_labels_multiple_{len(articles)}articles.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(pdf_content)
        
        return response
        
    except Exception as e:
        return Response(
            {'error': f'Failed to generate PDF: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([ArticlePermissions])
def get_print_templates(request):
    """
    Get available QR print templates.
    """
    templates = QRService.get_qr_print_templates()
    return Response({
        'templates': templates
    })


@api_view(['POST'])
@permission_classes([ArticlePermissions])
def regenerate_all_qr_codes(request):
    """
    Regenerate QR codes for all active articles.
    Admin only operation.
    """
    if not request.user.profile.is_admin:
        return Response(
            {'error': 'Only administrators can regenerate all QR codes'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        count = QRService.regenerate_all_qr_codes()
        return Response({
            'message': f'Successfully regenerated {count} QR codes',
            'count': count
        })
    except Exception as e:
        return Response(
            {'error': f'Failed to regenerate QR codes: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([ArticlePermissions])
def preview_qr_layout(request):
    """
    Preview QR layout parameters.
    
    GET /api/articles/qr/preview?cols=3&rows=8&margin=10
    """
    cols = int(request.query_params.get('cols', 3))
    rows = int(request.query_params.get('rows', 8))
    margin = float(request.query_params.get('margin', 10.0))
    
    # Calculate layout dimensions
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    
    page_width, page_height = A4
    margin_points = margin * mm
    
    label_width = (page_width - 2 * margin_points) / cols
    label_height = (page_height - 2 * margin_points) / rows
    
    # Convert back to mm for display
    label_width_mm = label_width / mm
    label_height_mm = label_height / mm
    
    labels_per_page = cols * rows
    
    return Response({
        'layout': {
            'cols': cols,
            'rows': rows,
            'margin': margin,
            'labels_per_page': labels_per_page,
            'label_dimensions': {
                'width_mm': round(label_width_mm, 2),
                'height_mm': round(label_height_mm, 2),
            },
            'page_dimensions': {
                'width_mm': round(page_width / mm, 2),
                'height_mm': round(page_height / mm, 2),
            }
        }
    })
