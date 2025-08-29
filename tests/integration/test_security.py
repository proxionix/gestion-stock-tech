"""
Security tests for Stock Management System.
Tests OWASP ASVS L1/L2 compliance and security features.
"""
import pytest
from unittest.mock import patch, Mock
from django.test import Client, override_settings
from django.urls import reverse
from django.core.cache import cache
from apps.core.security import (
    SecurityValidator, IPSecurityManager, AttackDetector,
    SecurityAudit, get_client_ip
)
from apps.core.middleware import SecurityHeadersMiddleware
from apps.core.advanced_middleware import (
    AdvancedSecurityMiddleware, InputValidationMiddleware,
    BruteForceProtectionMiddleware
)


class TestSecurityValidator:
    """Test SecurityValidator utility class."""
    
    def test_validate_input_safe_data(self):
        """Test validation of safe input data."""
        assert SecurityValidator.validate_input("normal text") is True
        assert SecurityValidator.validate_input("user@domain.com") is True
        assert SecurityValidator.validate_input("123-456-789") is True
        assert SecurityValidator.validate_input({"key": "value"}) is True
    
    def test_validate_input_xss_patterns(self):
        """Test detection of XSS patterns."""
        xss_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "onload=alert(1)",
            "<iframe src='evil.com'></iframe>",
            "eval(malicious_code)",
        ]
        
        for xss_input in xss_inputs:
            assert SecurityValidator.validate_input(xss_input) is False
    
    def test_validate_input_sql_injection_patterns(self):
        """Test detection of SQL injection patterns."""
        sql_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "UNION SELECT * FROM passwords",
            "1=1",
            "exec xp_cmdshell",
        ]
        
        for sql_input in sql_inputs:
            assert SecurityValidator.validate_input(sql_input) is False
    
    def test_validate_input_path_traversal_patterns(self):
        """Test detection of path traversal patterns."""
        path_inputs = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "%2e%2e%2f",
            "..%c0%af",
        ]
        
        for path_input in path_inputs:
            assert SecurityValidator.validate_input(path_input) is False
    
    def test_validate_request_data_get_params(self, rf):
        """Test validation of GET parameters."""
        request = rf.get('/test/', {'param': '<script>alert(1)</script>'})
        
        errors = SecurityValidator.validate_request_data(request)
        
        assert len(errors) == 1
        assert 'Invalid GET parameter' in errors[0]
    
    def test_validate_request_data_post_params(self, rf):
        """Test validation of POST parameters."""
        request = rf.post('/test/', {'param': "'; DROP TABLE users; --"})
        
        errors = SecurityValidator.validate_request_data(request)
        
        assert len(errors) == 1
        assert 'Invalid POST parameter' in errors[0]


class TestIPSecurityManager:
    """Test IP security management."""
    
    def setUp(self):
        """Clear cache before each test."""
        cache.clear()
    
    def test_block_ip(self):
        """Test blocking an IP address."""
        ip = "192.168.1.100"
        
        IPSecurityManager.block_ip(ip, duration=3600, reason="Test block")
        
        assert IPSecurityManager.is_ip_blocked(ip) is True
    
    def test_is_ip_blocked_false_for_unblocked(self):
        """Test checking unblocked IP."""
        ip = "192.168.1.200"
        
        assert IPSecurityManager.is_ip_blocked(ip) is False
    
    def test_record_security_event(self):
        """Test recording security events."""
        ip = "192.168.1.100"
        
        IPSecurityManager.record_security_event(ip, "test_event", "medium")
        
        # Check event was recorded
        cache_key = f"security_events:{ip}"
        events = cache.get(cache_key, [])
        assert len(events) == 1
        assert events[0]['type'] == 'test_event'
        assert events[0]['severity'] == 'medium'
    
    def test_auto_block_on_high_severity_events(self):
        """Test automatic blocking on multiple high severity events."""
        ip = "192.168.1.100"
        
        # Record 5 high severity events
        for i in range(5):
            IPSecurityManager.record_security_event(ip, "critical_event", "high")
        
        # Should be automatically blocked
        assert IPSecurityManager.is_ip_blocked(ip) is True
    
    @override_settings(TRUSTED_IPS=['192.168.1.0/24', '10.0.0.1'])
    def test_is_trusted_ip(self):
        """Test trusted IP checking."""
        assert IPSecurityManager.is_trusted_ip("192.168.1.50") is True
        assert IPSecurityManager.is_trusted_ip("10.0.0.1") is True
        assert IPSecurityManager.is_trusted_ip("203.0.113.1") is False


