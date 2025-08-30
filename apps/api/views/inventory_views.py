"""
Inventory API views for Stock Management System.
"""
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from apps.inventory.models import Article, StockTech, Threshold
from apps.inventory.services.stock_service import StockService
from apps.api.serializers import (
    ArticleSerializer, StockTechSerializer, ThresholdSerializer, IssueStockSerializer,
    StockAdjustSerializer
)
from apps.api.permissions import (
    ArticlePermissions, IsTechnicianOrAdmin, IsTechnicianOwnerOrAdmin, IsAdmin
)


class ArticleListCreateView(generics.ListCreateAPIView):
    """
    List articles with search and filtering.
    Create new articles (admin only).
    """
    serializer_class = ArticleSerializer
    permission_classes = [ArticlePermissions]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'unit', 'is_active']
    search_fields = ['reference', 'name', 'description', 'manufacturer']
    ordering_fields = ['reference', 'name', 'created_at']
    ordering = ['reference']
    
    def get_queryset(self):
        """Get articles based on user role."""
        if self.request.user.profile.is_admin:
            return Article.objects.all()
        else:
            # Technicians only see active articles
            return Article.objects.filter(is_active=True)


class ArticleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete an article.
    """
    serializer_class = ArticleSerializer
    permission_classes = [ArticlePermissions]
    
    def get_queryset(self):
        """Get articles based on user role."""
        if self.request.user.profile.is_admin:
            return Article.objects.all()
        else:
            return Article.objects.filter(is_active=True)


@api_view(['GET'])
@permission_classes([IsTechnicianOrAdmin])
def my_stock(request):
    """
    Get current user's stock levels.
    """
    if not request.user.profile.is_technician:
        return Response(
            {'error': 'Only technicians have stock'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    stock_items = StockService.get_technician_stock(
        technician=request.user.profile,
        include_zero=request.query_params.get('include_zero', 'false').lower() == 'true'
    )
    
    return Response({
        'technician': {
            'id': str(request.user.profile.id),
            'name': request.user.profile.display_name,
        },
        'stock_items': stock_items
    })


@api_view(['GET'])
@permission_classes([IsAdmin])
def technician_stock(request, technician_id):
    """
    Get stock levels for a specific technician (admin only).
    """
    try:
        from apps.users.models import Profile
        technician = Profile.objects.get(id=technician_id, role='TECH')
    except Profile.DoesNotExist:
        return Response(
            {'error': 'Technician not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    stock_items = StockService.get_technician_stock(
        technician=technician,
        include_zero=request.query_params.get('include_zero', 'false').lower() == 'true'
    )
    
    return Response({
        'technician': {
            'id': str(technician.id),
            'name': technician.display_name,
        },
        'stock_items': stock_items
    })


@api_view(['POST'])
@permission_classes([IsTechnicianOrAdmin])
def issue_stock(request):
    """
    Declare stock usage.
    """
    if not request.user.profile.is_technician:
        return Response(
            {'error': 'Only technicians can issue stock'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = IssueStockSerializer(data=request.data)
    if serializer.is_valid():
        try:
            from apps.inventory.models import Article
            article = Article.objects.get(id=serializer.validated_data['article_id'])
            
            movement = StockService.issue_stock(
                technician=request.user.profile,
                article=article,
                quantity=serializer.validated_data['quantity'],
                location_text=serializer.validated_data['location_text'],
                performed_by=request.user,
                notes=serializer.validated_data.get('notes', '')
            )
            
            return Response({
                'message': 'Stock issued successfully',
                'movement_id': str(movement.id),
                'balance_after': str(movement.balance_after)
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAdmin])
def admin_adjust_stock(request):
    """
    Admin adjustment: add/remove/set stock for a technician.
    """
    serializer = StockAdjustSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    try:
        from apps.users.models import Profile
        from apps.inventory.models import Article, StockTech
        from apps.inventory.services.stock_service import StockService
        from apps.audit.services.audit_service import AuditService

        technician = Profile.objects.get(id=data['technician_id'], role='TECH')
        article = Article.objects.get(id=data['article_id'])

        # Lock stock row
        stock, _ = StockTech.objects.select_for_update().get_or_create(
            technician=technician,
            article=article,
            defaults={'quantity': 0}
        )

        operation = data['operation']
        qty = data['quantity']
        reason = data.get('reason', '')
        notes = data.get('notes', '')

        old_qty = stock.quantity
        if operation == 'add':
            new_qty = old_qty + qty
        elif operation == 'remove':
            if qty > stock.available_quantity:
                return Response({'error': 'Insufficient stock to remove'}, status=400)
            new_qty = old_qty - qty
        else:  # set
            if qty < 0:
                return Response({'error': 'Quantity cannot be negative'}, status=400)
            new_qty = qty

        # Use adjust to keep movement/audit consistent
        movement = StockService.adjust_stock(
            technician=technician,
            article=article,
            new_quantity=new_qty,
            reason=reason or f"admin_{operation}",
            performed_by=request.user,
            notes=notes
        )

        return Response({
            'message': 'Stock adjusted',
            'movement_id': str(movement.id),
            'balance_after': str(movement.balance_after)
        })
    except Profile.DoesNotExist:
        return Response({'error': 'Technician not found'}, status=404)
    except Article.DoesNotExist:
        return Response({'error': 'Article not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400)
