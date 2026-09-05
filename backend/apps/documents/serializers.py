"""
apps.documents — Serializers
"""

from rest_framework import serializers
from django.conf import settings
from django.urls import reverse
from .models import Document, ProcessingJob


class ProcessingJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessingJob
        fields = [
            'id', 'document', 'job_type', 'status',
            'started_at', 'completed_at', 'error_message', 'metadata',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DocumentSerializer(serializers.ModelSerializer):
    file_size_display = serializers.ReadOnlyField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id', 'title', 'original_filename',
            'file_extension', 'file_size',
            'file_size_display', 'mime_type', 'sha256_hash',
            'status', 'error_message', 'is_archived', 'notes',
            'download_url', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'file_extension',
            'file_size', 'file_size_display', 'sha256_hash',
            'download_url', 'created_at', 'updated_at',
        ]

    def get_download_url(self, obj) -> str | None:
        if not obj.storage_key:
            return None
        request = self.context.get('request')
        url = f'/api/documents/{obj.id}/download/'
        if request:
            return request.build_absolute_uri(url)
        return url


class DocumentDetailSerializer(DocumentSerializer):
    jobs = ProcessingJobSerializer(many=True, read_only=True)
    uploaded_by_username = serializers.SerializerMethodField()

    class Meta(DocumentSerializer.Meta):
        fields = DocumentSerializer.Meta.fields + ['jobs', 'uploaded_by_username', 'extraction_summary']

    def get_uploaded_by_username(self, obj) -> str | None:
        if obj.uploaded_by:
            return obj.uploaded_by.username or obj.uploaded_by.email
        return None

    extraction_summary = serializers.SerializerMethodField()

    def get_extraction_summary(self, obj):
        try:
            er = obj.extraction_result
            return {
                'status': er.status,
                'extractor_type': er.extractor_type,
                'ocr_used': er.ocr_used,
                'page_count': er.page_count,
                'tables_count': len(er.extracted_tables),
                'error': er.error_message or None,
            }
        except Exception:
            return None

