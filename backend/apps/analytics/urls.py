"""
apps.analytics — URL patterns (Phase 6)
"""

from django.urls import path
from . import views

urlpatterns = [
    path('datasets/', views.dataset_list, name='analytics-dataset-list'),
    path('kpi/', views.kpi_view, name='analytics-kpi'),
    path('trends/', views.trends_view, name='analytics-trends'),
    path('breakdown/', views.breakdown_view, name='analytics-breakdown'),
    path('query/', views.query_view, name='analytics-query'),
    path('drilldown/', views.drilldown_view, name='analytics-drilldown'),
]
