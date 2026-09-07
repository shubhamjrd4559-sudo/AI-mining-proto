"""
apps.reports.urls — URL Routing for Reports API (Phase 7)
"""

from django.urls import path
from apps.reports import views

urlpatterns = [
    path('', views.report_list, name='report-list'),
    path('list/', views.report_list, name='report-list-alias'),
    path('options/', views.report_options, name='report-options'),
    path('generate/', views.report_generate, name='report-generate'),
    path('<int:report_id>/', views.report_detail, name='report-detail'),
    path('<int:report_id>/edit/', views.report_edit, name='report-edit'),
    path('<int:report_id>/verify/', views.report_verify, name='report-verify'),
    path('<int:report_id>/approve/', views.report_approve, name='report-approve'),
    path('<int:report_id>/export/<str:export_format>/', views.report_export, name='report-export'),
]
