"""
Celery tasks for audit management.
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from apps.audit.services.audit_service import AuditService
from apps.audit.models import EventLog

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def verify_audit_chain(self):
    """
    Periodic task to verify audit chain integrity.
    """
    try:
        logger.info("Starting audit chain verification")
        
        # Verify the entire chain
        result = AuditService.verify_audit_chain()
        
        if result['valid']:
            logger.info(
                f"Audit chain verification completed successfully. "
                f"Verified {result['verified_records']}/{result['total_records']} records",
                extra={
                    'task_id': self.request.id,
                    'total_records': result['total_records'],
                    'verified_records': result['verified_records'],
                    'valid': True,
                    'event_type': 'audit_verification_completed'
                }
            )
        else:
            logger.error(
                f"Audit chain verification failed. "
                f"Found {len(result['errors'])} errors in {result['total_records']} records",
                extra={
                    'task_id': self.request.id,
                    'total_records': result['total_records'],
                    'verified_records': result['verified_records'],
                    'valid': False,
                    'errors': result['errors'],
                    'event_type': 'audit_verification_failed'
                }
            )
        
        return {
            'status': 'success' if result['valid'] else 'failed',
            'total_records': result['total_records'],
            'verified_records': result['verified_records'],
            'valid': result['valid'],
            'errors': result['errors'],
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(
            f"Audit chain verification task failed: {str(e)}",
            extra={
                'task_id': self.request.id,
                'error': str(e),
                'event_type': 'audit_verification_task_failed'
            },
            exc_info=True
        )
        
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def cleanup_old_audit_records():
    """
    Cleanup old audit records based on retention policy.
    Only removes records older than the configured retention period.
    """
    try:
        logger.info("Starting old audit records cleanup")
        
        retention_days = settings.STOCK_SYSTEM['DATA_RETENTION_DAYS']
        cutoff_date = timezone.now() - timezone.timedelta(days=retention_days)
        
        # Count records to be deleted
        old_events = EventLog.objects.filter(timestamp__lt=cutoff_date)
        old_count = old_events.count()
        
        if old_count == 0:
            logger.info("No old audit records to cleanup")
            return {
                'status': 'success',
                'records_deleted': 0,
                'retention_days': retention_days,
                'timestamp': timezone.now().isoformat()
            }
        
        # In a real system, you might want to archive before deleting
        # For now, we'll just log what would be deleted
        logger.info(
            f"Would delete {old_count} audit records older than {retention_days} days",
            extra={
                'old_count': old_count,
                'retention_days': retention_days,
                'cutoff_date': cutoff_date.isoformat(),
                'event_type': 'audit_cleanup_simulated'
            }
        )
        
        # Uncomment the next line to actually delete old records
        # deleted_count = old_events.delete()[0]
        deleted_count = 0  # Simulated deletion
        
        logger.info(
            f"Audit records cleanup completed. Deleted {deleted_count} old records",
            extra={
                'deleted_count': deleted_count,
                'retention_days': retention_days,
                'event_type': 'audit_cleanup_completed'
            }
        )
        
        return {
            'status': 'success',
            'records_deleted': deleted_count,
            'retention_days': retention_days,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Audit records cleanup failed: {str(e)}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def generate_audit_report():
    """
    Generate periodic audit reports.
    """
    try:
        logger.info("Starting audit report generation")
        
        # Generate summary statistics
        total_events = EventLog.objects.count()
        
        # Events by action type in last 24 hours
        since_yesterday = timezone.now() - timezone.timedelta(hours=24)
        recent_events = EventLog.objects.filter(timestamp__gte=since_yesterday)
        
        action_counts = {}
        for event in recent_events.values('action'):
            action = event['action']
            action_counts[action] = action_counts.get(action, 0) + 1
        
        # Users activity in last 24 hours
        active_users = recent_events.values_list('actor_user_id', flat=True).distinct().count()
        
        report_data = {
            'total_audit_events': total_events,
            'events_last_24h': recent_events.count(),
            'active_users_last_24h': active_users,
            'action_breakdown_24h': action_counts,
            'report_generated_at': timezone.now().isoformat()
        }
        
        logger.info(
            f"Audit report generated: {recent_events.count()} events in last 24h, "
            f"{active_users} active users",
            extra={
                **report_data,
                'event_type': 'audit_report_generated'
            }
        )
        
        return {
            'status': 'success',
            'report': report_data,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Audit report generation failed: {str(e)}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def export_audit_data_for_user(user_id, start_date=None, end_date=None):
    """
    Export audit data for GDPR compliance.
    
    Args:
        user_id: ID of user to export data for
        start_date: Start date for export (ISO format)
        end_date: End date for export (ISO format)
    """
    try:
        from django.contrib.auth.models import User
        from datetime import datetime
        
        logger.info(f"Starting audit data export for user {user_id}")
        
        user = User.objects.get(id=user_id)
        
        # Parse dates if provided
        start_dt = datetime.fromisoformat(start_date) if start_date else None
        end_dt = datetime.fromisoformat(end_date) if end_date else None
        
        # Export audit data
        audit_data = AuditService.export_audit_data(
            start_date=start_dt,
            end_date=end_dt,
            user_id=user_id
        )
        
        logger.info(
            f"Audit data export completed for user {user_id}. "
            f"Exported {len(audit_data)} records",
            extra={
                'user_id': user_id,
                'username': user.username,
                'records_exported': len(audit_data),
                'start_date': start_date,
                'end_date': end_date,
                'event_type': 'audit_data_exported'
            }
        )
        
        # In a real implementation, you would save this to a file
        # and provide a download link to the user
        
        return {
            'status': 'success',
            'user_id': user_id,
            'records_exported': len(audit_data),
            'start_date': start_date,
            'end_date': end_date,
            'timestamp': timezone.now().isoformat()
        }
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for audit export")
        return {
            'status': 'failed',
            'error': f'User {user_id} not found',
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Audit data export failed for user {user_id}: {str(e)}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
            'user_id': user_id,
            'timestamp': timezone.now().isoformat()
        }
