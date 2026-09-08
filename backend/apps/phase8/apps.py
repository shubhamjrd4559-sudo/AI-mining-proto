"""
apps.phase8.apps — Django AppConfig for Phase 8
"""
from django.apps import AppConfig


class Phase8Config(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.phase8"
    label = "phase8"
    verbose_name = "Phase 8: Topics, Mining Map & Geological View"

