"""
SIH26023 — Audit Admin Registration.
"""

from django.contrib import admin
from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "entity_type", "entity_id", "timestamp")
    list_filter = ("action", "entity_type", "timestamp")
    search_fields = ("action", "actor", "entity_type", "entity_id")
    readonly_fields = ("id", "action", "actor", "entity_type", "entity_id",
                       "details", "ip_address", "timestamp")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
