"""
Celery configuration for Stock Management System.
"""
import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

app = Celery('stock_system')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery beat schedule for periodic tasks
app.conf.beat_schedule = {
    'check-stock-thresholds': {
        'task': 'apps.inventory.tasks.check_stock_thresholds',
        'schedule': settings.STOCK_SYSTEM['THRESHOLD_CHECK_INTERVAL'],
    },
    'cleanup-expired-pins': {
        'task': 'apps.orders.tasks.cleanup_expired_pins',
        'schedule': 300.0,  # Every 5 minutes
    },
    'audit-integrity-check': {
        'task': 'apps.audit.tasks.verify_audit_chain',
        'schedule': 3600.0,  # Every hour
    },
}

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f'Request: {self.request!r}')
