"""
Enhanced security utilities for Stock Management System.
OWASP ASVS Level 1/2 compliance utilities.
"""
import re
import hashlib
import ipaddress
from typing import List, Dict, Any, Optional
from django.core.cache import cache
from django.http import HttpRequest
from django.utils import timezone
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class SecurityValidator:
    """Advanced security validation utilities."""
    
    # XSS patterns
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'vbscript:',
        r'onload\s*=',
        r'onerror\s*=',
        r'onclick\s*=',
        r'onmouseover\s*=',
        r'<iframe[^>]*>',
        r'<object[^>]*>',
        r'<embed[^>]*>',
        r'<link[^>]*>',
        r'<meta[^>]*>',
        r'eval\s*\(',
        r'expression\s*\(',
    ]
    
    # SQL injection patterns
    SQL_PATTERNS = [
        r"';\s*(drop|delete|insert|update|create|alter)\s+",
        r'union\s+select',
        r'1\s*=\s*1',
        r"'\s*or\s*'1'\s*=\s*'1",
        r'--\s*$',
        r'/\*.*?\*/',
        r'exec\s*\(',
        r'sp_\w+',
        r'xp_\w+',
    ]
    
    # Path traversal patterns
    PATH_PATTERNS = [
        r'(?:\.\./|\.\.\\)',
        r'%2e%2e%2f',
        r'%2e%2e%5c',
        r'\.\.%c0%af',
        r'\.\.%c1%9c',
    ]
    
    @classmethod
    def validate_input(cls, data: Any, field_name: str = "input") -> bool:
        """
        Validate input data against common attack patterns.
        
        Args:
            data: Data to validate
            field_name: Name of the field being validated
            
        Returns:
            True if input is safe, False otherwise
        """
        if data is None:
            return True
            
        # Convert to string for pattern matching
        if isinstance(data, (dict, list)):
            data_str = str(data)
        else:
            data_str = str(data).lower()
        
        # Check XSS patterns
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, data_str, re.IGNORECASE):
                logger.warning(
                    f"XSS pattern detected in {field_name}: {pattern}",
                    extra={'field': field_name, 'pattern': pattern, 'event_type': 'xss_attempt'}
                )
                return False
        
        # Check SQL injection patterns
        for pattern in cls.SQL_PATTERNS:
            if re.search(pattern, data_str, re.IGNORECASE):
                logger.warning(
                    f"SQL injection pattern detected in {field_name}: {pattern}",
                    extra={'field': field_name, 'pattern': pattern, 'event_type': 'sql_injection_attempt'}
                )
                return False
        
        # Check path traversal patterns
        for pattern in cls.PATH_PATTERNS:
            if re.search(pattern, data_str, re.IGNORECASE):
                logger.warning(
                    f"Path traversal pattern detected in {field_name}: {pattern}",
                    extra={'field': field_name, 'pattern': pattern, 'event_type': 'path_traversal_attempt'}
                )
                return False
        
        return True
    
    @classmethod
    def validate_request_data(cls, request: HttpRequest) -> List[str]:
        """
        Validate all data in a request.
        
        Args:
            request: Django request object
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Validate GET parameters
        for key, value in request.GET.items():
            if not cls.validate_input(value, f"GET.{key}"):
                errors.append(f"Invalid GET parameter: {key}")
        
        # Validate POST parameters
        for key, value in request.POST.items():
            if not cls.validate_input(value, f"POST.{key}"):
                errors.append(f"Invalid POST parameter: {key}")
        
        # Validate JSON data (if any)
        if hasattr(request, 'data') and isinstance(request.data, dict):
            for key, value in request.data.items():
                if not cls.validate_input(value, f"JSON.{key}"):
                    errors.append(f"Invalid JSON parameter: {key}")
        
        return errors


class IPSecurityManager:
    """IP-based security management."""
    
    @staticmethod
    def is_ip_blocked(ip_address: str) -> bool:
        """Check if IP address is blocked."""
        cache_key = f"blocked_ip:{ip_address}"
        return cache.get(cache_key, False)
    
    @staticmethod
    def block_ip(ip_address: str, duration: int = 3600, reason: str = "Security violation"):
        """
        Block an IP address.
        
        Args:
            ip_address: IP to block
            duration: Block duration in seconds
            reason: Reason for blocking
        """
        cache_key = f"blocked_ip:{ip_address}"
        cache.set(cache_key, True, duration)
        
        logger.warning(
            f"IP blocked: {ip_address} for {duration}s - {reason}",
            extra={
                'ip_address': ip_address,
                'duration': duration,
                'reason': reason,
                'event_type': 'ip_blocked'
            }
        )
    
    @staticmethod
    def record_security_event(ip_address: str, event_type: str, severity: str = "medium"):
        """
        Record a security event for an IP.
        
        Args:
            ip_address: IP address
            event_type: Type of security event
            severity: Severity level (low, medium, high, critical)
        """
        cache_key = f"security_events:{ip_address}"
        events = cache.get(cache_key, [])
        
        event = {
            'type': event_type,
            'severity': severity,
            'timestamp': timezone.now().isoformat()
        }
        events.append(event)
        
        # Keep only last 100 events
        events = events[-100:]
        
        # Store for 24 hours
        cache.set(cache_key, events, 86400)
        
        # Auto-block if too many high severity events
        high_events = [e for e in events if e['severity'] in ['high', 'critical']]
        if len(high_events) >= 5:
            IPSecurityManager.block_ip(
                ip_address, 
                duration=7200,  # 2 hours
                reason=f"Multiple high severity events: {len(high_events)}"
            )
    
    @staticmethod
    def is_trusted_ip(ip_address: str) -> bool:
        """Check if IP is in trusted list."""
        trusted_ips = getattr(settings, 'TRUSTED_IPS', [])
        
        try:
            ip = ipaddress.ip_address(ip_address)
            for trusted in trusted_ips:
                if '/' in trusted:
                    # Network range
                    if ip in ipaddress.ip_network(trusted):
                        return True
                else:
                    # Single IP
                    if ip == ipaddress.ip_address(trusted):
                        return True
        except ValueError:
            pass
        
        return False


class AttackDetector:
    """Detect various types of attacks."""
    
    @staticmethod
    def detect_brute_force(request: HttpRequest) -> bool:
        """
        Detect brute force attacks.
        
        Args:
            request: Django request object
            
        Returns:
            True if brute force detected
        """
        if request.path_info not in ['/api/auth/login/', '/admin/login/']:
            return False
        
        ip_address = get_client_ip(request)
        cache_key = f"login_attempts:{ip_address}"
        
        attempts = cache.get(cache_key, 0)
        
        # Check if too many attempts
        if attempts >= 5:
            IPSecurityManager.record_security_event(
                ip_address, 'brute_force_attempt', 'high'
            )
            return True
        
        return False
    
    @staticmethod
    def record_failed_login(request: HttpRequest):
        """Record a failed login attempt."""
        ip_address = get_client_ip(request)
        cache_key = f"login_attempts:{ip_address}"
        
        attempts = cache.get(cache_key, 0) + 1
        cache.set(cache_key, attempts, 900)  # 15 minutes
        
        if attempts >= 3:
            IPSecurityManager.record_security_event(
                ip_address, 'repeated_failed_login', 'medium'
            )
    
    @staticmethod
    def detect_scan_attempt(request: HttpRequest) -> bool:
        """
        Detect scanning attempts (directory traversal, vulnerability scanning).
        
        Args:
            request: Django request object
            
        Returns:
            True if scanning detected
        """
        suspicious_paths = [
            'wp-admin', 'wp-content', 'admin.php', 'phpmyadmin',
            '.env', 'config.php', 'wp-config.php', '.git',
            'backup', 'dump.sql', 'test.php', 'shell.php'
        ]
        
        path = request.path_info.lower()
        
        for suspicious in suspicious_paths:
            if suspicious in path:
                ip_address = get_client_ip(request)
                IPSecurityManager.record_security_event(
                    ip_address, 'scan_attempt', 'medium'
                )
                return True
        
        return False
    
    @staticmethod
    def detect_unusual_user_agent(request: HttpRequest) -> bool:
        """
        Detect unusual or suspicious user agents.
        
        Args:
            request: Django request object
            
        Returns:
            True if suspicious user agent detected
        """
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        # Empty or very short user agent
        if len(user_agent) < 10:
            return True
        
        # Known bot/scanner patterns
        suspicious_patterns = [
            'sqlmap', 'nikto', 'nmap', 'masscan', 'zap',
            'burp', 'w3af', 'acunetix', 'netsparker',
            'wget', 'curl', 'python-requests', 'python-urllib',
            'go-http-client', 'java/', 'apache-httpclient'
        ]
        
        for pattern in suspicious_patterns:
            if pattern in user_agent:
                ip_address = get_client_ip(request)
                IPSecurityManager.record_security_event(
                    ip_address, 'suspicious_user_agent', 'low'
                )
                return True
        
        return False


def get_client_ip(request: HttpRequest) -> str:
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


def generate_csrf_token() -> str:
    """Generate a secure CSRF token."""
    import secrets
    return secrets.token_urlsafe(32)


def hash_sensitive_data(data: str, salt: str = None) -> str:
    """
    Hash sensitive data with salt.
    
    Args:
        data: Data to hash
        salt: Optional salt (auto-generated if not provided)
        
    Returns:
        Hashed data
    """
    if salt is None:
        import secrets
        salt = secrets.token_hex(16)
    
    # Use PBKDF2 for secure hashing
    hashed = hashlib.pbkdf2_hmac('sha256', data.encode(), salt.encode(), 100000)
    return f"{salt}:{hashed.hex()}"


def verify_sensitive_data(data: str, hashed_data: str) -> bool:
    """
    Verify sensitive data against hash.
    
    Args:
        data: Data to verify
        hashed_data: Hash to verify against
        
    Returns:
        True if data matches hash
    """
    try:
        salt, hash_hex = hashed_data.split(':', 1)
        hashed = hashlib.pbkdf2_hmac('sha256', data.encode(), salt.encode(), 100000)
        return hashed.hex() == hash_hex
    except (ValueError, AttributeError):
        return False


class SecurityAudit:
    """Security audit utilities."""
    
    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get recommended security headers."""
        return {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "connect-src 'self'; "
                "font-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none';"
            ),
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
        }
    
    @staticmethod
    def audit_request(request: HttpRequest) -> Dict[str, Any]:
        """
        Perform security audit on a request.
        
        Args:
            request: Django request object
            
        Returns:
            Audit results
        """
        results = {
            'ip_address': get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'timestamp': timezone.now().isoformat(),
            'issues': [],
            'risk_level': 'low'
        }
        
        ip_address = results['ip_address']
        
        # Check if IP is blocked
        if IPSecurityManager.is_ip_blocked(ip_address):
            results['issues'].append('IP address is blocked')
            results['risk_level'] = 'critical'
        
        # Check for brute force
        if AttackDetector.detect_brute_force(request):
            results['issues'].append('Brute force attack detected')
            results['risk_level'] = 'high'
        
        # Check for scanning
        if AttackDetector.detect_scan_attempt(request):
            results['issues'].append('Scanning attempt detected')
            results['risk_level'] = 'medium'
        
        # Check user agent
        if AttackDetector.detect_unusual_user_agent(request):
            results['issues'].append('Suspicious user agent')
            if results['risk_level'] == 'low':
                results['risk_level'] = 'medium'
        
        # Validate input data
        validation_errors = SecurityValidator.validate_request_data(request)
        if validation_errors:
            results['issues'].extend(validation_errors)
            results['risk_level'] = 'high'
        
        return results
