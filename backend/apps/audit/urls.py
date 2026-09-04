"""
apps.audit — URL patterns
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.audit_list_stub, name='api-audit'),
]
