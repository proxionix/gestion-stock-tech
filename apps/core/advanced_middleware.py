"""
Advanced security middleware for Stock Management System.
OWASP ASVS Level 1/2 enhanced compliance.
"""
import json
import logging
from typing import Optional
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
        """Process incoming request for security threats."""
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
            
            # Log detailed security event
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
        """Process response and add additional security measures."""
        # Add security headers
        security_headers = SecurityAudit.get_security_headers()
        for header, value in security_headers.items():
            if not response.get(header):
                response[header] = value
        
        # Log security events if any
        if hasattr(request, '_security_audit'):
            audit_results = request._security_audit
            if audit_results['issues']:
                logger.info(
                    f"Security audit completed for {audit_results['ip_address']}",
                    extra={
                        'audit_results': audit_results,
                        'event_type': 'security_audit_completed'
                    }
                )
        
        return response


class InputValidationMiddleware(MiddlewareMixin):
    """
    Input validation middleware to prevent injection attacks.
    """
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Validate all input data in the request."""
        # Skip validation for certain paths
        skip_paths = [
            '/admin/jsi18n/',
            '/static/',
            '/media/',
            '/favicon.ico',
            '/health/',
            '/sw.js',
            '/manifest.json'
        ]
        
        if any(request.path.startswith(path) for path in skip_paths):
            return None
        
        # Validate request data
        validation_errors = SecurityValidator.validate_request_data(request)
        
        if validation_errors:
            ip_address = get_client_ip(request)
            
            # Log validation failure
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
            
            # Record security event
            IPSecurityManager.record_security_event(
                ip_address, 'input_validation_failure', 'medium'
            )
            
            # Return 400 Bad Request
            return HttpResponse(
                json.dumps({
                    'error': 'Invalid input detected',
                    'details': validation_errors[:3]  # Limit details for security
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
        """Check for brute force attacks."""
        # Only check login endpoints
        if request.path not in ['/api/auth/login/', '/admin/login/']:
            return None
        
        if AttackDetector.detect_brute_force(request):
            ip_address = get_client_ip(request)
            
            # Block IP for brute force
            IPSecurityManager.block_ip(
                ip_address,
                duration=1800,  # 30 minutes
                reason="Brute force attack detected"
            )
            
            logger.critical(
                f"Brute force attack detected and blocked: {ip_address}",
                extra={
                    'ip_address': ip_address,
                    'path': request.path,
                    'event_type': 'brute_force_blocked'
                }
            )
            
            return HttpResponse(
                json.dumps({'error': 'Too many login attempts. Try again later.'}),
                status=429,
                content_type='application/json'
            )
        
        return None
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Record failed login attempts."""
        # Only process login endpoints
        if request.path not in ['/api/auth/login/', '/admin/login/']:
            return response
        
        # Record failed login on 401/403 responses
        if response.status_code in [401, 403]:
            AttackDetector.record_failed_login(request)
        
        return response


class ScanDetectionMiddleware(MiddlewareMixin):
    """
    Middleware to detect vulnerability scanning attempts.
    """
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Detect scanning attempts."""
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
            
            # Return 404 to hide real structure
            return HttpResponse("Not Found", status=404)
        
        return None


class HTTPSEnforcementMiddleware(MiddlewareMixin):
    """
    Enforce HTTPS in production with enhanced security.
    """
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Enforce HTTPS and check security headers."""
        # Skip in development
        if hasattr(request, 'environ') and request.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('.dev'):
            return None
        
        # Check if request is secure
        if not request.is_secure():
            # Allow health checks on HTTP
            if request.path in ['/health/', '/health/ready/', '/health/live/']:
                return None
            
            # Redirect to HTTPS
            from django.http import HttpResponsePermanentRedirect
            redirect_url = request.build_absolute_uri().replace('http://', 'https://')
            return HttpResponsePermanentRedirect(redirect_url)
        
        return None
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Add HTTPS-related security headers."""
        if request.is_secure():
            # Add HSTS header
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
            
            # Add secure cookie headers
            response['Set-Cookie'] = response.get('Set-Cookie', '').replace(
                'SameSite=Lax', 'SameSite=Strict; Secure'
            )
        
        return response


class ContentSecurityPolicyMiddleware(MiddlewareMixin):
    """
    Advanced Content Security Policy middleware.
    """
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Add CSP headers based on request type."""
        # Different CSP for different endpoints
        if request.path.startswith('/api/'):
            # Strict CSP for API endpoints
            csp = (
                "default-src 'none'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'none';"
            )
        elif request.path.startswith('/admin/'):
            # Admin CSP
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "font-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none';"
            )
        else:
            # PWA CSP (allows camera access)
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "media-src 'self' blob:; "
                "connect-src 'self'; "
                "font-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none';"
            )
        
        response['Content-Security-Policy'] = csp
        return response


class SecurityMonitoringMiddleware(MiddlewareMixin):
    """
    Security monitoring and alerting middleware.
    """
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Monitor for security patterns."""
        ip_address = get_client_ip(request)
        
        # Monitor for unusual activity patterns
        self._check_request_frequency(request, ip_address)
        self._check_unusual_paths(request, ip_address)
        self._check_payload_size(request, ip_address)
        
        return None
    
    def _check_request_frequency(self, request: HttpRequest, ip_address: str):
        """Check for abnormally high request frequency."""
        from django.core.cache import cache
        
        cache_key = f"request_freq:{ip_address}"
        current_count = cache.get(cache_key, 0)
        
        # Allow up to 100 requests per minute
        if current_count > 100:
            IPSecurityManager.record_security_event(
                ip_address, 'high_request_frequency', 'medium'
            )
            logger.warning(
                f"High request frequency from {ip_address}: {current_count} requests/minute"
            )
        
        cache.set(cache_key, current_count + 1, 60)  # 1 minute window
    
    def _check_unusual_paths(self, request: HttpRequest, ip_address: str):
        """Check for access to unusual paths."""
        path = request.path.lower()
        
        # Common attack paths
        attack_paths = [
            'wp-admin', 'wp-content', 'wordpress', 'phpmyadmin',
            'adminer.php', 'db.php', 'config.php', 'backup',
            'shell.php', 'webshell', 'c99.php', 'r57.php'
        ]
        
        if any(attack_path in path for attack_path in attack_paths):
            IPSecurityManager.record_security_event(
                ip_address, 'suspicious_path_access', 'high'
            )
            logger.warning(
                f"Suspicious path access from {ip_address}: {path}"
            )
    
    def _check_payload_size(self, request: HttpRequest, ip_address: str):
        """Check for unusually large payloads."""
        content_length = request.META.get('CONTENT_LENGTH', '0')
        
        try:
            size = int(content_length)
            # Alert on payloads larger than 10MB
            if size > 10 * 1024 * 1024:
                IPSecurityManager.record_security_event(
                    ip_address, 'large_payload', 'medium'
                )
                logger.warning(
                    f"Large payload from {ip_address}: {size} bytes"
                )
        except (ValueError, TypeError):
            pass
