"""
apps.audit — AuditEvent Django admin registration.
"""
from django.contrib import admin
from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'actor', 'resource_type', 'resource_id', 'timestamp')
    list_filter = ('event_type', 'resource_type', 'timestamp')
    search_fields = ('event_type', 'actor', 'resource_type', 'resource_id', 'description')
    readonly_fields = (
        'id', 'event_type', 'actor', 'actor_ip', 'resource_type',
        'resource_id', 'description', 'metadata_json', 'timestamp',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
