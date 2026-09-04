"""
apps.datasets — URL patterns
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.dataset_list_stub, name='api-datasets'),
]
