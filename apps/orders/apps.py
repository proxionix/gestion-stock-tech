"""
Orders app configuration for Stock Management System.
"""
from django.apps import AppConfig


class OrdersConfig(AppConfig):
    """Orders application configuration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.orders'
    verbose_name = 'Orders'
