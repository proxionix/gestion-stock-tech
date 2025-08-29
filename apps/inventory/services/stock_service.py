"""
Stock service for Stock Management System.
Handles stock movements and threshold checking.
"""
from decimal import Decimal
from typing import Optional, List, Dict, Any
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from apps.inventory.models import Article, StockTech, Threshold
from apps.users.models import Profile
from apps.audit.models import StockMovement, MovementReason, ThresholdAlert
from apps.audit.services.audit_service import AuditService


class StockServiceError(Exception):
    """Base exception for stock service errors."""
    pass


class StockService:
    """Service class for stock management operations."""
    
    @staticmethod
    @transaction.atomic
    def issue_stock(
        technician: Profile,
        article: Article,
        quantity: Decimal,
        location_text: str,
        performed_by: User,
        linked_demande=None,
        notes: str = ""
    ) -> StockMovement:
        """
        Issue stock from a technician's inventory.
        Records usage and checks thresholds.
        
        Args:
            technician: Technician using the stock
            article: Article being used
            quantity: Quantity to issue (positive number)
            location_text: Where/how the material is being used
            performed_by: User performing the operation
            linked_demande: Related demand if applicable
            notes: Additional notes
        
        Returns:
            Created StockMovement record
        """
        if technician.role != 'TECH':
            raise StockServiceError(_("Only technicians can issue stock"))
        
        if quantity <= 0:
            raise StockServiceError(_("Issue quantity must be positive"))
        
        # Get or create stock record with locking
        stock, created = StockTech.objects.select_for_update().get_or_create(
            technician=technician,
            article=article,
            defaults={'quantity': Decimal('0')}
        )
        
        if stock.available_quantity < quantity:
            raise StockServiceError(
                _("Insufficient stock. Available: {available}, Requested: {requested}").format(
                    available=stock.available_quantity,
                    requested=quantity
                )
            )
        
        # Update stock
        old_quantity = stock.quantity
        stock.consume_stock(quantity)
        
        # Create movement record
        movement = StockMovement.objects.create(
            technician=technician,
            article=article,
            delta=-quantity,  # Negative for issue
            reason=MovementReason.ISSUE,
            linked_demande=linked_demande,
            location_text=location_text,
            performed_by=performed_by,
            balance_after=stock.quantity,
            notes=notes
        )
        
        # Log audit event
        AuditService.log_event(
            actor_user=performed_by,
            entity_type='StockMovement',
            entity_id=str(movement.id),
            action='issue_stock',
            after_data={
                'technician_id': str(technician.id),
                'article_reference': article.reference,
                'quantity_issued': str(quantity),
                'location': location_text,
                'balance_before': str(old_quantity),
                'balance_after': str(stock.quantity)
            }
        )
        
        # Check thresholds
        StockService._check_threshold_for_stock(stock)
        
        return movement
    
    @staticmethod
    @transaction.atomic
    def receive_stock(
        technician: Profile,
        article: Article,
        quantity: Decimal,
        performed_by: User,
        linked_demande=None,
        notes: str = ""
    ) -> StockMovement:
        """
        Receive stock into a technician's inventory.
        
        Args:
            technician: Technician receiving the stock
            article: Article being received
            quantity: Quantity to receive (positive number)
            performed_by: User performing the operation
            linked_demande: Related demand if applicable
            notes: Additional notes
        
        Returns:
            Created StockMovement record
        """
        if technician.role != 'TECH':
            raise StockServiceError(_("Only technicians can receive stock"))
        
        if quantity <= 0:
            raise StockServiceError(_("Receive quantity must be positive"))
        
        # Get or create stock record with locking
        stock, created = StockTech.objects.select_for_update().get_or_create(
            technician=technician,
            article=article,
            defaults={'quantity': Decimal('0')}
        )
        
        # Update stock
        old_quantity = stock.quantity
        stock.quantity += quantity
        stock.save(update_fields=['quantity', 'updated_at'])
        
        # Create movement record
        movement = StockMovement.objects.create(
            technician=technician,
            article=article,
            delta=quantity,  # Positive for receipt
            reason=MovementReason.RECEIPT,
            linked_demande=linked_demande,
            location_text="",
            performed_by=performed_by,
            balance_after=stock.quantity,
            notes=notes
        )
        
        # Log audit event
        AuditService.log_event(
            actor_user=performed_by,
            entity_type='StockMovement',
            entity_id=str(movement.id),
            action='receive_stock',
            after_data={
                'technician_id': str(technician.id),
                'article_reference': article.reference,
                'quantity_received': str(quantity),
                'balance_before': str(old_quantity),
                'balance_after': str(stock.quantity)
            }
        )
        
        return movement
    
    @staticmethod
    @transaction.atomic
    def adjust_stock(
        technician: Profile,
        article: Article,
        new_quantity: Decimal,
        reason: str,
        performed_by: User,
        notes: str = ""
    ) -> StockMovement:
        """
        Manual stock adjustment.
        
        Args:
            technician: Technician whose stock is being adjusted
            article: Article being adjusted
            new_quantity: New quantity after adjustment
            reason: Reason for adjustment
            performed_by: User performing the operation
            notes: Additional notes
        
        Returns:
            Created StockMovement record
        """
        if new_quantity < 0:
            raise StockServiceError(_("Stock quantity cannot be negative"))
        
        # Get or create stock record with locking
        stock, created = StockTech.objects.select_for_update().get_or_create(
            technician=technician,
            article=article,
            defaults={'quantity': Decimal('0')}
        )
        
        old_quantity = stock.quantity
        delta = new_quantity - old_quantity
        
        if delta == 0:
            raise StockServiceError(_("No change in quantity"))
        
        # Update stock
        stock.quantity = new_quantity
        stock.save(update_fields=['quantity', 'updated_at'])
        
        # Create movement record
        movement = StockMovement.objects.create(
            technician=technician,
            article=article,
            delta=delta,
            reason=MovementReason.ADJUST,
            location_text=reason,
            performed_by=performed_by,
            balance_after=stock.quantity,
            notes=notes
        )
        
        # Log audit event
        AuditService.log_event(
            actor_user=performed_by,
            entity_type='StockMovement',
            entity_id=str(movement.id),
            action='adjust_stock',
            after_data={
                'technician_id': str(technician.id),
                'article_reference': article.reference,
                'quantity_delta': str(delta),
                'balance_before': str(old_quantity),
                'balance_after': str(new_quantity),
                'reason': reason
            }
        )
        
        # Check thresholds if stock decreased
        if delta < 0:
            StockService._check_threshold_for_stock(stock)
        
        return movement
    
    @staticmethod
    @transaction.atomic
    def transfer_stock(
        from_technician: Profile,
        to_technician: Profile,
        article: Article,
        quantity: Decimal,
        performed_by: User,
        notes: str = ""
    ) -> tuple[StockMovement, StockMovement]:
        """
        Transfer stock between technicians.
        
        Args:
            from_technician: Source technician
            to_technician: Destination technician
            article: Article being transferred
            quantity: Quantity to transfer
            performed_by: User performing the operation
            notes: Additional notes
        
        Returns:
            Tuple of (issue_movement, receipt_movement)
        """
        if from_technician.role != 'TECH' or to_technician.role != 'TECH':
            raise StockServiceError(_("Both users must be technicians"))
        
        if from_technician == to_technician:
            raise StockServiceError(_("Cannot transfer to same technician"))
        
        if quantity <= 0:
            raise StockServiceError(_("Transfer quantity must be positive"))
        
        # Get source stock with locking
        try:
            from_stock = StockTech.objects.select_for_update().get(
                technician=from_technician,
                article=article
            )
        except StockTech.DoesNotExist:
            raise StockServiceError(_("Source technician has no stock for this article"))
        
        if from_stock.available_quantity < quantity:
            raise StockServiceError(_("Insufficient stock for transfer"))
        
        # Get or create destination stock with locking
        to_stock, created = StockTech.objects.select_for_update().get_or_create(
            technician=to_technician,
            article=article,
            defaults={'quantity': Decimal('0')}
        )
        
        # Perform transfer
        from_old_qty = from_stock.quantity
        to_old_qty = to_stock.quantity
        
        from_stock.consume_stock(quantity)
        to_stock.quantity += quantity
        to_stock.save(update_fields=['quantity', 'updated_at'])
        
        # Create movement records
        issue_movement = StockMovement.objects.create(
            technician=from_technician,
            article=article,
            delta=-quantity,
            reason=MovementReason.TRANSFER,
            location_text=f"Transfer to {to_technician.display_name}",
            performed_by=performed_by,
            balance_after=from_stock.quantity,
            notes=notes
        )
        
        receipt_movement = StockMovement.objects.create(
            technician=to_technician,
            article=article,
            delta=quantity,
            reason=MovementReason.TRANSFER,
            location_text=f"Transfer from {from_technician.display_name}",
            performed_by=performed_by,
            balance_after=to_stock.quantity,
            notes=notes
        )
        
        # Log audit events
        AuditService.log_event(
            actor_user=performed_by,
            entity_type='StockMovement',
            entity_id=str(issue_movement.id),
            action='transfer_stock_out',
            after_data={
                'from_technician_id': str(from_technician.id),
                'to_technician_id': str(to_technician.id),
                'article_reference': article.reference,
                'quantity': str(quantity),
                'from_balance_before': str(from_old_qty),
                'from_balance_after': str(from_stock.quantity)
            }
        )
        
        AuditService.log_event(
            actor_user=performed_by,
            entity_type='StockMovement',
            entity_id=str(receipt_movement.id),
            action='transfer_stock_in',
            after_data={
                'from_technician_id': str(from_technician.id),
                'to_technician_id': str(to_technician.id),
                'article_reference': article.reference,
                'quantity': str(quantity),
                'to_balance_before': str(to_old_qty),
                'to_balance_after': str(to_stock.quantity)
            }
        )
        
        # Check thresholds for source technician
        StockService._check_threshold_for_stock(from_stock)
        
        return issue_movement, receipt_movement
    
    @staticmethod
    def get_technician_stock(technician: Profile, include_zero: bool = False) -> List[Dict[str, Any]]:
        """
        Get all stock items for a technician.
        
        Args:
            technician: Technician to get stock for
            include_zero: Include items with zero quantity
        
        Returns:
            List of stock items with article details
        """
        query = StockTech.objects.select_related('article').filter(
            technician=technician
        )
        
        if not include_zero:
            query = query.filter(quantity__gt=0)
        
        stock_items = []
        for stock in query:
            stock_items.append({
                'article': {
                    'id': str(stock.article.id),
                    'reference': stock.article.reference,
                    'name': stock.article.name,
                    'description': stock.article.description,
                    'unit': stock.article.unit,
                    'category': stock.article.category,
                },
                'quantity': str(stock.quantity),
                'reserved_qty': str(stock.reserved_qty),
                'available_quantity': str(stock.available_quantity),
                'updated_at': stock.updated_at.isoformat(),
            })
        
        return stock_items
    
    @staticmethod
    def _check_threshold_for_stock(stock: StockTech) -> Optional[ThresholdAlert]:
        """
        Check if stock is below threshold and send alert if needed.
        
        Args:
            stock: StockTech instance to check
        
        Returns:
            ThresholdAlert if alert was sent, None otherwise
        """
        try:
            threshold = Threshold.objects.get(
                technician=stock.technician,
                article=stock.article,
                is_active=True
            )
        except Threshold.DoesNotExist:
            return None
        
        if not threshold.check_threshold():
            return None
        
        # Check if we already sent an alert recently (within 24 hours)
        if threshold.last_alert_sent:
            hours_since_last_alert = (
                timezone.now() - threshold.last_alert_sent
            ).total_seconds() / 3600
            if hours_since_last_alert < 24:
                return None
        
        # Create threshold alert
        alert = ThresholdAlert.objects.create(
            technician=stock.technician,
            article=stock.article,
            current_stock=stock.available_quantity,
            threshold_level=threshold.min_qty,
            alert_method='SYSTEM'
        )
        
        # Update threshold's last alert time
        threshold.last_alert_sent = timezone.now()
        threshold.save(update_fields=['last_alert_sent'])
        
        # Log audit event
        AuditService.log_event(
            actor_user=stock.technician.user,
            entity_type='ThresholdAlert',
            entity_id=str(alert.id),
            action='threshold_alert',
            after_data={
                'technician_id': str(stock.technician.id),
                'article_reference': stock.article.reference,
                'current_stock': str(stock.available_quantity),
                'threshold_level': str(threshold.min_qty)
            }
        )
        
        return alert
    
    @staticmethod
    def get_stock_movements(
        technician: Optional[Profile] = None,
        article: Optional[Article] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get stock movement history.
        
        Args:
            technician: Filter by technician
            article: Filter by article
            limit: Maximum number of movements to return
        
        Returns:
            List of stock movements
        """
        query = StockMovement.objects.select_related(
            'technician__user', 'article', 'performed_by'
        )
        
        if technician:
            query = query.filter(technician=technician)
        if article:
            query = query.filter(article=article)
        
        query = query.order_by('-timestamp')[:limit]
        
        movements = []
        for movement in query:
            movements.append({
                'id': str(movement.id),
                'technician': {
                    'id': str(movement.technician.id),
                    'name': movement.technician.display_name,
                },
                'article': {
                    'id': str(movement.article.id),
                    'reference': movement.article.reference,
                    'name': movement.article.name,
                },
                'delta': str(movement.delta),
                'reason': movement.reason,
                'location_text': movement.location_text,
                'balance_after': str(movement.balance_after),
                'performed_by': {
                    'id': movement.performed_by.id,
                    'username': movement.performed_by.username,
                    'full_name': movement.performed_by.get_full_name(),
                },
                'timestamp': movement.timestamp.isoformat(),
                'notes': movement.notes,
                'linked_demande_id': str(movement.linked_demande.id) if movement.linked_demande else None,
            })
        
        return movements
