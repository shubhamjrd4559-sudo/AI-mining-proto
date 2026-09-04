"""
SIH26023 — Documents App Configuration.
"""

from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.documents"
    verbose_name = "Documents"
