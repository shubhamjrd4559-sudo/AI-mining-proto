"""
apps.datasets — URL patterns (Phase 6 Data Explorer)
"""

from django.urls import path
from . import views

urlpatterns = [
    # Phase 1 backward-compatible stub (name='api-datasets')
    path('', views.dataset_list_stub, name='api-datasets'),

    # Phase 6 Data Explorer endpoints
    path('list/', views.dataset_list, name='api-datasets-list'),
    path('<int:dataset_id>/schema/', views.dataset_schema, name='api-dataset-schema'),
    path('<int:dataset_id>/records/', views.dataset_records, name='api-dataset-records'),
    path('<int:dataset_id>/records/<int:record_id>/', views.dataset_record_detail, name='api-dataset-record-detail'),
    path('<int:dataset_id>/export/csv/', views.dataset_export_csv, name='api-dataset-export-csv'),
]