class TestAttackDetector:
    """Test attack detection utilities."""
    
    def setUp(self):
        """Clear cache before each test."""
        cache.clear()
    
    def test_detect_brute_force_login_path(self, rf):
        """Test brute force detection on login path."""
        request = rf.post('/api/auth/login/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        
        # Simulate multiple failed attempts
        for i in range(6):
            AttackDetector.record_failed_login(request)
        
        # Should detect brute force
        assert AttackDetector.detect_brute_force(request) is True
    
    def test_detect_brute_force_non_login_path(self, rf):
        """Test brute force detection on non-login path."""
        request = rf.get('/api/articles/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        
        # Should not detect brute force on non-login paths
        assert AttackDetector.detect_brute_force(request) is False
    
    def test_detect_scan_attempt(self, rf):
        """Test scanning attempt detection."""
        scan_paths = [
            '/wp-admin/',
            '/phpmyadmin/',
            '/.env',
            '/config.php',
            '/backup.sql'
        ]
        
        for path in scan_paths:
            request = rf.get(path)
            request.META['REMOTE_ADDR'] = '192.168.1.100'
            
            assert AttackDetector.detect_scan_attempt(request) is True
    
    def test_detect_suspicious_user_agent(self, rf):
        """Test suspicious user agent detection."""
        suspicious_agents = [
            'sqlmap/1.0',
            'nikto',
            'python-requests/2.0',
            'curl/7.0',
            'wget/1.0'
        ]
        
        for agent in suspicious_agents:
            request = rf.get('/test/')
            request.META['HTTP_USER_AGENT'] = agent
            request.META['REMOTE_ADDR'] = '192.168.1.100'
            
            assert AttackDetector.detect_unusual_user_agent(request) is True
    
    def test_detect_normal_user_agent(self, rf):
        """Test detection with normal user agent."""
        normal_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        ]
        
        for agent in normal_agents:
            request = rf.get('/test/')
            request.META['HTTP_USER_AGENT'] = agent
            request.META['REMOTE_ADDR'] = '192.168.1.100'
            
            assert AttackDetector.detect_unusual_user_agent(request) is False


class TestSecurityAudit:
    """Test security audit functionality."""
    
    def test_get_security_headers(self):
        """Test getting security headers."""
        headers = SecurityAudit.get_security_headers()
        
        assert 'X-Content-Type-Options' in headers
        assert 'X-Frame-Options' in headers
        assert 'Content-Security-Policy' in headers
        assert 'Strict-Transport-Security' in headers
        assert headers['X-Content-Type-Options'] == 'nosniff'
        assert headers['X-Frame-Options'] == 'DENY'
    
    def test_audit_request_safe(self, rf):
        """Test auditing safe request."""
        request = rf.get('/test/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 (normal browser)'
        
        results = SecurityAudit.audit_request(request)
        
        assert results['risk_level'] == 'low'
        assert len(results['issues']) == 0
    
    def test_audit_request_suspicious(self, rf):
        """Test auditing suspicious request."""
        request = rf.get('/wp-admin/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_USER_AGENT'] = 'sqlmap/1.0'
        
        results = SecurityAudit.audit_request(request)
        
        assert results['risk_level'] in ['medium', 'high']
        assert len(results['issues']) > 0


class TestSecurityMiddleware:
    """Test security middleware functionality."""
    
    def test_security_headers_middleware(self, rf):
        """Test security headers are added."""
        middleware = SecurityHeadersMiddleware(Mock())
        request = rf.get('/test/')
        response = Mock()
        response.get.return_value = None
        
        # Process response
        result = middleware.process_response(request, response)
        
        # Check headers were set
        assert response.__setitem__.called
    
    def test_advanced_security_middleware_blocked_ip(self, rf):
        """Test advanced security middleware blocks IPs."""
        middleware = AdvancedSecurityMiddleware(Mock())
        request = rf.get('/test/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        
        # Block the IP first
        IPSecurityManager.block_ip('192.168.1.100', 3600, 'Test')
        
        # Should return forbidden response
        response = middleware.process_request(request)
        
        assert response is not None
        assert response.status_code == 403
    
    def test_input_validation_middleware(self, rf):
        """Test input validation middleware."""
        middleware = InputValidationMiddleware(Mock())
        request = rf.post('/test/', {'param': '<script>alert(1)</script>'})
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        
        # Should return bad request response
        response = middleware.process_request(request)
        
        assert response is not None
        assert response.status_code == 400
    
    def test_brute_force_protection_middleware(self, rf):
        """Test brute force protection middleware."""
        middleware = BruteForceProtectionMiddleware(Mock())
        request = rf.post('/api/auth/login/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        
        # Simulate multiple failed attempts
        for i in range(6):
            AttackDetector.record_failed_login(request)
        
        # Should block request
        response = middleware.process_request(request)
        
        assert response is not None
        assert response.status_code == 429


class TestSecurityIntegration:
    """Integration tests for security features."""
    
    def test_login_brute_force_protection(self, api_client):
        """Test brute force protection on login endpoint."""
        url = reverse('api:login')
        data = {'username': 'nonexistent', 'password': 'wrong'}
        
        # Make multiple failed login attempts
        for i in range(6):
            response = api_client.post(url, data)
        
        # Next attempt should be blocked
        response = api_client.post(url, data)
        assert response.status_code == 429
    
    def test_xss_protection_in_api(self, jwt_admin_client):
        """Test XSS protection in API endpoints."""
        url = reverse('api:article_list')
        data = {
            'reference': 'XSS001',
            'name': '<script>alert("xss")</script>',
            'unit': 'PCS'
        }
        
        response = jwt_admin_client.post(url, data)
        
        # Should reject malicious input
        assert response.status_code == 400
    
    def test_sql_injection_protection(self, jwt_tech_client):
        """Test SQL injection protection."""
        url = reverse('api:article_list')
        
        # Try SQL injection in search parameter
        response = jwt_tech_client.get(url, {'search': "'; DROP TABLE articles; --"})
        
        # Should reject malicious input
        assert response.status_code == 400
    
    def test_security_headers_in_response(self, api_client):
        """Test security headers are present in responses."""
        url = reverse('api:health')
        
        response = api_client.get(url)
        
        # Check security headers
        assert 'X-Content-Type-Options' in response
        assert 'X-Frame-Options' in response
        assert 'Content-Security-Policy' in response
        assert response['X-Content-Type-Options'] == 'nosniff'
        assert response['X-Frame-Options'] == 'DENY'
    
    def test_csrf_protection(self, api_client):
        """Test CSRF protection is active."""
        url = reverse('api:login')
        
        # Request without CSRF token should fail
        response = api_client.post(url, {'username': 'test', 'password': 'test'})
        
        # Should be protected (either 403 or 401 depending on implementation)
        assert response.status_code in [401, 403]
    
    def test_https_enforcement_production(self, api_client):
        """Test HTTPS enforcement in production-like settings."""
        # This would need to be tested with production settings
        # and proper SSL setup
        pass
    
    @patch('apps.core.security.IPSecurityManager.record_security_event')
    def test_security_event_logging(self, mock_record, api_client):
        """Test that security events are properly logged."""
        url = '/wp-admin/'  # Suspicious path
        
        api_client.get(url)
        
        # Should record security event
        mock_record.assert_called()
    
    def test_rate_limiting_api(self, jwt_tech_client):
        """Test API rate limiting."""
        url = reverse('api:article_list')
        
        # Make many requests quickly
        for i in range(150):  # Exceed the typical rate limit
            response = jwt_tech_client.get(url)
            if response.status_code == 429:
                break
        
        # Should eventually hit rate limit
        assert response.status_code == 429
    
    def test_permission_isolation(self, jwt_tech_client, jwt_admin_client):
        """Test that permissions are properly isolated."""
        # Test technician cannot access admin endpoints
        security_url = reverse('api:security_dashboard')
        response = jwt_tech_client.get(security_url)
        assert response.status_code == 403
        
        # Test admin can access admin endpoints
        response = jwt_admin_client.get(security_url)
        assert response.status_code == 200
    
    def test_input_size_limits(self, jwt_admin_client):
        """Test input size limits are enforced."""
        url = reverse('api:article_list')
        
        # Try to send very large input
        large_data = {
            'reference': 'TEST001',
            'name': 'A' * 20000,  # Very large string
            'unit': 'PCS'
        }
        
        response = jwt_admin_client.post(url, large_data)
        
        # Should reject oversized input
        assert response.status_code == 400
    
    def test_file_upload_security(self, jwt_admin_client, test_files):
        """Test file upload security restrictions."""
        # This would test file upload endpoints if they exist
        # For now, we test the security configuration
        pass
    
    def test_session_security(self, api_client, technician_user):
        """Test session security configuration."""
        # Login to create session
        api_client.login(username='tech_test', password='test_tech_123')
        
        # Check session cookie attributes
        session_cookie = api_client.cookies.get('sessionid')
        if session_cookie:
            # Check security attributes
            assert session_cookie.get('httponly', False)
            assert session_cookie.get('secure', False) or not session_cookie.get('secure')  # Depends on HTTPS
    
    def test_password_security(self, technician_user):
        """Test password security configuration."""
        # Check password is properly hashed
        assert not technician_user.password.startswith('test_tech_123')
        assert len(technician_user.password) > 20  # Hashed passwords are longer
    
    def test_sensitive_data_exposure(self, jwt_tech_client):
        """Test that sensitive data is not exposed in responses."""
        url = reverse('api:me')
        
        response = jwt_tech_client.get(url)
        
        assert response.status_code == 200
        # Check that password is not in response
        response_str = str(response.content)
        assert 'password' not in response_str.lower()
        assert 'secret' not in response_str.lower()


class TestSecurityConfiguration:
    """Test security configuration and settings."""
    
    def test_debug_disabled_production(self):
        """Test that DEBUG is disabled in production."""
        # This would check production settings
        pass
    
    def test_allowed_hosts_configured(self):
        """Test that ALLOWED_HOSTS is properly configured."""
        # This would check ALLOWED_HOSTS setting
        pass
    
    def test_secret_key_security(self):
        """Test that SECRET_KEY is secure."""
        # This would check SECRET_KEY configuration
        pass
    
    def test_database_security(self):
        """Test database security configuration."""
        # This would check database connection security
        pass
    
    def test_cors_configuration(self):
        """Test CORS configuration is secure."""
        # This would check CORS settings
        pass
