"""
apps.maintainer — Serializers
"""

from rest_framework import serializers
from apps.datasets.models import StructuredDataset, StructuredRecord
from apps.pipeline.models import ValidationResult
from .models import MaintainerSuggestion


class DatasetOverviewSerializer(serializers.ModelSerializer):
    """Full overview of a dataset for the maintainer workflow."""
    file_type = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()
    columns = serializers.SerializerMethodField()
    sheets = serializers.SerializerMethodField()
    detected_concepts = serializers.SerializerMethodField()
    validation_summary = serializers.SerializerMethodField()
    source_document_id = serializers.SerializerMethodField()

    class Meta:
        model = StructuredDataset
        fields = [
            'id', 'name', 'description', 'record_count',
            'filename', 'file_type', 'columns', 'sheets',
            'detected_concepts', 'validation_summary',
            'source_document_id', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_filename(self, obj):
        if obj.source_document:
            return obj.source_document.original_filename
        return obj.name

    def get_file_type(self, obj):
        if obj.source_document:
            return obj.source_document.file_extension.lstrip('.')
        return 'unknown'

    def get_columns(self, obj):
        schema = obj.schema_json or {}
        return schema.get('columns', [])

    def get_sheets(self, obj):
        schema = obj.schema_json or {}
        col_map = schema.get('column_map', {})
        # Collect sheet names from provenance of records
        sheets = set()
        for record in obj.records.all()[:50]:
            for prov in record.provenance.all():
                if prov.sheet_name:
                    sheets.add(prov.sheet_name)
        return list(sheets) if sheets else []

    def get_detected_concepts(self, obj):
        schema = obj.schema_json or {}
        col_map = schema.get('column_map', {})
        concepts = set()
        for info in col_map.values():
            c = info.get('concept') if isinstance(info, dict) else None
            if c:
                concepts.add(c)
        return sorted(concepts)

    def get_validation_summary(self, obj):
        if not obj.source_document:
            return {'error_count': 0, 'warning_count': 0, 'info_count': 0, 'total': 0}
        qs = ValidationResult.objects.filter(document=obj.source_document)
        return {
            'error_count': qs.filter(severity='ERROR').count(),
            'warning_count': qs.filter(severity='WARNING').count(),
            'info_count': qs.filter(severity='INFO').count(),
            'total': qs.count(),
        }

    def get_source_document_id(self, obj):
        if obj.source_document:
            return obj.source_document.pk
        return None


class StructuredRecordSerializer(serializers.ModelSerializer):
    """Record preview for the maintainer UI."""
    suggestions_count = serializers.SerializerMethodField()
    provenance_info = serializers.SerializerMethodField()

    class Meta:
        model = StructuredRecord
        fields = [
            'id', 'dataset', 'row_index', 'data_json',
            'is_valid', 'validation_errors',
            'suggestions_count', 'provenance_info',
            'created_at',
        ]
        read_only_fields = fields

    def get_suggestions_count(self, obj):
        return obj.suggestions.filter(
            status__in=['pending', 'approved']
        ).count()

    def get_provenance_info(self, obj):
        prov = obj.provenance.first()
        if not prov:
            return None
        return {
            'page_number': prov.page_number,
            'sheet_name': prov.sheet_name,
            'table_reference': prov.table_reference,
            'row_index': prov.row_index,
            'extraction_method': prov.extraction_method,
        }


class MaintainerSuggestionSerializer(serializers.ModelSerializer):
    """Full suggestion detail — includes before/after, status, source, provenance."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    issue_type_display = serializers.CharField(source='get_issue_type_display', read_only=True)
    suggestion_source_display = serializers.CharField(
        source='get_suggestion_source_display', read_only=True
    )
    created_by_username = serializers.SerializerMethodField()
    reviewed_by_username = serializers.SerializerMethodField()
    record_row_index = serializers.SerializerMethodField()
    has_provenance = serializers.SerializerMethodField()

    class Meta:
        model = MaintainerSuggestion
        fields = [
            'id',
            'dataset', 'record', 'document',
            'field_name',
            'original_value', 'suggested_value', 'applied_value',
            'issue_type', 'issue_type_display',
            'reason', 'confidence',
            'suggestion_source', 'suggestion_source_display',
            'status', 'status_display',
            'error_message',
            'created_by', 'created_by_username', 'created_at',
            'reviewed_by', 'reviewed_by_username', 'reviewed_at',
            'applied_at',
            'record_row_index',
            'has_provenance',
        ]
        read_only_fields = fields

    def get_created_by_username(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_reviewed_by_username(self, obj):
        return obj.reviewed_by.username if obj.reviewed_by else None

    def get_record_row_index(self, obj):
        return obj.record.row_index if obj.record else None

    def get_has_provenance(self, obj):
        return obj.provenance_id is not None
