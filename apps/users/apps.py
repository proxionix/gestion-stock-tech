"""
Users app configuration for Stock Management System.
"""
from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Users application configuration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'
    verbose_name = 'Users'
    
    def ready(self):
        """Initialize app when Django starts."""
        from . import signals  # Import signal handlers
