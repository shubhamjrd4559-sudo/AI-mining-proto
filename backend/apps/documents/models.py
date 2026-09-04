"""
apps.documents — Document and ProcessingJob models

Document statuses:
  UPLOADED     → file received, not yet processed
  PROCESSING   → job queued / started
  EXTRACTING   → text/data extraction in progress
  VALIDATING   → data quality validation
  INDEXED      → data written to StructuredDataset
  NEEDS_REVIEW → flagged for human review
  COMPLETED    → fully processed and approved
  FAILED       → processing failed (see ProcessingJob.error_message)
"""

from django.db import models
from django.contrib.auth.models import User


class DocumentStatus(models.TextChoices):
    UPLOADED = 'uploaded', 'Uploaded'
    PROCESSING = 'processing', 'Processing'
    EXTRACTING = 'extracting', 'Extracting'
    VALIDATING = 'validating', 'Validating'
    INDEXED = 'indexed', 'Indexed'
    NEEDS_REVIEW = 'needs_review', 'Needs Review'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class JobStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    RUNNING = 'running', 'Running'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'


class Document(models.Model):
    """
    Represents a document uploaded into the CMPDI AI system.

    Phase 1: Model and DB table only. No upload functionality yet.
    Phase 2: File upload endpoint and storage wired.
    Phase 3: Processing pipeline activated.
    """

    title = models.CharField(
        max_length=512,
        help_text='Human-readable document title.',
    )
    file = models.FileField(
        upload_to='documents/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text='Uploaded file path (relative to MEDIA_ROOT).',
    )
    original_filename = models.CharField(
        max_length=512,
        blank=True,
        help_text='Original filename as uploaded by the user.',
    )
    file_size = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text='File size in bytes.',
    )
    mime_type = models.CharField(
        max_length=128,
        blank=True,
        help_text='MIME type detected at upload (e.g. application/pdf).',
    )
    status = models.CharField(
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.UPLOADED,
        db_index=True,
    )
    uploaded_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='uploaded_documents',
        help_text='User who uploaded this document.',
    )
    notes = models.TextField(
        blank=True,
        help_text='Reviewer notes or processing remarks.',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'

    def __str__(self):
        return f'{self.title} [{self.status}]'

    @property
    def file_size_display(self):
        """Human-readable file size string."""
        if not self.file_size:
            return 'Unknown'
        for unit in ('B', 'KB', 'MB', 'GB'):
            if self.file_size < 1024:
                return f'{self.file_size:.1f} {unit}'
            self.file_size /= 1024
        return f'{self.file_size:.1f} TB'


class ProcessingJob(models.Model):
    """
    Tracks a single processing step applied to a Document.

    One document may have multiple jobs (OCR, extraction, validation, indexing).
    Phase 1: Model only. No actual job runner yet.
    Phase 3: Celery tasks will create and update these records.
    """

    class JobType(models.TextChoices):
        OCR = 'ocr', 'OCR'
        TEXT_EXTRACTION = 'text_extraction', 'Text Extraction'
        DATA_EXTRACTION = 'data_extraction', 'Data Extraction'
        VALIDATION = 'validation', 'Validation'
        INDEXING = 'indexing', 'Indexing'
        EMBEDDING = 'embedding', 'Embedding'

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='jobs',
    )
    job_type = models.CharField(
        max_length=30,
        choices=JobType.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.PENDING,
        db_index=True,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(
        blank=True,
        help_text='Error traceback or message if job failed.',
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Job-specific metadata (page count, confidence scores, etc.).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Processing Job'
        verbose_name_plural = 'Processing Jobs'

    def __str__(self):
        return f'{self.job_type} [{self.status}] → {self.document}'
