"""
Core views for Stock Management System.
"""
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import redis


@never_cache
@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """
    Health check endpoint for monitoring.
    Returns JSON with system status.
    """
    from django.utils import timezone
    status = {
        'status': 'healthy',
        'version': '1.0.0',
        'timestamp': timezone.now().isoformat(),
        'user': getattr(request.user, 'username', None),
        'checks': {}
    }
    
    overall_healthy = True
    
    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        status['checks']['database'] = {'status': 'healthy'}
    except Exception as e:
        status['checks']['database'] = {'status': 'unhealthy', 'error': str(e)}
        overall_healthy = False
    
    # Redis/Cache check
    try:
        cache.set('health_check', 'test', 10)
        cache.get('health_check')
        status['checks']['cache'] = {'status': 'healthy'}
    except Exception as e:
        status['checks']['cache'] = {'status': 'unhealthy', 'error': str(e)}
        overall_healthy = False
    
    # Update overall status
    if not overall_healthy:
        status['status'] = 'unhealthy'
    
    status_code = 200 if overall_healthy else 503
    return JsonResponse(status, status=status_code)


@never_cache
@csrf_exempt
@require_http_methods(["GET"])
def readiness_check(request):
    """
    Readiness check for Kubernetes/Docker health checks.
    Simple endpoint that returns 200 if the app is ready.
    """
    return HttpResponse("Ready", content_type="text/plain")


@never_cache
@csrf_exempt  
@require_http_methods(["GET"])
def liveness_check(request):
    """
    Liveness check for Kubernetes/Docker health checks.
    Simple endpoint that returns 200 if the app is alive.
    """
    return HttpResponse("Alive", content_type="text/plain")
