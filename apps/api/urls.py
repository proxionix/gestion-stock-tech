"""
API URLs for Stock Management System.
"""
from django.urls import path, include
from apps.api.views import auth_views, inventory_views, orders_views, qr_views, security_views
from apps.core.views import health_check

app_name = 'api'

# Authentication URLs
auth_urlpatterns = [
    path('login/', auth_views.login, name='login'),
    path('refresh/', auth_views.refresh_token, name='refresh_token'),
    path('me/', auth_views.me, name='me'),
    path('logout/', auth_views.logout, name='logout'),
]

# Inventory URLs
inventory_urlpatterns = [
    path('articles/', inventory_views.ArticleListCreateView.as_view(), name='article_list'),
    path('articles/<uuid:pk>/', inventory_views.ArticleDetailView.as_view(), name='article_detail'),
    path('my/stock/', inventory_views.my_stock, name='my_stock'),
    path('tech/<uuid:technician_id>/stock/', inventory_views.technician_stock, name='technician_stock'),
    path('use/', inventory_views.issue_stock, name='issue_stock'),
    path('admin/adjust-stock/', inventory_views.admin_adjust_stock, name='admin_adjust_stock'),
]

# QR Code URLs
qr_urlpatterns = [
    path('articles/<uuid:article_id>/qr/', qr_views.get_article_qr, name='get_article_qr'),
    path('articles/<uuid:article_id>/qr/regenerate/', qr_views.regenerate_article_qr, name='regenerate_article_qr'),
    path('articles/<uuid:article_id>/qr/print-sheet/', qr_views.print_qr_sheet, name='print_qr_sheet'),
    path('articles/qr/print-multiple/', qr_views.print_multiple_qr_sheet, name='print_multiple_qr_sheet'),
    path('articles/qr/templates/', qr_views.get_print_templates, name='get_print_templates'),
    path('articles/qr/preview/', qr_views.preview_qr_layout, name='preview_qr_layout'),
    path('articles/qr/regenerate-all/', qr_views.regenerate_all_qr_codes, name='regenerate_all_qr_codes'),
]

# Security URLs (Admin only)
security_urlpatterns = [
    path('security/dashboard/', security_views.security_dashboard, name='security_dashboard'),
    path('security/block-ip/', security_views.block_ip, name='block_ip'),
    path('security/unblock-ip/', security_views.unblock_ip, name='unblock_ip'),
    path('security/events/', security_views.security_events, name='security_events'),
    path('security/blocked-ips/', security_views.blocked_ips, name='blocked_ips'),
    path('security/test/', security_views.security_test, name='security_test'),
    path('security/metrics/', security_views.security_metrics, name='security_metrics'),
    path('security/export-logs/', security_views.export_security_logs, name='export_security_logs'),
    path('security/recommendations/', security_views.security_recommendations, name='security_recommendations'),
]

# Orders URLs
orders_urlpatterns = [
    # Cart management
    path('my/cart/', orders_views.my_cart, name='my_cart'),
    path('my/cart/add/', orders_views.add_to_cart, name='add_to_cart'),
    path('my/cart/line/<uuid:line_id>/', orders_views.update_cart_line, name='update_cart_line'),
    path('my/cart/submit/', orders_views.submit_cart, name='submit_cart'),
    
    # Demands management
    path('demandes/', orders_views.DemandeListView.as_view(), name='demande_list'),
    path('demandes/<uuid:pk>/', orders_views.DemandeDetailView.as_view(), name='demande_detail'),
    path('demandes/queue/', orders_views.demands_queue, name='demands_queue'),
    
    # Admin workflow
    path('demandes/<uuid:demande_id>/approve_all/', orders_views.approve_demand_all, name='approve_demand_all'),
    path('demandes/<uuid:demande_id>/approve_partial/', orders_views.approve_demand_partial, name='approve_demand_partial'),
    path('demandes/<uuid:demande_id>/refuse/', orders_views.refuse_demand, name='refuse_demand'),
    path('demandes/<uuid:demande_id>/prepare/', orders_views.prepare_demand, name='prepare_demand'),
    path('demandes/<uuid:demande_id>/handover/', orders_views.handover_demand, name='handover_demand'),

    # Reservations
    path('reservations/', orders_views.list_reservations, name='reservations_list'),
    path('reservations/create/', orders_views.create_reservation, name='reservation_create'),
    path('reservations/<uuid:reservation_id>/approve/', orders_views.approve_reservation, name='reservation_approve'),
    path('reservations/<uuid:reservation_id>/cancel/', orders_views.cancel_reservation, name='reservation_cancel'),

    # Transfers
    path('transfers/', orders_views.transfer_stock, name='transfer_stock'),
]

# Main URL patterns
urlpatterns = [
    # Health check
    path('health/', health_check, name='health'),
    
    # Authentication
    path('auth/', include(auth_urlpatterns)),
    
    # Inventory
    path('', include(inventory_urlpatterns)),
    
    # QR Codes
    path('', include(qr_urlpatterns)),
    
    # Security (Admin only)
    path('', include(security_urlpatterns)),
    
    # Orders
    path('', include(orders_urlpatterns)),
]
