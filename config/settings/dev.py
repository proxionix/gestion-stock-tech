"""
Development settings for Stock Management System.
"""
from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Allow all hosts in development
ALLOWED_HOSTS = ['*']

# Database - use environment or default SQLite for dev
if not env('DATABASE_URL', default=''):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Disable security features for development
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# CORS - allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True

# Email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Debug toolbar for development
INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]

# Additional development apps
INSTALLED_APPS += [
    'django_extensions',
]

# Relaxed throttling for development
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '1000/hour',
    'user': '10000/hour'
}

# Less strict logging in development
LOGGING['loggers']['django']['level'] = 'DEBUG'
LOGGING['loggers']['apps']['level'] = 'DEBUG'

# Create logs directory if it doesn't exist
import os
logs_dir = BASE_DIR / 'logs'
if not logs_dir.exists():
    logs_dir.mkdir(exist_ok=True)

# Development-specific settings
STOCK_SYSTEM.update({
    'PIN_EXPIRY_MINUTES': 60,  # Longer PIN expiry in dev
    'THRESHOLD_CHECK_INTERVAL': 30,  # More frequent checks in dev
})

# Celery configuration for development
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
