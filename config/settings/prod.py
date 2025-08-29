"""
Production settings for Stock Management System.
Enterprise-grade security and performance configuration.
"""
from .base import *

# Security settings for production
DEBUG = False

# Require environment variables for production
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required in production")

if not ALLOWED_HOSTS:
    raise ValueError("ALLOWED_HOSTS environment variable is required in production")

# Database - require environment variable
if not env('DATABASE_URL', default=''):
    raise ValueError("DATABASE_URL environment variable is required in production")

# Enhanced security headers
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Enhanced session security
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Enhanced CSRF protection
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Strict'

# CORS - restrictive in production
CORS_ALLOW_ALL_ORIGINS = False
if not CORS_ALLOWED_ORIGINS:
    raise ValueError("CORS_ALLOWED_ORIGINS environment variable is required in production")

# Production email configuration
if EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = env('EMAIL_HOST', default='localhost')
    EMAIL_PORT = env('EMAIL_PORT', default=587)
    EMAIL_USE_TLS = env('EMAIL_USE_TLS', default=True)
    EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')

# Production throttling
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '50/hour',
    'user': '500/hour'
}

# Production logging - more restrictive
LOGGING['loggers']['django']['level'] = 'WARNING'
LOGGING['loggers']['apps']['level'] = 'INFO'

# Add audit logging handler
LOGGING['handlers']['audit'] = {
    'class': 'logging.FileHandler',
    'filename': BASE_DIR / 'logs' / 'audit.log',
    'formatter': 'json',
}

LOGGING['loggers']['apps.audit'] = {
    'handlers': ['audit'],
    'level': 'INFO',
    'propagate': False,
}

# Performance optimizations
CONN_MAX_AGE = 60

# Cache sessions
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Celery production configuration
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Production-specific settings
STOCK_SYSTEM.update({
    'PIN_EXPIRY_MINUTES': 10,  # Shorter PIN expiry in prod
    'THRESHOLD_CHECK_INTERVAL': 600,  # Less frequent checks in prod
})

# Health check settings
ALLOWED_HOSTS += [
    'health-check',  # Allow health check requests
]

# Additional security middleware for production
MIDDLEWARE.insert(0, 'django.middleware.security.SecurityMiddleware')

# Content Security Policy (basic)
CSP_DEFAULT_SRC = ["'self'"]
CSP_SCRIPT_SRC = ["'self'", "'unsafe-inline'"]  # For QR scanning
CSP_STYLE_SRC = ["'self'", "'unsafe-inline'"]
CSP_IMG_SRC = ["'self'", "data:", "blob:"]  # For QR codes and signatures
CSP_CONNECT_SRC = ["'self'"]
CSP_FONT_SRC = ["'self'"]
CSP_OBJECT_SRC = ["'none'"]
CSP_BASE_URI = ["'self'"]
CSP_FORM_ACTION = ["'self'"]
CSP_FRAME_ANCESTORS = ["'none'"]

# Ensure logs directory exists
import os
logs_dir = BASE_DIR / 'logs'
if not logs_dir.exists():
    logs_dir.mkdir(exist_ok=True)
