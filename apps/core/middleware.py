"""
Security and audit middleware for Stock Management System.
OWASP ASVS Level 1/2 compliance.
"""
import json
import logging
import time
import uuid
from typing import Callable, Optional

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin
from .security import (
    SecurityValidator, IPSecurityManager, AttackDetector, 
    SecurityAudit, get_client_ip
)

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Enhanced security headers middleware for OWASP compliance.
    """
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Add security headers to response."""
        # Content Security Policy
        if not response.get('Content-Security-Policy'):
            csp_directives = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline'",  # For QR scanning
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data: blob:",  # For QR codes and signatures
                "connect-src 'self'",
                "font-src 'self'",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "frame-ancestors 'none'",
            ]
            response['Content-Security-Policy'] = '; '.join(csp_directives)
        
        # Additional security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        
        # Server header removal
        if 'Server' in response:
            del response['Server']
            
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Structured logging middleware for audit trail.
    """
    
    def process_request(self, request: HttpRequest) -> None:
        """Log incoming request with structured data."""
        request._start_time = time.time()
        request._request_id = str(uuid.uuid4())
        
        # Extract request info
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        ip_address = self._get_client_ip(request)
        user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') else None
        
        # Log request
        logger.info("Request started", extra={
            'request_id': request._request_id,
            'method': request.method,
            'path': request.path,
            'user_id': user_id,
            'ip_address': ip_address,
            'user_agent': user_agent[:200],  # Truncate long user agents
            'event_type': 'request_start'
        })
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Log response with timing information."""
        if hasattr(request, '_start_time'):
            duration = time.time() - request._start_time
            
            user_id = getattr(request.user, 'id', None) if hasattr(request, 'user') else None
            
            logger.info("Request completed", extra={
                'request_id': getattr(request, '_request_id', ''),
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration_ms': round(duration * 1000, 2),
                'user_id': user_id,
                'event_type': 'request_end'
            })
        
        return response
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip


class AuditMiddleware(MiddlewareMixin):
    """
    Audit middleware for tracking sensitive operations.
    """
    
    AUDIT_PATHS = [
        '/api/demandes/',
        '/api/my/cart/submit',
        '/api/use',
        '/admin/',
    ]
    
    def process_request(self, request: HttpRequest) -> None:
        """Capture request data for audit if needed."""
        if self._should_audit(request):
            request._audit_data = {
                'method': request.method,
                'path': request.path,
                'user_id': getattr(request.user, 'id', None) if hasattr(request, 'user') else None,
                'ip_address': self._get_client_ip(request),
                'timestamp': time.time(),
                'request_id': getattr(request, '_request_id', ''),
            }
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Log audit event if needed."""
        if hasattr(request, '_audit_data') and self._should_audit(request):
            audit_data = request._audit_data
            audit_data['status_code'] = response.status_code
            audit_data['success'] = 200 <= response.status_code < 400
            
            logger.info("Audit event", extra={
                **audit_data,
                'event_type': 'audit_trail'
            })
        
        return response
    
    def _should_audit(self, request: HttpRequest) -> bool:
        """Determine if request should be audited."""
        if not hasattr(request, 'user') or isinstance(request.user, AnonymousUser):
            return False
            
        return any(request.path.startswith(path) for path in self.AUDIT_PATHS)
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip


class RateLimitMiddleware(MiddlewareMixin):
    """
    Simple rate limiting middleware.
    Note: In production, use Redis-based rate limiting for distributed systems.
    """
    
    def __init__(self, get_response: Callable):
        """Initialize rate limiting storage."""
        super().__init__(get_response)
        self._requests = {}  # Simple in-memory storage (not production-ready)
        self._window_size = 3600  # 1 hour
        self._max_requests = 1000  # Per user per hour
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Check rate limits for authenticated users."""
        if not hasattr(request, 'user') or isinstance(request.user, AnonymousUser):
            return None
        
        user_id = request.user.id
        current_time = time.time()
        
        # Clean old entries
        self._cleanup_old_requests(current_time)
        
        # Check current user's requests
        user_requests = self._requests.get(user_id, [])
        recent_requests = [ts for ts in user_requests if current_time - ts < self._window_size]
        
        if len(recent_requests) >= self._max_requests:
            logger.warning("Rate limit exceeded", extra={
                'user_id': user_id,
                'ip_address': self._get_client_ip(request),
                'request_count': len(recent_requests),
                'event_type': 'rate_limit_exceeded'
            })
            return HttpResponse(
                json.dumps({'error': 'Rate limit exceeded'}),
                status=429,
                content_type='application/json'
            )
        
        # Record this request
        recent_requests.append(current_time)
        self._requests[user_id] = recent_requests
        
        return None
    
    def _cleanup_old_requests(self, current_time: float) -> None:
        """Remove old request timestamps."""
        for user_id in list(self._requests.keys()):
            self._requests[user_id] = [
                ts for ts in self._requests[user_id] 
                if current_time - ts < self._window_size
            ]
            if not self._requests[user_id]:
                del self._requests[user_id]
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip
