"""
apps.documents — URL patterns

GET /api/documents/ → Phase 1 stub
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.document_list_stub, name='api-documents'),
]
