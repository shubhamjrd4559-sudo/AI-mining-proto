"""
apps.documents — Serializers (Phase 1 stubs)
Full serializers implemented in Phase 2.
"""

from rest_framework import serializers
from .models import Document, ProcessingJob


class DocumentSerializer(serializers.ModelSerializer):
    file_size_display = serializers.ReadOnlyField()

    class Meta:
        model = Document
        fields = [
            'id', 'title', 'original_filename', 'file_size',
            'file_size_display', 'mime_type', 'status', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'file_size_display']


class ProcessingJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessingJob
        fields = [
            'id', 'document', 'job_type', 'status',
            'started_at', 'completed_at', 'error_message', 'metadata',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
