"""
apps.maintainer — URL patterns
"""

from django.urls import path
from . import views

urlpatterns = [
    # Dataset-level
    path('datasets/', views.dataset_list, name='maintainer-dataset-list'),
    path('datasets/<int:dataset_id>/overview/', views.dataset_overview, name='maintainer-dataset-overview'),
    path('datasets/<int:dataset_id>/records/', views.dataset_records, name='maintainer-dataset-records'),
    path('datasets/<int:dataset_id>/suggestions/', views.dataset_suggestions, name='maintainer-dataset-suggestions'),
    path('datasets/<int:dataset_id>/validation-issues/', views.dataset_validation_issues, name='maintainer-validation-issues'),
    path('datasets/<int:dataset_id>/generate-suggestions/', views.generate_suggestions, name='maintainer-generate-suggestions'),
    path('datasets/<int:dataset_id>/apply/', views.apply_approved, name='maintainer-apply'),
    path('datasets/<int:dataset_id>/export/xlsx/', views.export_xlsx, name='maintainer-export-xlsx'),
    path('datasets/<int:dataset_id>/export/csv/', views.export_csv, name='maintainer-export-csv'),

    # Suggestion-level
    path('suggestions/<int:suggestion_id>/approve/', views.approve_suggestion, name='maintainer-approve'),
    path('suggestions/<int:suggestion_id>/reject/', views.reject_suggestion, name='maintainer-reject'),
    path('suggestions/batch-review/', views.batch_review, name='maintainer-batch-review'),
]
