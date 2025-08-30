"""
Advanced security middleware for Stock Management System.
OWASP ASVS Level 1/2 enhanced compliance.
"""
import json
import logging
from typing import Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin

from .security import (
    SecurityValidator, IPSecurityManager, AttackDetector,
    SecurityAudit, get_client_ip
)

logger = logging.getLogger(__name__)


class AdvancedSecurityMiddleware(MiddlewareMixin):
    """
    Advanced security middleware with attack detection and IP blocking.
    """

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        ip_address = get_client_ip(request)

        # Skip security checks for trusted IPs
        if IPSecurityManager.is_trusted_ip(ip_address):
            return None

        # Check if IP is blocked
        if IPSecurityManager.is_ip_blocked(ip_address):
            logger.warning(
                f"Blocked IP attempted access: {ip_address}",
                extra={
                    'ip_address': ip_address,
                    'path': request.path,
                    'method': request.method,
                    'event_type': 'blocked_ip_access'
                }
            )
            return HttpResponseForbidden("Access denied")

        # Perform security audit
        audit_results = SecurityAudit.audit_request(request)

        # Handle critical risk level
        if audit_results['risk_level'] == 'critical':
            IPSecurityManager.block_ip(
                ip_address,
                duration=3600,  # 1 hour
                reason="Critical security risk detected"
            )
            return HttpResponseForbidden("Security violation detected")

        # Handle high risk level
        elif audit_results['risk_level'] == 'high':
            IPSecurityManager.record_security_event(
                ip_address, 'high_risk_request', 'high'
            )
            logger.warning(
                f"High risk request detected from {ip_address}",
                extra={
                    'ip_address': ip_address,
                    'issues': audit_results['issues'],
                    'path': request.path,
                    'method': request.method,
                    'user_agent': audit_results.get('user_agent', ''),
                    'event_type': 'high_risk_request'
                }
            )

        # Store audit results in request for later use
        request._security_audit = audit_results
        return None

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        # Add security headers (only if not already set)
        security_headers = SecurityAudit.get_security_headers()
        for header, value in security_headers.items():
            if not response.get(header):
                response[header] = value

        # Log audit summary
        if hasattr(request, '_security_audit'):
            audit_results = request._security_audit
            if audit_results['issues']:
                logger.info(
                    f"Security audit completed for {audit_results['ip_address']}",
                    extra={'audit_results': audit_results, 'event_type': 'security_audit_completed'}
                )
        return response


class InputValidationMiddleware(MiddlewareMixin):
    """
    Input validation middleware to prevent injection attacks.
    """

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        # Skip validation for static/health/PWA assets
        skip_paths = [
            '/admin/jsi18n/',
            '/static/',
            '/media/',
            '/favicon.ico',
            '/health/',
            '/sw.js',
            '/manifest.json',
        ]
        if any(request.path.startswith(path) for path in skip_paths):
            return None

        validation_errors = SecurityValidator.validate_request_data(request)
        if validation_errors:
            ip_address = get_client_ip(request)
            logger.warning(
                f"Input validation failed for {ip_address}: {validation_errors}",
                extra={
                    'ip_address': ip_address,
                    'validation_errors': validation_errors,
                    'path': request.path,
                    'method': request.method,
                    'event_type': 'input_validation_failed'
                }
            )
            IPSecurityManager.record_security_event(
                ip_address, 'input_validation_failure', 'medium'
            )
            return HttpResponse(
                json.dumps({
                    'error': 'Invalid input detected',
                    'details': validation_errors[:3]
                }),
                status=400,
                content_type='application/json'
            )
        return None


class BruteForceProtectionMiddleware(MiddlewareMixin):
    """
    Brute force protection middleware.
    """

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        # Only check login endpoints
        if request.path not in ['/api/auth/login/', '/admin/login/']:
            return None

        if AttackDetector.detect_brute_force(request):
            ip_address = get_client_ip(request)
            IPSecurityManager.block_ip(
                ip_address, duration=1800, reason="Brute force attack detected"
            )
            logger.critical(
                f"Brute force attack detected and blocked: {ip_address}",
                extra={'ip_address': ip_address, 'path': request.path, 'event_type': 'brute_force_blocked'}
            )
            return HttpResponse(
                json.dumps({'error': 'Too many login attempts. Try again later.'}),
                status=429,
                content_type='application/json'
            )
        return None

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        if request.path not in ['/api/auth/login/', '/admin/login/']:
            return response
        if response.status_code in [401, 403]:
            AttackDetector.record_failed_login(request)
        return response


class ScanDetectionMiddleware(MiddlewareMixin):
    """
    Middleware to detect vulnerability scanning attempts.
    """

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        if AttackDetector.detect_scan_attempt(request):
            ip_address = get_client_ip(request)
            logger.warning(
                f"Vulnerability scan detected from {ip_address}: {request.path}",
                extra={
                    'ip_address': ip_address,
                    'path': request.path,
                    'method': request.method,
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'event_type': 'vulnerability_scan_detected'
                }
            )
            return HttpResponse("Not Found", status=404)
        return None


