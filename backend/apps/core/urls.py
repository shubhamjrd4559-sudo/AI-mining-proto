"""
apps.core — URL patterns

Mounts:
  GET  /api/health/
  GET  /api/analytics/
  GET  /api/chat/
  GET  /api/excel/
  GET  /api/reports/
  GET  /api/topics/
"""

from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='api-health'),
    path('analytics/', views.analytics_stub, name='api-analytics'),
    path('chat/', views.chat_stub, name='api-chat'),
    path('excel/', views.excel_stub, name='api-excel'),
    path('reports/', views.reports_stub, name='api-reports'),
    path('topics/', views.topics_stub, name='api-topics'),
]
