"""
Audit app configuration for Stock Management System.
"""
from django.apps import AppConfig


class AuditConfig(AppConfig):
    """Audit application configuration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.audit'
    verbose_name = 'Audit'
