"""
SIH26023 — Audit App Configuration.
"""

from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.audit"
    verbose_name = "Audit Trail"
