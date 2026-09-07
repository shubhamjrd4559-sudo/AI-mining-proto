"""
apps.reports — Report Models (Phase 7)

Provides persistent, auditable, owner-scoped reports with full lifecycle state machine:
DRAFT → GENERATING → GENERATED → UNDER_REVIEW → VERIFIED → APPROVED → EXPORTED
"""

from django.db import models
from django.conf import settings


class ReportType(models.TextChoices):
    PRODUCTION = 'Production Report', 'Production Report'
    GEOLOGICAL_EXPLORATION = 'Geological & Exploration Report', 'Geological & Exploration Report'
    MINING_PERFORMANCE = 'Mining Performance Report', 'Mining Performance Report'
    EXPLORATION = 'Exploration Report', 'Exploration Report'
    COAL_SEAM = 'Coal Seam Analysis', 'Coal Seam Analysis'
    PARLIAMENTARY_QUESTION = 'Parliamentary Question Response', 'Parliamentary Question Response'
    ADMINISTRATIVE_QUERY = 'Administrative Query', 'Administrative Query'
    CUSTOM = 'Custom Report', 'Custom Report'


class ReportStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    GENERATING = 'GENERATING', 'Generating'
    GENERATED = 'GENERATED', 'Generated'
    UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
    VERIFIED = 'VERIFIED', 'Verified'
    APPROVED = 'APPROVED', 'Approved'
    EXPORTED = 'EXPORTED', 'Exported'
    FAILED = 'FAILED', 'Failed'


class Report(models.Model):
    """
    Official generated report entity.
    Maintains complete separation between source datasets and generated/edited report content.
    """
    title = models.CharField(max_length=256)
    report_type = models.CharField(
        max_length=64,
        choices=ReportType.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=32,
        choices=ReportStatus.choices,
        default=ReportStatus.DRAFT,
        db_index=True,
    )
    organization = models.CharField(max_length=128, default='CMPDI (HQ)', blank=True)
    date_range = models.CharField(max_length=128, default='All Available', blank=True)
    filters_json = models.JSONField(
        default=dict,
        blank=True,
        help_text='Filter criteria applied during report generation (e.g. subsidiary, FY).',
    )
    source_datasets = models.ManyToManyField(
        'datasets.StructuredDataset',
        blank=True,
        related_name='reports',
        help_text='Underlying structured datasets providing verified facts and figures.',
    )
    source_documents = models.ManyToManyField(
        'documents.Document',
        blank=True,
        related_name='reports',
        help_text='Source documents providing narrative and context evidence.',
    )
    content_json = models.JSONField(
        default=dict,
        blank=True,
        help_text='Full structured content of the report (summary, KPIs, tables, trends, analysis, etc.).',
    )
    provenance_json = models.JSONField(
        default=list,
        blank=True,
        help_text='Source-backed traceability citations for all critical numbers and statements.',
    )
    export_format = models.CharField(max_length=16, blank=True, default='')

    # Authorship & Governance
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_reports',
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='verified_reports',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_reports',
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True, default='')
    revision_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'

    def __str__(self):
        return f'{self.title} [{self.report_type}] ({self.status})'
