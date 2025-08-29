"""
Celery tasks for inventory management.
"""
import logging
from celery import shared_task
from django.utils import timezone
from apps.inventory.services.threshold_service import ThresholdService

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def check_stock_thresholds(self):
    """
    Periodic task to check all stock thresholds and send alerts.
    """
    try:
        logger.info("Starting stock threshold check")
        
        alerts_created = ThresholdService.check_all_thresholds()
        
        logger.info(
            f"Stock threshold check completed. Created {len(alerts_created)} alerts",
            extra={
                'task_id': self.request.id,
                'alerts_count': len(alerts_created),
                'event_type': 'threshold_check_completed'
            }
        )
        
        return {
            'status': 'success',
            'alerts_created': len(alerts_created),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(
            f"Stock threshold check failed: {str(e)}",
            extra={
                'task_id': self.request.id,
                'error': str(e),
                'event_type': 'threshold_check_failed'
            },
            exc_info=True
        )
        
        # Retry up to 3 times with exponential backoff
        if self.request.retries < 3:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def cleanup_old_qr_files():
    """
    Cleanup orphaned QR code files.
    """
    try:
        import os
        from django.conf import settings
        from apps.inventory.models import ArticleQR
        
        logger.info("Starting QR files cleanup")
        
        qr_directory = os.path.join(settings.MEDIA_ROOT, 'qr_codes')
        if not os.path.exists(qr_directory):
            return {'status': 'success', 'files_deleted': 0}
        
        deleted_count = 0
        
        # Get all QR files in database
        db_files = set()
        for qr in ArticleQR.objects.all():
            if qr.png_file:
                db_files.add(os.path.basename(qr.png_file.name))
        
        # Check files in directory
        for root, dirs, files in os.walk(qr_directory):
            for file in files:
                if file.endswith('.png') and file not in db_files:
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.debug(f"Deleted orphaned QR file: {file}")
                    except OSError as e:
                        logger.warning(f"Failed to delete QR file {file}: {e}")
        
        logger.info(f"QR files cleanup completed. Deleted {deleted_count} orphaned files")
        
        return {
            'status': 'success',
            'files_deleted': deleted_count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"QR files cleanup failed: {str(e)}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
