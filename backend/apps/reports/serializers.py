"""
apps.reports.serializers — DRF Serializers for Reports
"""

from rest_framework import serializers
from apps.reports.models import Report, ReportType, ReportStatus


class ReportListSerializer(serializers.ModelSerializer):
    created_by_name = serializers.ReadOnlyField(source='created_by.username')
    verified_by_name = serializers.ReadOnlyField(source='verified_by.username')
    approved_by_name = serializers.ReadOnlyField(source='approved_by.username')

    class Meta:
        model = Report
        fields = (
            'id',
            'title',
            'report_type',
            'status',
            'organization',
            'date_range',
            'export_format',
            'revision_count',
            'created_by_name',
            'verified_by_name',
            'approved_by_name',
            'verified_at',
            'approved_at',
            'created_at',
            'updated_at',
        )


class ReportDetailSerializer(serializers.ModelSerializer):
    created_by_name = serializers.ReadOnlyField(source='created_by.username')
    verified_by_name = serializers.ReadOnlyField(source='verified_by.username')
    approved_by_name = serializers.ReadOnlyField(source='approved_by.username')

    class Meta:
        model = Report
        fields = (
            'id',
            'title',
            'report_type',
            'status',
            'organization',
            'date_range',
            'filters_json',
            'content_json',
            'provenance_json',
            'export_format',
            'revision_count',
            'approval_notes',
            'error_message',
            'created_by_name',
            'verified_by_name',
            'approved_by_name',
            'verified_at',
            'approved_at',
            'created_at',
            'updated_at',
        )


class ReportGenerateRequestSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True, max_length=256)
    report_type = serializers.ChoiceField(choices=ReportType.choices, default=ReportType.PRODUCTION)
    organization = serializers.CharField(required=False, default='CMPDI (HQ)', max_length=128)
    date_range = serializers.CharField(required=False, default='All Available', max_length=128)
    filters = serializers.DictField(required=False, default=dict)
    source_dataset_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
    )
    source_document_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
    )


class ReportEditSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, max_length=256)
    executive_summary = serializers.CharField(required=False, allow_blank=True)
    analysis = serializers.CharField(required=False, allow_blank=True)
    conclusions = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class ReportApproveSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default='')