class HTTPSEnforcementMiddleware(MiddlewareMixin):
    """
    Enforce HTTPS in production with enhanced security.
    """

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        # Skip entirely in development
        if settings.DEBUG:
            return None

        if not request.is_secure():
            # Allow health checks on HTTP
            if request.path in ['/health/', '/health/ready/', '/health/live/']:
                return None
            from django.http import HttpResponsePermanentRedirect
            redirect_url = request.build_absolute_uri().replace('http://', 'https://', 1)
            return HttpResponsePermanentRedirect(redirect_url)
        return None

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        if request.is_secure():
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
            # Harden cookies when present
            if 'Set-Cookie' in response:
                response['Set-Cookie'] = response['Set-Cookie'].replace('SameSite=Lax', 'SameSite=Strict; Secure')
        return response


class ContentSecurityPolicyMiddleware(MiddlewareMixin):
    """
    Advanced Content Security Policy middleware.
    """

    # CDNs autorisés pour la PWA (CSS/JS/Fonts)
    PWA_SCRIPT_CDNS = ["https://cdn.jsdelivr.net", "https://unpkg.com", "https://cdnjs.cloudflare.com"]
    PWA_STYLE_CDNS = ["https://cdn.jsdelivr.net"]
    PWA_FONT_CDNS = ["https://cdn.jsdelivr.net", "https://fonts.gstatic.com"]

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        # Pas de CSP en dev si tu préfères éviter les blocages (désactive ici si besoin)
        # if settings.DEBUG:
        #     return response

        path = request.path

        if path.startswith('/api/'):
            # Très strict pour l'API
            csp = (
                "default-src 'none'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'none'; "
                "form-action 'none'; "
                "worker-src 'none'; "
                "manifest-src 'none'"
            )

        elif path.startswith('/admin/'):
            # Admin : autoriser styles inline de Django admin et données locales
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self' data:; "
                "connect-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none'; "
                "worker-src 'self'; "
                "manifest-src 'self'"
            )

        else:
            # PWA / pages publiques (autoriser Tailwind via jsDelivr + quelques CDNs sûrs)
            script_src = ["'self'", "'unsafe-inline'", "'unsafe-eval'"] + self.PWA_SCRIPT_CDNS
            style_src = ["'self'", "'unsafe-inline'"] + self.PWA_STYLE_CDNS
            font_src = ["'self'", "data:"] + self.PWA_FONT_CDNS

            csp = (
                "default-src 'self'; "
                f"script-src {' '.join(script_src)}; "
                f"style-src {' '.join(style_src)}; "
                "img-src 'self' data: blob:; "
                "media-src 'self' blob:; "
                f"font-src {' '.join(font_src)}; "
                "connect-src 'self' ws: wss:; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none'; "
                "worker-src 'self'; "
                "manifest-src 'self'"
            )

        response['Content-Security-Policy'] = csp
        return response


class SecurityMonitoringMiddleware(MiddlewareMixin):
    """
    Security monitoring and alerting middleware.
    """

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        ip_address = get_client_ip(request)
        self._check_request_frequency(request, ip_address)
        self._check_unusual_paths(request, ip_address)
        self._check_payload_size(request, ip_address)
        return None

    def _check_request_frequency(self, request: HttpRequest, ip_address: str):
        from django.core.cache import cache

        cache_key = f"request_freq:{ip_address}"
        current_count = cache.get(cache_key, 0)

        # Allow up to 100 requests per minute
        if current_count > 100:
            IPSecurityManager.record_security_event(
                ip_address, 'high_request_frequency', 'medium'
            )
            logger.warning(f"High request frequency from {ip_address}: {current_count} requests/minute")

        cache.set(cache_key, current_count + 1, 60)  # 1 minute window

    def _check_unusual_paths(self, request: HttpRequest, ip_address: str):
        path = request.path.lower()
        attack_paths = [
            'wp-admin', 'wp-content', 'wordpress', 'phpmyadmin',
            'adminer.php', 'db.php', 'config.php', 'backup',
            'shell.php', 'webshell', 'c99.php', 'r57.php'
        ]
        if any(attack_path in path for attack_path in attack_paths):
            IPSecurityManager.record_security_event(
                ip_address, 'suspicious_path_access', 'high'
            )
            logger.warning(f"Suspicious path access from {ip_address}: {path}")

    def _check_payload_size(self, request: HttpRequest, ip_address: str):
        content_length = request.META.get('CONTENT_LENGTH', '0')
        try:
            size = int(content_length)
            if size > 10 * 1024 * 1024:  # > 10MB
                IPSecurityManager.record_security_event(
                    ip_address, 'large_payload', 'medium'
                )
                logger.warning(f"Large payload from {ip_address}: {size} bytes")
        except (ValueError, TypeError):
            pass
