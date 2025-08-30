"""
URL configuration for Stock Management System.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API
    path('api/', include('apps.api.urls')),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # PWA
    path('', include('apps.pwa.urls')),
    
    # Health check
    path('health/', include('apps.core.urls')),
    
    # Default redirect to PWA
    path('', RedirectView.as_view(url='/app/', permanent=False)),
]

# i18n (language switching)
urlpatterns += [
    path('i18n/', include('django.conf.urls.i18n')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site customization
admin.site.site_header = "Stock Management System"
admin.site.site_title = "Stock Admin"
admin.site.index_title = "Stock Management Administration"
