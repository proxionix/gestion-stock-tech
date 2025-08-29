"""
Core URLs for Stock Management System.
"""
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.health_check, name='health_check'),
    path('ready/', views.readiness_check, name='readiness_check'),
    path('live/', views.liveness_check, name='liveness_check'),
]
