"""
PWA URLs for Stock Management System.
"""
from django.urls import path
from . import views

app_name = 'pwa'

urlpatterns = [
    # Main PWA pages
    path('app/', views.app_home, name='home'),
    path('app/scan/', views.scan_qr, name='scan_qr'),
    path('app/cart/', views.my_cart_view, name='my_cart'),
    path('app/demands/', views.my_demands_view, name='my_demands'),
    
    # Article detail from QR code
    path('a/<str:reference>/', views.article_detail, name='article_detail'),
    
    # AJAX endpoints
    path('api/quick-add-to-cart/', views.quick_add_to_cart, name='quick_add_to_cart'),
    path('api/quick-declare-usage/', views.quick_declare_usage, name='quick_declare_usage'),
    
    # PWA files
    path('manifest.json', views.manifest_json, name='manifest'),
    path('sw.js', views.service_worker_js, name='service_worker'),
]
