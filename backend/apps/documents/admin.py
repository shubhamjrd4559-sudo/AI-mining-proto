"""
apps.documents — Document and ProcessingJob Django admin registration.
"""
from django.contrib import admin
from .models import Document, ProcessingJob


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'original_filename',
        'file_extension',
        'file_size',
        'status',
        'uploaded_by',
        'created_at',
    )
    list_filter = ('status', 'file_extension', 'created_at')
    search_fields = ('original_filename', 'uploaded_by__username', 'sha256_hash')
    readonly_fields = ('id', 'sha256_hash', 'storage_key', 'created_at', 'updated_at')


@admin.register(ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'document',
        'job_type',
        'status',
        'started_at',
        'completed_at',
        'created_at',
    )
    list_filter = ('job_type', 'status', 'created_at')
    search_fields = ('document__original_filename',)
    readonly_fields = ('id', 'created_at', 'updated_at')
