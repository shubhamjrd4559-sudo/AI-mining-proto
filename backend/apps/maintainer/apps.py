"""
apps.maintainer — AppConfig
"""

from django.apps import AppConfig


class MaintainerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.maintainer'
    verbose_name = 'Data Maintainer'
