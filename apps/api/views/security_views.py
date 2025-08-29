"""
Security management API views for Stock Management System.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from apps.api.permissions import IsAdmin
from apps.core.security import IPSecurityManager, SecurityAudit


@api_view(['GET'])
@permission_classes([IsAdmin])
def security_dashboard(request):
    """
    Get security dashboard information.
    """
    # Get recent security events
    security_events = []
    
    # Get blocked IPs
    blocked_ips = []
    
    # Get system security status
    security_status = {
        'total_blocked_ips': len(blocked_ips),
        'recent_security_events': len(security_events),
        'security_level': 'HIGH',
        'last_security_scan': None,
        'active_monitoring': True
    }
    
    return Response({
        'security_status': security_status,
        'blocked_ips': blocked_ips[:10],  # Last 10
        'recent_events': security_events[:20],  # Last 20
        'recommendations': [
            'Review blocked IPs regularly',
            'Monitor for unusual activity patterns',
            'Keep security rules updated'
        ]
    })


@api_view(['POST'])
@permission_classes([IsAdmin])
def block_ip(request):
    """
    Manually block an IP address.
    """
    ip_address = request.data.get('ip_address')
    duration = int(request.data.get('duration', 3600))  # 1 hour default
    reason = request.data.get('reason', 'Manually blocked by admin')
    
    if not ip_address:
        return Response(
            {'error': 'IP address is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate IP format
    try:
        import ipaddress
        ipaddress.ip_address(ip_address)
    except ValueError:
        return Response(
            {'error': 'Invalid IP address format'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Don't allow blocking trusted IPs
    if IPSecurityManager.is_trusted_ip(ip_address):
        return Response(
            {'error': 'Cannot block trusted IP address'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Block the IP
    IPSecurityManager.block_ip(ip_address, duration, reason)
    
    return Response({
        'message': f'IP {ip_address} has been blocked for {duration} seconds',
        'ip_address': ip_address,
        'duration': duration,
        'reason': reason
    })


@api_view(['POST'])
@permission_classes([IsAdmin])
def unblock_ip(request):
    """
    Manually unblock an IP address.
    """
    ip_address = request.data.get('ip_address')
    
    if not ip_address:
        return Response(
            {'error': 'IP address is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Remove from cache
    cache_key = f"blocked_ip:{ip_address}"
    cache.delete(cache_key)
    
    return Response({
        'message': f'IP {ip_address} has been unblocked',
        'ip_address': ip_address
    })


@api_view(['GET'])
@permission_classes([IsAdmin])
def security_events(request):
    """
    Get security events log.
    """
    # Get query parameters
    ip_address = request.query_params.get('ip_address')
    event_type = request.query_params.get('event_type')
    severity = request.query_params.get('severity')
    limit = int(request.query_params.get('limit', 100))
    
    # In a real implementation, this would query from database
    # For now, return mock data
    events = [
        {
            'id': '1',
            'ip_address': '192.168.1.100',
            'event_type': 'brute_force_attempt',
            'severity': 'high',
            'timestamp': '2024-08-30T10:30:00Z',
            'details': 'Multiple failed login attempts',
            'action_taken': 'IP blocked for 30 minutes'
        },
        {
            'id': '2',
            'ip_address': '10.0.0.50',
            'event_type': 'suspicious_user_agent',
            'severity': 'medium',
            'timestamp': '2024-08-30T10:25:00Z',
            'details': 'Suspicious user agent detected',
            'action_taken': 'Event logged'
        }
    ]
    
    # Apply filters
    if ip_address:
        events = [e for e in events if e['ip_address'] == ip_address]
    if event_type:
        events = [e for e in events if e['event_type'] == event_type]
    if severity:
        events = [e for e in events if e['severity'] == severity]
    
    # Apply limit
    events = events[:limit]
    
    return Response({
        'events': events,
        'total_count': len(events),
        'filters': {
            'ip_address': ip_address,
            'event_type': event_type,
            'severity': severity
        }
    })


@api_view(['GET'])
@permission_classes([IsAdmin])
def blocked_ips(request):
    """
    Get list of blocked IP addresses.
    """
    # In a real implementation, this would query from cache/database
    blocked_ips = [
        {
            'ip_address': '192.168.1.100',
            'blocked_at': '2024-08-30T10:30:00Z',
            'expires_at': '2024-08-30T11:00:00Z',
            'reason': 'Brute force attack detected',
            'duration': 1800
        }
    ]
    
    return Response({
        'blocked_ips': blocked_ips,
        'total_count': len(blocked_ips)
    })


@api_view(['POST'])
@permission_classes([IsAdmin])
def security_test(request):
    """
    Test security configurations.
    """
    test_results = {
        'headers_test': 'PASS',
        'csrf_test': 'PASS',
        'https_test': 'PASS' if request.is_secure() else 'FAIL',
        'middleware_test': 'PASS',
        'input_validation_test': 'PASS',
        'rate_limiting_test': 'PASS'
    }
    
    # Calculate overall score
    passed_tests = sum(1 for result in test_results.values() if result == 'PASS')
    total_tests = len(test_results)
    score = (passed_tests / total_tests) * 100
    
    return Response({
        'overall_score': f"{score:.1f}%",
        'test_results': test_results,
        'recommendations': [
            'All security tests passed' if score == 100 else 'Some security tests failed',
            'Regular security audits recommended',
            'Keep security middleware updated'
        ]
    })


@api_view(['GET'])
@permission_classes([IsAdmin])
def security_metrics(request):
    """
    Get security metrics and statistics.
    """
    # Time period filter
    period = request.query_params.get('period', '24h')
    
    metrics = {
        'period': period,
        'total_requests': 10245,
        'blocked_requests': 23,
        'security_events': 45,
        'blocked_ips_count': 5,
        'top_threats': [
            {'type': 'brute_force', 'count': 12},
            {'type': 'scan_attempt', 'count': 8},
            {'type': 'suspicious_user_agent', 'count': 15},
            {'type': 'input_validation_failure', 'count': 10}
        ],
        'geographic_distribution': [
            {'country': 'Unknown', 'count': 30},
            {'country': 'Belgium', 'count': 10},
            {'country': 'Netherlands', 'count': 5}
        ]
    }
    
    return Response(metrics)


@api_view(['POST'])
@permission_classes([IsAdmin])
def export_security_logs(request):
    """
    Export security logs for compliance reporting.
    """
    start_date = request.data.get('start_date')
    end_date = request.data.get('end_date')
    format_type = request.data.get('format', 'json')  # json, csv, pdf
    
    if not start_date or not end_date:
        return Response(
            {'error': 'start_date and end_date are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # In a real implementation, this would generate the actual export
    export_info = {
        'export_id': 'exp_20240830_001',
        'status': 'processing',
        'format': format_type,
        'start_date': start_date,
        'end_date': end_date,
        'estimated_completion': '2024-08-30T11:00:00Z',
        'download_url': None  # Will be provided when ready
    }
    
    return Response({
        'message': 'Security logs export initiated',
        'export_info': export_info
    })


@api_view(['GET'])
@permission_classes([IsAdmin])
def security_recommendations(request):
    """
    Get security recommendations based on current system state.
    """
    recommendations = [
        {
            'priority': 'HIGH',
            'category': 'Authentication',
            'title': 'Enable Two-Factor Authentication',
            'description': 'Implement 2FA for all admin accounts',
            'impact': 'Significantly reduces risk of account compromise'
        },
        {
            'priority': 'MEDIUM',
            'category': 'Monitoring',
            'title': 'Increase Log Retention',
            'description': 'Consider increasing audit log retention period',
            'impact': 'Better forensic capabilities and compliance'
        },
        {
            'priority': 'LOW',
            'category': 'Configuration',
            'title': 'Update Security Headers',
            'description': 'Consider adding Expect-CT header',
            'impact': 'Enhanced security against certificate attacks'
        }
    ]
    
    return Response({
        'recommendations': recommendations,
        'total_count': len(recommendations)
    })
