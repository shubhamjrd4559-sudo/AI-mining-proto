"""
SIH26023 — Users App Configuration.
"""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.users"
    verbose_name = "Users"
