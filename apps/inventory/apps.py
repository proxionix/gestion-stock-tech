"""
Inventory app configuration for Stock Management System.
"""
from django.apps import AppConfig


class InventoryConfig(AppConfig):
    """Inventory application configuration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.inventory'
    verbose_name = 'Inventory'
    
    def ready(self):
        """Initialize app when Django starts."""
        from . import signals  # Import signal handlers
