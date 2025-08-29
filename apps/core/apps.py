"""
Core app configuration for Stock Management System.
"""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Core application configuration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Core'
    
    def ready(self):
        """Initialize app when Django starts."""
        # Import signal handlers if any
        pass
