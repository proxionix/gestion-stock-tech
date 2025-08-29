"""
Celery tasks for orders management.
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
from apps.users.models import PINCode

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_pins():
    """
    Cleanup expired PIN codes.
    """
    try:
        logger.info("Starting expired PIN cleanup")
        
        expired_pins = PINCode.objects.filter(
            expires_at__lt=timezone.now(),
            is_used=False
        )
        
        expired_count = expired_pins.count()
        expired_pins.delete()
        
        logger.info(
            f"Expired PIN cleanup completed. Deleted {expired_count} expired PINs",
            extra={
                'expired_count': expired_count,
                'event_type': 'pin_cleanup_completed'
            }
        )
        
        return {
            'status': 'success',
            'expired_pins_deleted': expired_count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Expired PIN cleanup failed: {str(e)}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def send_demand_notifications():
    """
    Send notifications for pending demands.
    This is a placeholder for email/SMS notifications.
    """
    try:
        from apps.orders.models import Demande, DemandeStatus
        
        logger.info("Starting demand notifications check")
        
        # Get demands that need admin attention
        pending_demands = Demande.objects.filter(
            status=DemandeStatus.SUBMITTED
        ).select_related('technician__user')
        
        # Get demands that have been sitting too long
        old_threshold = timezone.now() - timezone.timedelta(hours=24)
        old_demands = pending_demands.filter(created_at__lt=old_threshold)
        
        notifications_sent = 0
        
        for demand in old_demands:
            # In a real implementation, send email/SMS here
            logger.info(
                f"Old demand notification: {demand.id} from {demand.technician.display_name}",
                extra={
                    'demand_id': str(demand.id),
                    'technician_id': str(demand.technician.id),
                    'age_hours': (timezone.now() - demand.created_at).total_seconds() / 3600,
                    'event_type': 'demand_notification'
                }
            )
            notifications_sent += 1
        
        logger.info(
            f"Demand notifications completed. Sent {notifications_sent} notifications",
            extra={
                'notifications_sent': notifications_sent,
                'total_pending': pending_demands.count(),
                'event_type': 'demand_notifications_completed'
            }
        )
        
        return {
            'status': 'success',
            'notifications_sent': notifications_sent,
            'total_pending_demands': pending_demands.count(),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Demand notifications failed: {str(e)}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def auto_close_old_demands():
    """
    Auto-close demands that have been handed over for too long.
    """
    try:
        from apps.orders.models import Demande, DemandeStatus
        from apps.orders.services.admin_workflow import AdminWorkflow
        
        logger.info("Starting auto-close old demands")
        
        # Get demands handed over more than 30 days ago
        cutoff_date = timezone.now() - timezone.timedelta(days=30)
        old_demands = Demande.objects.filter(
            status=DemandeStatus.HANDED_OVER,
            handed_over_at__lt=cutoff_date
        )
        
        closed_count = 0
        system_user = User.objects.filter(is_superuser=True).first()
        
        if not system_user:
            logger.warning("No superuser found for auto-closing demands")
            return {
                'status': 'failed',
                'error': 'No system user available',
                'timestamp': timezone.now().isoformat()
            }
        
        for demand in old_demands:
            try:
                AdminWorkflow.close_demand(
                    demand, 
                    system_user, 
                    "Auto-closed after 30 days"
                )
                closed_count += 1
                logger.info(f"Auto-closed old demand: {demand.id}")
            except Exception as e:
                logger.warning(f"Failed to auto-close demand {demand.id}: {e}")
        
        logger.info(
            f"Auto-close completed. Closed {closed_count} old demands",
            extra={
                'closed_count': closed_count,
                'event_type': 'auto_close_completed'
            }
        )
        
        return {
            'status': 'success',
            'demands_closed': closed_count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Auto-close old demands failed: {str(e)}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
