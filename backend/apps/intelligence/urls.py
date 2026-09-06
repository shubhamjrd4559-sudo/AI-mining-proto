"""
apps.intelligence — URL Configuration.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('query/', views.query_view, name='intelligence-query'),
    path('history/', views.query_history_view, name='intelligence-history'),
    path('reindex/', views.reindex_view, name='intelligence-reindex'),
    # Direct endpoint alias for chat
    path('chat/', views.query_view, name='intelligence-chat'),
]
