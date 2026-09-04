"""
SIH26023 — Documents Admin Registration.
"""

from django.contrib import admin
from .models import Document, ProcessingJob


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "original_filename",
        "file_type",
        "file_size",
        "status",
        "processing_progress",
        "uploaded_by",
        "uploaded_at",
        "created_at",
    )
    list_filter = ("status", "file_type", "uploaded_at")
    search_fields = ("original_filename", "uploaded_by", "id")
    readonly_fields = ("id", "uploaded_at", "created_at", "updated_at")


@admin.register(ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "document",
        "job_type",
        "status",
        "progress",
        "started_at",
        "completed_at",
        "created_at",
    )
    list_filter = ("job_type", "status", "created_at")
    search_fields = ("document__original_filename", "id")
    readonly_fields = ("id", "created_at")
