"""
apps.documents — URL patterns

Endpoints:
  POST /api/documents/             -> document_collection (upload)
  GET  /api/documents/             -> document_collection (list)
  GET  /api/documents/<id>/        -> document_detail (detail)
  DELETE /api/documents/<id>/      -> document_detail (archive / delete)
  GET  /api/documents/<id>/status/ -> document_status
  GET  /api/documents/<id>/download/ -> document_download
  POST /api/documents/<id>/retry/  -> document_retry
  POST /api/documents/<id>/archive/-> document_archive
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.document_collection, name='document-collection'),
    path('<int:pk>/', views.document_detail, name='document-detail'),
    path('<int:pk>/status/', views.document_status, name='document-status'),
    path('<int:pk>/download/', views.document_download, name='document-download'),
    path('<int:pk>/retry/', views.document_retry, name='document-retry'),
    path('<int:pk>/archive/', views.document_archive, name='document-archive'),
]

