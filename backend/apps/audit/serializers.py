"""
apps.audit — Serializers (Phase 1)
"""

from rest_framework import serializers
from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            'id', 'event_type', 'actor', 'actor_ip',
            'resource_type', 'resource_id', 'description',
            'metadata_json', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']
