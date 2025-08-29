"""
Admin workflow service for Stock Management System.
Handles demand approval, preparation, and handover processes.
"""
import hashlib
import secrets
from decimal import Decimal
from typing import List, Dict, Any, Optional
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings
from apps.orders.models import Demande, DemandeLine, DemandeStatus, HandoverMethod
from apps.inventory.services.stock_service import StockService
from apps.users.models import Profile, PINCode
from apps.audit.services.audit_service import AuditService


class AdminWorkflowError(Exception):
    """Base exception for admin workflow errors."""
    pass


class AdminWorkflow:
    """Service class for admin workflow operations."""
    
    @staticmethod
    @transaction.atomic
    def approve_demand_full(demande: Demande, approved_by: User, notes: str = "") -> Demande:
        """
        Approve a demand in full (all requested quantities).
        
        Args:
            demande: Demand to approve
            approved_by: Admin user approving the demand
            notes: Additional approval notes
        
        Returns:
            Updated demand
        """
        if not approved_by.profile.is_admin:
            raise AdminWorkflowError(_("Only administrators can approve demands"))
        
        if demande.status != DemandeStatus.SUBMITTED:
            raise AdminWorkflowError(_("Only submitted demands can be approved"))
        
        # Approve all lines with full quantities
        old_status = demande.status
        for line in demande.lines.all():
            line.qty_approved = line.qty_requested
            line.save(update_fields=['qty_approved', 'updated_at'])
        
        # Update demand
        demande.status = DemandeStatus.APPROVED
        demande.approved_by = approved_by
        demande.approved_at = timezone.now()
        if notes:
            demande.notes = f"{demande.notes}\n\nApproval notes: {notes}".strip()
        demande.save(update_fields=['status', 'approved_by', 'approved_at', 'notes', 'updated_at'])
        
        # Log audit event
        AuditService.log_event(
            actor_user=approved_by,
            entity_type='Demande',
            entity_id=str(demande.id),
            action='approve_demand_full',
            before_data={'status': old_status},
            after_data={
                'status': demande.status,
                'approved_by_id': approved_by.id,
                'total_approved_quantity': str(demande.total_approved_quantity),
                'notes': notes
            }
        )
        
        return demande
    
    @staticmethod
    @transaction.atomic
    def approve_demand_partial(
        demande: Demande,
        approved_by: User,
        line_approvals: List[Dict[str, Any]],
        notes: str = ""
    ) -> Demande:
        """
        Approve a demand partially (specific quantities per line).
        
        Args:
            demande: Demand to approve
            approved_by: Admin user approving the demand
            line_approvals: List of {'line_id': str, 'qty_approved': Decimal}
            notes: Additional approval notes
        
        Returns:
            Updated demand
        """
        if not approved_by.profile.is_admin:
            raise AdminWorkflowError(_("Only administrators can approve demands"))
        
        if demande.status != DemandeStatus.SUBMITTED:
            raise AdminWorkflowError(_("Only submitted demands can be approved"))
        
        old_status = demande.status
        approved_lines = []
        
        # Process each line approval
        for approval in line_approvals:
            line_id = approval['line_id']
            qty_approved = Decimal(str(approval['qty_approved']))
            
            try:
                line = demande.lines.get(id=line_id)
            except DemandeLine.DoesNotExist:
                raise AdminWorkflowError(f"Demand line {line_id} not found")
            
            if qty_approved < 0:
                raise AdminWorkflowError(_("Approved quantity cannot be negative"))
            
            if qty_approved > line.qty_requested:
                raise AdminWorkflowError(
                    _("Approved quantity cannot exceed requested quantity for line {line_id}").format(
                        line_id=line_id
                    )
                )
            
            old_qty = line.qty_approved
            line.qty_approved = qty_approved
            line.save(update_fields=['qty_approved', 'updated_at'])
            
            approved_lines.append({
                'line_id': str(line.id),
                'article_reference': line.article.reference,
                'qty_requested': str(line.qty_requested),
                'qty_approved_before': str(old_qty),
                'qty_approved_after': str(qty_approved)
            })
        
        # Determine new status
        if demande.is_fully_approved:
            new_status = DemandeStatus.APPROVED
        elif demande.total_approved_quantity > 0:
            new_status = DemandeStatus.PARTIAL
        else:
            new_status = DemandeStatus.REFUSED
        
        # Update demand
        demande.status = new_status
        demande.approved_by = approved_by
        demande.approved_at = timezone.now()
        if notes:
            demande.notes = f"{demande.notes}\n\nApproval notes: {notes}".strip()
        demande.save(update_fields=['status', 'approved_by', 'approved_at', 'notes', 'updated_at'])
        
        # Log audit event
        AuditService.log_event(
            actor_user=approved_by,
            entity_type='Demande',
            entity_id=str(demande.id),
            action='approve_demand_partial',
            before_data={'status': old_status},
            after_data={
                'status': demande.status,
                'approved_by_id': approved_by.id,
                'total_approved_quantity': str(demande.total_approved_quantity),
                'approved_lines': approved_lines,
                'notes': notes
            }
        )
        
        return demande
    
    @staticmethod
    @transaction.atomic
    def refuse_demand(demande: Demande, refused_by: User, reason: str) -> Demande:
        """
        Refuse a demand completely.
        
        Args:
            demande: Demand to refuse
            refused_by: Admin user refusing the demand
            reason: Reason for refusal
        
        Returns:
            Updated demand
        """
        if not refused_by.profile.is_admin:
            raise AdminWorkflowError(_("Only administrators can refuse demands"))
        
        if demande.status != DemandeStatus.SUBMITTED:
            raise AdminWorkflowError(_("Only submitted demands can be refused"))
        
        old_status = demande.status
        
        # Set all approved quantities to 0
        for line in demande.lines.all():
            line.qty_approved = Decimal('0')
            line.save(update_fields=['qty_approved', 'updated_at'])
        
        # Update demand
        demande.status = DemandeStatus.REFUSED
        demande.approved_by = refused_by
        demande.approved_at = timezone.now()
        demande.refusal_reason = reason
        demande.save(update_fields=[
            'status', 'approved_by', 'approved_at', 'refusal_reason', 'updated_at'
        ])
        
        # Log audit event
        AuditService.log_event(
            actor_user=refused_by,
            entity_type='Demande',
            entity_id=str(demande.id),
            action='refuse_demand',
            before_data={'status': old_status},
            after_data={
                'status': demande.status,
                'refused_by_id': refused_by.id,
                'refusal_reason': reason
            }
        )
        
        return demande
    
    @staticmethod
    @transaction.atomic
    def prepare_demand(demande: Demande, prepared_by: User) -> Demande:
        """
        Prepare an approved demand by reserving stock.
        
        Args:
            demande: Demand to prepare
            prepared_by: Admin user preparing the demand
        
        Returns:
            Updated demand
        """
        if not prepared_by.profile.is_admin:
            raise AdminWorkflowError(_("Only administrators can prepare demands"))
        
        if not demande.can_be_prepared():
            raise AdminWorkflowError(_("Demand cannot be prepared"))
        
        old_status = demande.status
        prepared_lines = []
        
        # Reserve stock for each approved line
        for line in demande.lines.filter(qty_approved__gt=0):
            try:
                # Get or create stock record
                from apps.inventory.models import StockTech
                stock, created = StockTech.objects.select_for_update().get_or_create(
                    technician=demande.technician,
                    article=line.article,
                    defaults={'quantity': Decimal('0')}
                )
                
                # Reserve the approved quantity
                if stock.available_quantity >= line.qty_approved:
                    stock.reserve_quantity(line.qty_approved)
                    line.qty_prepared = line.qty_approved
                else:
                    # Partial preparation based on available stock
                    available = stock.available_quantity
                    if available > 0:
                        stock.reserve_quantity(available)
                        line.qty_prepared = available
                    else:
                        line.qty_prepared = Decimal('0')
                
                line.save(update_fields=['qty_prepared', 'updated_at'])
                
                prepared_lines.append({
                    'line_id': str(line.id),
                    'article_reference': line.article.reference,
                    'qty_approved': str(line.qty_approved),
                    'qty_prepared': str(line.qty_prepared),
                    'stock_available': str(stock.available_quantity + line.qty_prepared)
                })
                
            except Exception as e:
                raise AdminWorkflowError(
                    _("Failed to prepare line for article {article}: {error}").format(
                        article=line.article.reference,
                        error=str(e)
                    )
                )
        
        # Update demand
        demande.status = DemandeStatus.PREPARED
        demande.prepared_by = prepared_by
        demande.prepared_at = timezone.now()
        demande.save(update_fields=['status', 'prepared_by', 'prepared_at', 'updated_at'])
        
        # Log audit event
        AuditService.log_event(
            actor_user=prepared_by,
            entity_type='Demande',
            entity_id=str(demande.id),
            action='prepare_demand',
            before_data={'status': old_status},
            after_data={
                'status': demande.status,
                'prepared_by_id': prepared_by.id,
                'prepared_lines': prepared_lines
            }
        )
        
        return demande
    
    @staticmethod
    @transaction.atomic
    def handover_demand(
        demande: Demande,
        method: str,
        device_info: Dict[str, Any],
        performed_by: User,
        pin: Optional[str] = None,
        signature_data: Optional[str] = None
    ) -> Demande:
        """
        Complete handover of a prepared demand.
        
        Args:
            demande: Demand to hand over
            method: Handover method (PIN or SIGNATURE)
            device_info: Device information for handover
            performed_by: User performing the handover
            pin: PIN code if using PIN method
            signature_data: Base64 signature data if using signature method
        
        Returns:
            Updated demand
        """
        if not demande.can_be_handed_over():
            raise AdminWorkflowError(_("Demand cannot be handed over"))
        
        if method not in [HandoverMethod.PIN, HandoverMethod.SIGNATURE]:
            raise AdminWorkflowError(_("Invalid handover method"))
        
        old_status = demande.status
        
        # Validate handover method
        if method == HandoverMethod.PIN:
            if not pin:
                raise AdminWorkflowError(_("PIN is required for PIN handover"))
            AdminWorkflow._validate_pin(demande, pin)
        elif method == HandoverMethod.SIGNATURE:
            if not signature_data:
                raise AdminWorkflowError(_("Signature is required for signature handover"))
            AdminWorkflow._validate_signature(signature_data)
        
        # Process stock movements for each prepared line
        movements = []
        for line in demande.lines.filter(qty_prepared__gt=0):
            movement = StockService.receive_stock(
                technician=demande.technician,
                article=line.article,
                quantity=line.qty_prepared,
                performed_by=performed_by,
                linked_demande=demande,
                notes=f"Handover via {method}"
            )
            movements.append({
                'movement_id': str(movement.id),
                'article_reference': line.article.reference,
                'quantity': str(line.qty_prepared)
            })
        
        # Prepare handover data
        handover_data = {
            'method': method,
            'timestamp': timezone.now().isoformat(),
            'device_info': device_info,
            'performed_by_id': performed_by.id,
        }
        
        if method == HandoverMethod.PIN:
            handover_data['pin_verified'] = True
        elif method == HandoverMethod.SIGNATURE:
            handover_data['signature_data'] = signature_data
        
        # Update demand
        demande.status = DemandeStatus.HANDED_OVER
        demande.handover_method = method
        demande.handover_data = handover_data
        demande.handed_over_at = timezone.now()
        demande.save(update_fields=[
            'status', 'handover_method', 'handover_data', 'handed_over_at', 'updated_at'
        ])
        
        # Mark PIN as used if applicable
        if method == HandoverMethod.PIN:
            AdminWorkflow._mark_pin_used(demande, pin)
        
        # Log audit event
        AuditService.log_event(
            actor_user=performed_by,
            entity_type='Demande',
            entity_id=str(demande.id),
            action='handover_demand',
            before_data={'status': old_status},
            after_data={
                'status': demande.status,
                'handover_method': method,
                'movements': movements,
                'device_info': device_info
            }
        )
        
        # Auto-close demand if fully consumed
        if AdminWorkflow._should_auto_close(demande):
            AdminWorkflow.close_demand(demande, performed_by, "Auto-closed after handover")
        
        return demande
    
    @staticmethod
    @transaction.atomic
    def close_demand(demande: Demande, closed_by: User, reason: str = "") -> Demande:
        """
        Close a handed over demand.
        
        Args:
            demande: Demand to close
            closed_by: User closing the demand
            reason: Reason for closing
        
        Returns:
            Updated demand
        """
        if demande.status != DemandeStatus.HANDED_OVER:
            raise AdminWorkflowError(_("Only handed over demands can be closed"))
        
        old_status = demande.status
        
        # Update demand
        demande.status = DemandeStatus.CLOSED
        demande.closed_at = timezone.now()
        if reason:
            demande.notes = f"{demande.notes}\n\nClosure reason: {reason}".strip()
        demande.save(update_fields=['status', 'closed_at', 'notes', 'updated_at'])
        
        # Log audit event
        AuditService.log_event(
            actor_user=closed_by,
            entity_type='Demande',
            entity_id=str(demande.id),
            action='close_demand',
            before_data={'status': old_status},
            after_data={
                'status': demande.status,
                'closed_by_id': closed_by.id,
                'reason': reason
            }
        )
        
        return demande
    
    @staticmethod
    def generate_pin(demande: Demande) -> str:
        """
        Generate a PIN code for demand handover.
        
        Args:
            demande: Demand for which to generate PIN
        
        Returns:
            Generated PIN code (plain text)
        """
        pin_length = settings.STOCK_SYSTEM['PIN_LENGTH']
        pin_expiry_minutes = settings.STOCK_SYSTEM['PIN_EXPIRY_MINUTES']
        
        # Generate random PIN
        pin = ''.join(secrets.choice('0123456789') for _ in range(pin_length))
        
        # Hash the PIN
        pin_hash = hashlib.pbkdf2_hmac('sha256', pin.encode(), b'stock_system_salt', 100000)
        
        # Calculate expiry time
        expires_at = timezone.now() + timezone.timedelta(minutes=pin_expiry_minutes)
        
        # Save PIN record
        PINCode.objects.create(
            user=demande.technician.user,
            pin_hash=pin_hash.hex(),
            demande_id=demande.id,
            expires_at=expires_at
        )
        
        return pin
    
    @staticmethod
    def _validate_pin(demande: Demande, pin: str) -> bool:
        """Validate PIN code for demand handover."""
        pin_hash = hashlib.pbkdf2_hmac('sha256', pin.encode(), b'stock_system_salt', 100000)
        
        try:
            pin_record = PINCode.objects.get(
                user=demande.technician.user,
                demande_id=demande.id,
                pin_hash=pin_hash.hex(),
                is_used=False
            )
        except PINCode.DoesNotExist:
            raise AdminWorkflowError(_("Invalid PIN"))
        
        if pin_record.is_expired:
            raise AdminWorkflowError(_("PIN has expired"))
        
        return True
    
    @staticmethod
    def _mark_pin_used(demande: Demande, pin: str) -> None:
        """Mark PIN as used."""
        pin_hash = hashlib.pbkdf2_hmac('sha256', pin.encode(), b'stock_system_salt', 100000)
        
        pin_record = PINCode.objects.get(
            user=demande.technician.user,
            demande_id=demande.id,
            pin_hash=pin_hash.hex(),
            is_used=False
        )
        
        pin_record.is_used = True
        pin_record.used_at = timezone.now()
        pin_record.save(update_fields=['is_used', 'used_at'])
    
    @staticmethod
    def _validate_signature(signature_data: str) -> bool:
        """Validate signature data."""
        import base64
        
        try:
            # Decode base64 signature
            signature_bytes = base64.b64decode(signature_data)
            
            # Check size limit
            max_size = settings.STOCK_SYSTEM['SIGNATURE_MAX_SIZE']
            if len(signature_bytes) > max_size:
                raise AdminWorkflowError(_("Signature file too large"))
            
            return True
        except Exception:
            raise AdminWorkflowError(_("Invalid signature data"))
    
    @staticmethod
    def _should_auto_close(demande: Demande) -> bool:
        """Check if demand should be auto-closed."""
        # Auto-close if all prepared quantities were handed over
        return demande.status == DemandeStatus.HANDED_OVER
    
    @staticmethod
    def get_demands_queue(status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get demands queue for admin review.
        
        Args:
            status: Filter by status
        
        Returns:
            List of demands with summary information
        """
        query = Demande.objects.select_related(
            'technician__user', 'approved_by', 'prepared_by'
        ).prefetch_related('lines__article')
        
        if status:
            query = query.filter(status=status)
        else:
            # Show active demands that need admin attention
            query = query.filter(
                status__in=[
                    DemandeStatus.SUBMITTED,
                    DemandeStatus.APPROVED,
                    DemandeStatus.PARTIAL,
                    DemandeStatus.PREPARED
                ]
            )
        
        query = query.order_by('priority', 'created_at')
        
        demands = []
        for demande in query:
            demands.append({
                'id': str(demande.id),
                'technician': {
                    'id': str(demande.technician.id),
                    'name': demande.technician.display_name,
                    'employee_id': demande.technician.employee_id,
                },
                'status': demande.status,
                'priority': demande.priority,
                'total_requested_items': demande.total_requested_items,
                'total_requested_quantity': str(demande.total_requested_quantity),
                'total_approved_quantity': str(demande.total_approved_quantity),
                'created_at': demande.created_at.isoformat(),
                'updated_at': demande.updated_at.isoformat(),
                'approved_by': {
                    'id': demande.approved_by.id,
                    'username': demande.approved_by.username,
                } if demande.approved_by else None,
                'approved_at': demande.approved_at.isoformat() if demande.approved_at else None,
                'can_be_prepared': demande.can_be_prepared(),
                'can_be_handed_over': demande.can_be_handed_over(),
                'lines_summary': [
                    {
                        'article_reference': line.article.reference,
                        'article_name': line.article.name,
                        'qty_requested': str(line.qty_requested),
                        'qty_approved': str(line.qty_approved),
                        'qty_prepared': str(line.qty_prepared),
                    }
                    for line in demande.lines.all()
                ]
            })
        
        return demands
