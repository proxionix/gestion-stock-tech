"""
Threshold service for Stock Management System.
Handles stock threshold monitoring and alerting.
"""
from typing import List, Dict, Any, Optional
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from apps.inventory.models import Article, StockTech, Threshold
from apps.users.models import Profile
from apps.audit.models import ThresholdAlert
from apps.audit.services.audit_service import AuditService


class ThresholdService:
    """Service class for stock threshold management."""
    
    @staticmethod
    @transaction.atomic
    def create_or_update_threshold(
        technician: Profile,
        article: Article,
        min_qty: float,
        is_active: bool = True,
        created_by: Optional[User] = None
    ) -> Threshold:
        """
        Create or update a stock threshold for a technician.
        
        Args:
            technician: Technician for the threshold
            article: Article for the threshold
            min_qty: Minimum quantity threshold
            is_active: Whether the threshold is active
            created_by: User creating/updating the threshold
        
        Returns:
            Created or updated Threshold instance
        """
        if technician.role != 'TECH':
            raise ValueError(_("Only technicians can have thresholds"))
        
        if min_qty < 0:
            raise ValueError(_("Minimum quantity cannot be negative"))
        
        threshold, created = Threshold.objects.update_or_create(
            technician=technician,
            article=article,
            defaults={
                'min_qty': min_qty,
                'is_active': is_active,
            }
        )
        
        # Log audit event
        if created_by:
            action = 'create_threshold' if created else 'update_threshold'
            AuditService.log_event(
                actor_user=created_by,
                entity_type='Threshold',
                entity_id=str(threshold.id),
                action=action,
                after_data={
                    'technician_id': str(technician.id),
                    'article_reference': article.reference,
                    'min_qty': str(min_qty),
                    'is_active': is_active
                }
            )
        
        return threshold
    
    @staticmethod
    def check_all_thresholds() -> List[ThresholdAlert]:
        """
        Check all active thresholds and create alerts as needed.
        
        Returns:
            List of alerts created
        """
        active_thresholds = Threshold.objects.filter(
            is_active=True
        ).select_related('technician__user', 'article')
        
        alerts_created = []
        
        for threshold in active_thresholds:
            try:
                # Get current stock
                stock = StockTech.objects.get(
                    technician=threshold.technician,
                    article=threshold.article
                )
                current_qty = stock.available_quantity
            except StockTech.DoesNotExist:
                current_qty = 0
            
            # Check if below threshold
            if current_qty <= threshold.min_qty:
                alert = ThresholdService._create_alert_if_needed(
                    threshold, current_qty
                )
                if alert:
                    alerts_created.append(alert)
        
        return alerts_created
    
    @staticmethod
    def check_technician_thresholds(technician: Profile) -> List[ThresholdAlert]:
        """
        Check thresholds for a specific technician.
        
        Args:
            technician: Technician to check thresholds for
        
        Returns:
            List of alerts created
        """
        if technician.role != 'TECH':
            return []
        
        thresholds = Threshold.objects.filter(
            technician=technician,
            is_active=True
        ).select_related('article')
        
        alerts_created = []
        
        for threshold in thresholds:
            try:
                stock = StockTech.objects.get(
                    technician=technician,
                    article=threshold.article
                )
                current_qty = stock.available_quantity
            except StockTech.DoesNotExist:
                current_qty = 0
            
            if current_qty <= threshold.min_qty:
                alert = ThresholdService._create_alert_if_needed(
                    threshold, current_qty
                )
                if alert:
                    alerts_created.append(alert)
        
        return alerts_created
    
    @staticmethod
    def check_article_thresholds(article: Article) -> List[ThresholdAlert]:
        """
        Check thresholds for a specific article across all technicians.
        
        Args:
            article: Article to check thresholds for
        
        Returns:
            List of alerts created
        """
        thresholds = Threshold.objects.filter(
            article=article,
            is_active=True
        ).select_related('technician__user')
        
        alerts_created = []
        
        for threshold in thresholds:
            try:
                stock = StockTech.objects.get(
                    technician=threshold.technician,
                    article=article
                )
                current_qty = stock.available_quantity
            except StockTech.DoesNotExist:
                current_qty = 0
            
            if current_qty <= threshold.min_qty:
                alert = ThresholdService._create_alert_if_needed(
                    threshold, current_qty
                )
                if alert:
                    alerts_created.append(alert)
        
        return alerts_created
    
    @staticmethod
    def _create_alert_if_needed(threshold: Threshold, current_qty: float) -> Optional[ThresholdAlert]:
        """
        Create a threshold alert if one hasn't been sent recently.
        
        Args:
            threshold: Threshold that was crossed
            current_qty: Current stock quantity
        
        Returns:
            Created alert or None if no alert was needed
        """
        # Check if we already sent an alert recently (within 24 hours)
        if threshold.last_alert_sent:
            hours_since_last_alert = (
                timezone.now() - threshold.last_alert_sent
            ).total_seconds() / 3600
            if hours_since_last_alert < 24:
                return None
        
        # Create threshold alert
        alert = ThresholdAlert.objects.create(
            technician=threshold.technician,
            article=threshold.article,
            current_stock=current_qty,
            threshold_level=threshold.min_qty,
            alert_method='SYSTEM'
        )
        
        # Update threshold's last alert time
        threshold.last_alert_sent = timezone.now()
        threshold.save(update_fields=['last_alert_sent'])
        
        # Log audit event
        AuditService.log_event(
            actor_user=threshold.technician.user,
            entity_type='ThresholdAlert',
            entity_id=str(alert.id),
            action='threshold_alert_created',
            after_data={
                'technician_id': str(threshold.technician.id),
                'article_reference': threshold.article.reference,
                'current_stock': str(current_qty),
                'threshold_level': str(threshold.min_qty),
                'alert_method': alert.alert_method
            }
        )
        
        return alert
    
    @staticmethod
    def get_threshold_status(technician: Profile) -> List[Dict[str, Any]]:
        """
        Get threshold status for a technician.
        
        Args:
            technician: Technician to get status for
        
        Returns:
            List of threshold status information
        """
        if technician.role != 'TECH':
            return []
        
        thresholds = Threshold.objects.filter(
            technician=technician,
            is_active=True
        ).select_related('article')
        
        status_list = []
        
        for threshold in thresholds:
            try:
                stock = StockTech.objects.get(
                    technician=technician,
                    article=threshold.article
                )
                current_qty = stock.available_quantity
                has_stock = True
            except StockTech.DoesNotExist:
                current_qty = 0
                has_stock = False
            
            is_below_threshold = current_qty <= threshold.min_qty
            
            status_list.append({
                'threshold_id': str(threshold.id),
                'article': {
                    'id': str(threshold.article.id),
                    'reference': threshold.article.reference,
                    'name': threshold.article.name,
                    'unit': threshold.article.unit,
                },
                'threshold_level': str(threshold.min_qty),
                'current_stock': str(current_qty),
                'has_stock': has_stock,
                'is_below_threshold': is_below_threshold,
                'last_alert_sent': threshold.last_alert_sent.isoformat() if threshold.last_alert_sent else None,
                'updated_at': threshold.updated_at.isoformat(),
            })
        
        return status_list
    
    @staticmethod
    def get_active_alerts(
        technician: Optional[Profile] = None,
        acknowledged: Optional[bool] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get active threshold alerts.
        
        Args:
            technician: Filter by technician (optional)
            acknowledged: Filter by acknowledgment status (optional)
            limit: Maximum number of alerts to return
        
        Returns:
            List of threshold alerts
        """
        query = ThresholdAlert.objects.select_related(
            'technician__user', 'article'
        )
        
        if technician:
            query = query.filter(technician=technician)
        if acknowledged is not None:
            query = query.filter(acknowledged=acknowledged)
        
        query = query.order_by('-alert_sent_at')[:limit]
        
        alerts = []
        for alert in query:
            alerts.append({
                'id': str(alert.id),
                'technician': {
                    'id': str(alert.technician.id),
                    'name': alert.technician.display_name,
                    'employee_id': alert.technician.employee_id,
                },
                'article': {
                    'id': str(alert.article.id),
                    'reference': alert.article.reference,
                    'name': alert.article.name,
                    'unit': alert.article.unit,
                },
                'current_stock': str(alert.current_stock),
                'threshold_level': str(alert.threshold_level),
                'alert_method': alert.alert_method,
                'alert_sent_at': alert.alert_sent_at.isoformat(),
                'acknowledged': alert.acknowledged,
                'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            })
        
        return alerts
    
    @staticmethod
    @transaction.atomic
    def acknowledge_alert(alert_id: str, acknowledged_by: User) -> ThresholdAlert:
        """
        Acknowledge a threshold alert.
        
        Args:
            alert_id: ID of the alert to acknowledge
            acknowledged_by: User acknowledging the alert
        
        Returns:
            Updated alert
        """
        try:
            alert = ThresholdAlert.objects.get(id=alert_id)
        except ThresholdAlert.DoesNotExist:
            raise ValueError(_("Alert not found"))
        
        if alert.acknowledged:
            raise ValueError(_("Alert already acknowledged"))
        
        alert.acknowledged = True
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=['acknowledged', 'acknowledged_at'])
        
        # Log audit event
        AuditService.log_event(
            actor_user=acknowledged_by,
            entity_type='ThresholdAlert',
            entity_id=str(alert.id),
            action='acknowledge_alert',
            after_data={
                'acknowledged_by_id': acknowledged_by.id,
                'acknowledged_at': alert.acknowledged_at.isoformat()
            }
        )
        
        return alert
    
    @staticmethod
    def get_threshold_summary() -> Dict[str, Any]:
        """
        Get overall threshold monitoring summary.
        
        Returns:
            Summary statistics
        """
        total_thresholds = Threshold.objects.filter(is_active=True).count()
        
        # Count thresholds currently below threshold
        below_threshold_count = 0
        recent_alerts_count = ThresholdAlert.objects.filter(
            alert_sent_at__gte=timezone.now() - timezone.timedelta(hours=24),
            acknowledged=False
        ).count()
        
        active_thresholds = Threshold.objects.filter(
            is_active=True
        ).select_related('technician', 'article')
        
        for threshold in active_thresholds:
            try:
                stock = StockTech.objects.get(
                    technician=threshold.technician,
                    article=threshold.article
                )
                if stock.available_quantity <= threshold.min_qty:
                    below_threshold_count += 1
            except StockTech.DoesNotExist:
                below_threshold_count += 1
        
        return {
            'total_active_thresholds': total_thresholds,
            'below_threshold_count': below_threshold_count,
            'recent_unacknowledged_alerts': recent_alerts_count,
            'last_check_time': timezone.now().isoformat(),
        }
