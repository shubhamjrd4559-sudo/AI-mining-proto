from django.urls import path
from . import views

urlpatterns = [
    path('documents/<int:pk>/extraction/', views.extraction_detail, name='document-extraction'),
]
