"""
Orders API views for Stock Management System.
"""
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from apps.orders.models import Panier, Demande, DemandeStatus
from apps.orders.services.panier_service import PanierService
from apps.orders.services.admin_workflow import AdminWorkflow
from apps.api.serializers import (
    PanierSerializer, DemandeSerializer, AddToCartSerializer, 
    UpdateCartLineSerializer, ApprovePartialSerializer, 
    RefuseDemandeSerializer, HandoverSerializer
)
from apps.api.permissions import (
    IsTechnicianOrAdmin, IsAdmin, DemandPermissions
)


@api_view(['GET'])
@permission_classes([IsTechnicianOrAdmin])
def my_cart(request):
    """
    Get current user's shopping cart.
    """
    if not request.user.profile.is_technician:
        return Response(
            {'error': 'Only technicians have carts'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    cart_summary = PanierService.get_cart_summary(request.user.profile)
    return Response(cart_summary)


@api_view(['POST'])
@permission_classes([IsTechnicianOrAdmin])
def add_to_cart(request):
    """
    Add an item to the cart.
    """
    if not request.user.profile.is_technician:
        return Response(
            {'error': 'Only technicians can add to cart'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = AddToCartSerializer(data=request.data)
    if serializer.is_valid():
        try:
            from apps.inventory.models import Article
            article = Article.objects.get(id=serializer.validated_data['article_id'])
            
            line = PanierService.add_to_cart(
                technician=request.user.profile,
                article=article,
                quantity=serializer.validated_data['quantity'],
                notes=serializer.validated_data.get('notes', '')
            )
            
            return Response({
                'message': 'Item added to cart',
                'line_id': str(line.id),
                'quantity': str(line.quantity)
            })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
@permission_classes([IsTechnicianOrAdmin])
def update_cart_line(request, line_id):
    """
    Update quantity of a cart line.
    """
    if not request.user.profile.is_technician:
        return Response(
            {'error': 'Only technicians can update cart'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = UpdateCartLineSerializer(data=request.data)
    if serializer.is_valid():
        try:
            line = PanierService.update_cart_line_quantity(
                technician=request.user.profile,
                line_id=line_id,
                new_quantity=serializer.validated_data['quantity']
            )
            
            if line:
                return Response({
                    'message': 'Cart line updated',
                    'line_id': str(line.id),
                    'quantity': str(line.quantity)
                })
            else:
                return Response({
                    'message': 'Cart line removed'
                })
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsTechnicianOrAdmin])
def submit_cart(request):
    """
    Submit the cart and create a demand.
    """
    if not request.user.profile.is_technician:
        return Response(
            {'error': 'Only technicians can submit carts'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    notes = request.data.get('notes', '')
    
    try:
        demande = PanierService.submit_cart(
            technician=request.user.profile,
            notes=notes
        )
        
        return Response({
            'message': 'Cart submitted successfully',
            'demande_id': str(demande.id),
            'status': demande.status
        })
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


class DemandeListView(generics.ListAPIView):
    """
    List demands with filtering.
    """
    serializer_class = DemandeSerializer
    permission_classes = [DemandPermissions]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'priority']
    ordering_fields = ['created_at', 'priority']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Get demands based on user role."""
        if self.request.user.profile.is_admin:
            return Demande.objects.all().select_related(
                'technician__user', 'approved_by', 'prepared_by'
            ).prefetch_related('lines__article')
        else:
            # Technicians only see their own demands
            return Demande.objects.filter(
                technician=self.request.user.profile
            ).select_related(
                'technician__user', 'approved_by', 'prepared_by'
            ).prefetch_related('lines__article')


class DemandeDetailView(generics.RetrieveAPIView):
    """
    Retrieve a specific demand.
    """
    serializer_class = DemandeSerializer
    permission_classes = [DemandPermissions]
    
    def get_queryset(self):
        """Get demands based on user role."""
        if self.request.user.profile.is_admin:
            return Demande.objects.all().select_related(
                'technician__user', 'approved_by', 'prepared_by'
            ).prefetch_related('lines__article')
        else:
            return Demande.objects.filter(
                technician=self.request.user.profile
            ).select_related(
                'technician__user', 'approved_by', 'prepared_by'
            ).prefetch_related('lines__article')


@api_view(['POST'])
@permission_classes([IsAdmin])
def approve_demand_all(request, demande_id):
    """
    Approve a demand in full (admin only).
    """
    try:
        demande = Demande.objects.get(id=demande_id)
        notes = request.data.get('notes', '')
        
        demande = AdminWorkflow.approve_demand_full(
            demande=demande,
            approved_by=request.user,
            notes=notes
        )
        
        return Response({
            'message': 'Demand approved successfully',
            'demande_id': str(demande.id),
            'status': demande.status
        })
    
    except Demande.DoesNotExist:
        return Response(
            {'error': 'Demand not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAdmin])
def approve_demand_partial(request, demande_id):
    """
    Approve a demand partially (admin only).
    """
    try:
        demande = Demande.objects.get(id=demande_id)
        
        serializer = ApprovePartialSerializer(data=request.data)
        if serializer.is_valid():
            demande = AdminWorkflow.approve_demand_partial(
                demande=demande,
                approved_by=request.user,
                line_approvals=serializer.validated_data['line_approvals'],
                notes=serializer.validated_data.get('notes', '')
            )
            
            return Response({
                'message': 'Demand approved partially',
                'demande_id': str(demande.id),
                'status': demande.status
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    except Demande.DoesNotExist:
        return Response(
            {'error': 'Demand not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAdmin])
def refuse_demand(request, demande_id):
    """
    Refuse a demand (admin only).
    """
    try:
        demande = Demande.objects.get(id=demande_id)
        
        serializer = RefuseDemandeSerializer(data=request.data)
        if serializer.is_valid():
            demande = AdminWorkflow.refuse_demand(
                demande=demande,
                refused_by=request.user,
                reason=serializer.validated_data['reason']
            )
            
            return Response({
                'message': 'Demand refused',
                'demande_id': str(demande.id),
                'status': demande.status
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    except Demande.DoesNotExist:
        return Response(
            {'error': 'Demand not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAdmin])
def prepare_demand(request, demande_id):
    """
    Prepare a demand (admin only).
    """
    try:
        demande = Demande.objects.get(id=demande_id)
        
        demande = AdminWorkflow.prepare_demand(
            demande=demande,
            prepared_by=request.user
        )
        
        return Response({
            'message': 'Demand prepared successfully',
            'demande_id': str(demande.id),
            'status': demande.status
        })
    
    except Demande.DoesNotExist:
        return Response(
            {'error': 'Demand not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAdmin])
def handover_demand(request, demande_id):
    """
    Complete demand handover (admin only).
    """
    try:
        demande = Demande.objects.get(id=demande_id)
        
        serializer = HandoverSerializer(data=request.data)
        if serializer.is_valid():
            demande = AdminWorkflow.handover_demand(
                demande=demande,
                method=serializer.validated_data['method'],
                device_info=serializer.validated_data['device_info'],
                performed_by=request.user,
                pin=serializer.validated_data.get('pin'),
                signature_data=serializer.validated_data.get('signature_data')
            )
            
            return Response({
                'message': 'Demand handed over successfully',
                'demande_id': str(demande.id),
                'status': demande.status
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    except Demande.DoesNotExist:
        return Response(
            {'error': 'Demand not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAdmin])
def demands_queue(request):
    """
    Get demands queue for admin review.
    """
    status_filter = request.query_params.get('status')
    demands = AdminWorkflow.get_demands_queue(status=status_filter)
    
    return Response({
        'demands': demands,
        'total_count': len(demands)
    })
