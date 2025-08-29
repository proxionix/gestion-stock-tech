"""
PWA app configuration for Stock Management System.
"""
from django.apps import AppConfig


class PwaConfig(AppConfig):
    """PWA application configuration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pwa'
    verbose_name = 'PWA'
