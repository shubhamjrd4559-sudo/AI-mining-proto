"""
SIH26023 — Structured Data App Configuration.
"""

from django.apps import AppConfig


class StructuredDataConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.structured_data"
    verbose_name = "Structured Data"
