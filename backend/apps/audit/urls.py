"""
apps.audit — URL patterns
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.audit_list, name='api-audit'),
    path('<int:pk>/', views.audit_detail, name='api-audit-detail'),
]
