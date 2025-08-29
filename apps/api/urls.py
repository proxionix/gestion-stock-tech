"""
API URLs for Stock Management System.
"""
from django.urls import path, include
from apps.api.views import auth_views, inventory_views, orders_views
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
]

# Main URL patterns
urlpatterns = [
    # Health check
    path('health/', health_check, name='health'),
    
    # Authentication
    path('auth/', include(auth_urlpatterns)),
    
    # Inventory
    path('', include(inventory_urlpatterns)),
    
    # Orders
    path('', include(orders_urlpatterns)),
]
