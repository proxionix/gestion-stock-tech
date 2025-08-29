"""
API app configuration for Stock Management System.
"""
from django.apps import AppConfig


class ApiConfig(AppConfig):
    """API application configuration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.api'
    verbose_name = 'API'
