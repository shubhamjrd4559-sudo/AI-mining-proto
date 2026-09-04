"""
apps.datasets — Serializers (Phase 1 stubs)
"""

from rest_framework import serializers
from .models import StructuredDataset, StructuredRecord


class StructuredDatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = StructuredDataset
        fields = [
            'id', 'name', 'description', 'source_document',
            'schema_json', 'record_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StructuredRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = StructuredRecord
        fields = [
            'id', 'dataset', 'row_index', 'data_json',
            'is_valid', 'validation_errors', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
