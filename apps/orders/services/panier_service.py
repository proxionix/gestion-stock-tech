"""
Panier (Cart) service for Stock Management System.
Handles shopping cart operations with atomic transactions.
"""
from decimal import Decimal
from typing import Optional
from django.db import transaction, IntegrityError
from django.utils.translation import gettext_lazy as _
from apps.orders.models import Panier, PanierLine, PanierStatus, Demande
from apps.inventory.models import Article
from apps.users.models import Profile
from apps.audit.services.audit_service import AuditService


class PanierServiceError(Exception):
    """Base exception for panier service errors."""
    pass


class PanierService:
    """Service class for managing shopping carts."""
    
    @staticmethod
    @transaction.atomic
    def get_or_create_active_cart(technician: Profile) -> Panier:
        """
        Get or create the active DRAFT cart for a technician.
        Only one DRAFT cart allowed per technician.
        """
        if technician.role != 'TECH':
            raise PanierServiceError(_("Only technicians can have carts"))
        
        cart, created = Panier.objects.select_for_update().get_or_create(
            technician=technician,
            status=PanierStatus.DRAFT,
            defaults={
                'notes': ''
            }
        )
        
        if created:
            AuditService.log_event(
                actor_user=technician.user,
                entity_type='Panier',
                entity_id=str(cart.id),
                action='create_cart',
                after_data={'status': cart.status}
            )
        
        return cart
    
    @staticmethod
    @transaction.atomic
    def add_to_cart(
        technician: Profile,
        article: Article,
        quantity: Decimal,
        notes: str = ""
    ) -> PanierLine:
        """
        Add or update an article in the cart.
        Aggregates quantities if article already exists.
        """
        if not article.is_active:
            raise PanierServiceError(_("Cannot add inactive article to cart"))
        
        if quantity <= 0:
            raise PanierServiceError(_("Quantity must be positive"))
        
        # Get or create active cart
        cart = PanierService.get_or_create_active_cart(technician)
        
        if cart.status != PanierStatus.DRAFT:
            raise PanierServiceError(_("Cannot modify a submitted cart"))
        
        # Get or create cart line with locking
        line, created = PanierLine.objects.select_for_update().get_or_create(
            panier=cart,
            article=article,
            defaults={
                'quantity': quantity,
                'notes': notes
            }
        )
        
        if not created:
            # Update existing line - aggregate quantities
            old_quantity = line.quantity
            line.quantity += quantity
            line.notes = notes or line.notes
            line.save(update_fields=['quantity', 'notes', 'updated_at'])
            
            AuditService.log_event(
                actor_user=technician.user,
                entity_type='PanierLine',
                entity_id=str(line.id),
                action='update_cart_line',
                before_data={'quantity': str(old_quantity)},
                after_data={'quantity': str(line.quantity)}
            )
        else:
            AuditService.log_event(
                actor_user=technician.user,
                entity_type='PanierLine',
                entity_id=str(line.id),
                action='add_to_cart',
                after_data={
                    'article_id': str(article.id),
                    'article_reference': article.reference,
                    'quantity': str(quantity)
                }
            )
        
        return line
    
    @staticmethod
    @transaction.atomic
    def update_cart_line_quantity(
        technician: Profile,
        line_id: str,
        new_quantity: Decimal
    ) -> Optional[PanierLine]:
        """
        Update the quantity of a cart line.
        Remove line if quantity is 0 or negative.
        """
        try:
            line = PanierLine.objects.select_for_update().select_related(
                'panier__technician', 'article'
            ).get(id=line_id, panier__technician=technician)
        except PanierLine.DoesNotExist:
            raise PanierServiceError(_("Cart line not found"))
        
        if line.panier.status != PanierStatus.DRAFT:
            raise PanierServiceError(_("Cannot modify a submitted cart"))
        
        old_quantity = line.quantity
        
        if new_quantity <= 0:
            # Remove line
            AuditService.log_event(
                actor_user=technician.user,
                entity_type='PanierLine',
                entity_id=str(line.id),
                action='remove_from_cart',
                before_data={
                    'article_reference': line.article.reference,
                    'quantity': str(old_quantity)
                }
            )
            line.delete()
            return None
        else:
            # Update quantity
            line.quantity = new_quantity
            line.save(update_fields=['quantity', 'updated_at'])
            
            AuditService.log_event(
                actor_user=technician.user,
                entity_type='PanierLine',
                entity_id=str(line.id),
                action='update_cart_line',
                before_data={'quantity': str(old_quantity)},
                after_data={'quantity': str(new_quantity)}
            )
            return line
    
    @staticmethod
    @transaction.atomic
    def remove_from_cart(technician: Profile, line_id: str) -> bool:
        """Remove a line from the cart."""
        result = PanierService.update_cart_line_quantity(
            technician, line_id, Decimal('0')
        )
        return result is None
    
    @staticmethod
    @transaction.atomic
    def submit_cart(technician: Profile, notes: str = "") -> Demande:
        """
        Submit the cart and create a demand.
        This locks the cart and creates the demand workflow.
        """
        try:
            cart = Panier.objects.select_for_update().get(
                technician=technician,
                status=PanierStatus.DRAFT
            )
        except Panier.DoesNotExist:
            raise PanierServiceError(_("No active cart found"))
        
        if not cart.can_be_submitted():
            raise PanierServiceError(_("Cart cannot be submitted"))
        
        # Update cart notes if provided
        if notes:
            cart.notes = notes
            cart.save(update_fields=['notes', 'updated_at'])
        
        # Submit cart (this creates the demand)
        demande = cart.submit()
        
        AuditService.log_event(
            actor_user=technician.user,
            entity_type='Panier',
            entity_id=str(cart.id),
            action='submit_cart',
            before_data={'status': PanierStatus.DRAFT},
            after_data={
                'status': PanierStatus.SUBMITTED,
                'demande_id': str(demande.id),
                'total_items': cart.total_items,
                'total_quantity': str(cart.total_quantity)
            }
        )
        
        AuditService.log_event(
            actor_user=technician.user,
            entity_type='Demande',
            entity_id=str(demande.id),
            action='create_demand',
            after_data={
                'status': demande.status,
                'total_requested_items': demande.total_requested_items,
                'total_requested_quantity': str(demande.total_requested_quantity)
            }
        )
        
        return demande
    
    @staticmethod
    def get_cart_summary(technician: Profile) -> dict:
        """Get summary information about the technician's active cart."""
        try:
            cart = Panier.objects.prefetch_related(
                'lines__article'
            ).get(
                technician=technician,
                status=PanierStatus.DRAFT
            )
            
            lines_data = []
            for line in cart.lines.all():
                lines_data.append({
                    'id': str(line.id),
                    'article': {
                        'id': str(line.article.id),
                        'reference': line.article.reference,
                        'name': line.article.name,
                        'unit': line.article.unit,
                    },
                    'quantity': str(line.quantity),
                    'notes': line.notes,
                    'created_at': line.created_at.isoformat(),
                    'updated_at': line.updated_at.isoformat(),
                })
            
            return {
                'cart_id': str(cart.id),
                'status': cart.status,
                'total_items': cart.total_items,
                'total_quantity': str(cart.total_quantity),
                'notes': cart.notes,
                'lines': lines_data,
                'can_be_submitted': cart.can_be_submitted(),
                'created_at': cart.created_at.isoformat(),
                'updated_at': cart.updated_at.isoformat(),
            }
        except Panier.DoesNotExist:
            return {
                'cart_id': None,
                'status': None,
                'total_items': 0,
                'total_quantity': '0',
                'notes': '',
                'lines': [],
                'can_be_submitted': False,
                'created_at': None,
                'updated_at': None,
            }
    
    @staticmethod
    @transaction.atomic
    def clear_cart(technician: Profile) -> bool:
        """Clear all items from the active cart."""
        try:
            cart = Panier.objects.select_for_update().get(
                technician=technician,
                status=PanierStatus.DRAFT
            )
        except Panier.DoesNotExist:
            return False
        
        if cart.status != PanierStatus.DRAFT:
            raise PanierServiceError(_("Cannot clear a submitted cart"))
        
        lines_count = cart.lines.count()
        cart.lines.all().delete()
        
        AuditService.log_event(
            actor_user=technician.user,
            entity_type='Panier',
            entity_id=str(cart.id),
            action='clear_cart',
            before_data={'lines_count': lines_count},
            after_data={'lines_count': 0}
        )
        
        return True
