"""
SIH26023 — Documents and Processing Jobs Models.
Manages document ingestion metadata, immutable storage pointers, and processing pipeline jobs.
"""

import uuid
from django.db import models


class Document(models.Model):
    """
    Represents an uploaded document (PDF, scanned report, spreadsheet, etc.)
    undergoing ingestion, OCR, parsing, and structured extraction.
    """

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        EXTRACTING = "extracting", "Extracting"
        VALIDATING = "validating", "Validating"
        INDEXED = "indexed", "Indexed"
        NEEDS_REVIEW = "needs_review", "Needs Review"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_filename = models.CharField(max_length=500)
    stored_file = models.CharField(
        max_length=1000,
        blank=True,
        help_text="Storage key or relative path referencing the stored file in storage backend.",
    )
    file_type = models.CharField(max_length=50)
    file_size = models.BigIntegerField(default=0, help_text="File size in bytes.")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.CharField(
        max_length=200,
        blank=True,
        help_text="Username or identifier of the uploader (Phase 1 simple string).",
    )
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.UPLOADED,
    )
    processing_progress = models.IntegerField(
        default=0,
        help_text="Processing progress percentage from 0 to 100.",
    )
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Document"
        verbose_name_plural = "Documents"

    def __str__(self):
        return self.original_filename


class ProcessingJob(models.Model):
    """
    Tracks individual stage tasks in the document processing lifecycle
    (e.g., OCR, table extraction, schema detection, validation, indexing).
    """

    class JobType(models.TextChoices):
        OCR = "ocr", "OCR"
        TEXT_EXTRACTION = "text_extraction", "Text Extraction"
        TABLE_EXTRACTION = "table_extraction", "Table Extraction"
        SCHEMA_DETECTION = "schema_detection", "Schema Detection"
        VALIDATION = "validation", "Validation"
        INDEXING = "indexing", "Indexing"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="processing_jobs",
    )
    job_type = models.CharField(
        max_length=100,
        choices=JobType.choices,
    )
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.PENDING,
    )
    progress = models.IntegerField(
        default=0,
        help_text="Job progress percentage from 0 to 100.",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    result_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Processing Job"
        verbose_name_plural = "Processing Jobs"

    def __str__(self):
        return f"{self.get_job_type_display()} - {self.document.original_filename} ({self.get_status_display()})"
