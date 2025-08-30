"""
PWA views for Stock Management System.
"""
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils.translation import gettext as _
from apps.inventory.models import Article
from apps.orders.services.panier_service import PanierService
from apps.inventory.services.stock_service import StockService


def app_home(request):
    """
    PWA home page - redirects to login if not authenticated.
    """
    if not request.user.is_authenticated:
        return redirect('admin:login')
    
    if not hasattr(request.user, 'profile'):
        messages.error(request, _('No profile found. Please contact administrator.'))
        return redirect('admin:login')
    
    context = {
        'user': request.user,
        'profile': request.user.profile,
        'page_title': _('Stock Management'),
    }
    
    return render(request, 'pwa/home.html', context)


@login_required
def scan_qr(request):
    """
    QR code scanning page with camera access.
    """
    context = {
        'page_title': _('Scan QR Code'),
    }
    return render(request, 'pwa/scan.html', context)


@login_required
def article_detail(request, reference):
    """
    Article detail page (accessed via QR code).
    """
    article = get_object_or_404(Article, reference=reference, is_active=True)
    
    # Get current stock if user is a technician
    current_stock = None
    if hasattr(request.user, 'profile') and request.user.profile.is_technician:
        try:
            from apps.inventory.models import StockTech
            stock = StockTech.objects.get(
                technician=request.user.profile,
                article=article
            )
            current_stock = stock.available_quantity
        except StockTech.DoesNotExist:
            current_stock = 0
    
    context = {
        'article': article,
        'current_stock': current_stock,
        'page_title': f'{article.reference} - {article.name}',
        'can_add_to_cart': (
            hasattr(request.user, 'profile') and 
            request.user.profile.is_technician
        ),
        'can_declare_usage': (
            hasattr(request.user, 'profile') and 
            request.user.profile.is_technician and
            current_stock and current_stock > 0
        ),
    }
    
    return render(request, 'pwa/article_detail.html', context)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def quick_add_to_cart(request):
    """
    Quick add to cart from QR scan.
    """
    if not hasattr(request.user, 'profile') or not request.user.profile.is_technician:
        return JsonResponse({
            'success': False,
            'error': _('Only technicians can add items to cart')
        }, status=403)
    
    try:
        data = json.loads(request.body)
        article_reference = data.get('article_reference')
        quantity = float(data.get('quantity', 1))
        notes = data.get('notes', '')
        
        if not article_reference:
            return JsonResponse({
                'success': False,
                'error': _('Article reference is required')
            }, status=400)
        
        if quantity <= 0:
            return JsonResponse({
                'success': False,
                'error': _('Quantity must be positive')
            }, status=400)
        
        # Get article
        article = Article.objects.get(reference=article_reference, is_active=True)
        
        # Add to cart
        line = PanierService.add_to_cart(
            technician=request.user.profile,
            article=article,
            quantity=quantity,
            notes=notes
        )
        
        return JsonResponse({
            'success': True,
            'message': _('Item added to cart successfully'),
            'line_id': str(line.id),
            'quantity': str(line.quantity)
        })
        
    except Article.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Article not found')
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def quick_declare_usage(request):
    """
    Quick declare usage from QR scan.
    """
    if not hasattr(request.user, 'profile') or not request.user.profile.is_technician:
        return JsonResponse({
            'success': False,
            'error': _('Only technicians can declare usage')
        }, status=403)
    
    try:
        data = json.loads(request.body)
        article_reference = data.get('article_reference')
        quantity = float(data.get('quantity', 1))
        location = data.get('location', '')
        notes = data.get('notes', '')
        
        if not article_reference:
            return JsonResponse({
                'success': False,
                'error': _('Article reference is required')
            }, status=400)
        
        if quantity <= 0:
            return JsonResponse({
                'success': False,
                'error': _('Quantity must be positive')
            }, status=400)
        
        if not location:
            return JsonResponse({
                'success': False,
                'error': _('Location is required')
            }, status=400)
        
        # Get article
        article = Article.objects.get(reference=article_reference, is_active=True)
        
        # Declare usage
        movement = StockService.issue_stock(
            technician=request.user.profile,
            article=article,
            quantity=quantity,
            location_text=location,
            performed_by=request.user,
            notes=notes
        )
        
        return JsonResponse({
            'success': True,
            'message': _('Usage declared successfully'),
            'movement_id': str(movement.id),
            'balance_after': str(movement.balance_after)
        })
        
    except Article.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': _('Article not found')
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required
def my_cart_view(request):
    """
    My cart page.
    """
    if not hasattr(request.user, 'profile') or not request.user.profile.is_technician:
        messages.error(request, _('Only technicians have carts'))
        return redirect('pwa:home')
    
    cart_summary = PanierService.get_cart_summary(request.user.profile)
    
    context = {
        'cart': cart_summary,
        'page_title': _('My Cart'),
    }
    
    return render(request, 'pwa/cart.html', context)


@login_required
def my_demands_view(request):
    """
    My demands page.
    """
    if not hasattr(request.user, 'profile'):
        messages.error(request, _('No profile found'))
        return redirect('pwa:home')
    
    from apps.orders.models import Demande
    
    if request.user.profile.is_technician:
        demands = Demande.objects.filter(
            technician=request.user.profile
        ).order_by('-created_at')
    else:
        # Admins see all demands
        demands = Demande.objects.all().order_by('-created_at')
    
    context = {
        'demands': demands[:20],  # Limit to recent 20
        'page_title': _('My Demands') if request.user.profile.is_technician else _('All Demands'),
        'is_admin': request.user.profile.is_admin,
    }
    
    return render(request, 'pwa/demands.html', context)


def manifest_json(request):
    """
    PWA manifest.json
    """
    manifest = {
        "name": "Stock Management System",
        "short_name": "StockMgmt",
        "description": "Enterprise Stock Management System for Technicians",
        "start_url": "/app/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#2563eb",
        "orientation": "portrait",
        "icons": [
            {
                "src": "/static/pwa/icon-192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/pwa/icon-512.png",
                "sizes": "512x512", 
                "type": "image/png"
            }
        ],
        "screenshots": [
            {
                "src": "/static/pwa/screenshot-1.png",
                "sizes": "1080x1920",
                "type": "image/png"
            }
        ],
        "categories": ["productivity", "business"],
        "lang": "fr",
        "scope": "/app/",
        "permissions": ["camera"]
    }
    
    return JsonResponse(manifest)


def service_worker_js(request):
    """
    Service Worker for PWA offline functionality.
    """
    service_worker_content = """
const CACHE_NAME = 'stock-mgmt-v1';
const urlsToCache = [
  '/app/',
  '/app/scan/',
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/js/qr-scanner.js',
  '/static/pwa/icon-192.png',
  '/static/pwa/icon-512.png'
];

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', function(event) {
  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        // Cache hit - return response
        if (response) {
          return response;
        }
        return fetch(event.request);
      }
    )
  );
});

self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.map(function(cacheName) {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});
"""
    
    return HttpResponse(
        service_worker_content,
        content_type='application/javascript'
    )
