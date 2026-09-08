"""
apps.frontend — Django app configuration

Provides a minimal Django app that owns:
  - The root view rendering the frontend template at '/'
  - Integration tests for the Django-hosted frontend

This app does NOT own any models, migrations, or API endpoints.
"""

from django.apps import AppConfig


class FrontendConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.frontend'
    label = 'frontend'
    verbose_name = 'Frontend Integration'
