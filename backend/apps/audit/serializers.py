"""
apps.audit — Serializers (Phase 1)
"""

from rest_framework import serializers
from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)

    class Meta:
        model = AuditEvent
        fields = [
            'id', 'event_type', 'event_type_display', 'actor', 'actor_ip',
            'resource_type', 'resource_id', 'description',
            'metadata_json', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp', 'event_type_display']
