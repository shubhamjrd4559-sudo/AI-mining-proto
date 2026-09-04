"""
SIH26023 — Structured Data Models.
Maintains canonical datasets, column schemas, and validated row records extracted from mining documents.
"""

import uuid
from django.db import models


class StructuredDataset(models.Model):
    """
    A canonical structured dataset representing an extracted table, sheet,
    or organized collection from an ingested document.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=300)
    source_document = models.ForeignKey(
        "documents.Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="datasets",
        help_text="Original source document from which this dataset was extracted.",
    )
    schema_definition = models.JSONField(
        default=dict,
        blank=True,
        help_text="Schema metadata including column names, data types, and validation constraints.",
    )
    row_count = models.IntegerField(default=0)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Structured Dataset"
        verbose_name_plural = "Structured Datasets"

    def __str__(self):
        return self.name


class StructuredRecord(models.Model):
    """
    An individual structured data row belonging to a dataset with provenance tracking
    and validation status.
    """

    class ValidationStatus(models.TextChoices):
        VALID = "valid", "Valid"
        INVALID = "invalid", "Invalid"
        NEEDS_REVIEW = "needs_review", "Needs Review"
        UNVALIDATED = "unvalidated", "Unvalidated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(
        StructuredDataset,
        on_delete=models.CASCADE,
        related_name="records",
    )
    row_data = models.JSONField(
        default=dict,
        help_text="Key-value mapping of extracted and normalized row columns.",
    )
    source_reference = models.CharField(
        max_length=500,
        blank=True,
        help_text="Provenance locator, e.g., 'doc:D-1001:page:3:table:1:row:5'.",
    )
    validation_status = models.CharField(
        max_length=50,
        choices=ValidationStatus.choices,
        default=ValidationStatus.UNVALIDATED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Structured Record"
        verbose_name_plural = "Structured Records"

    def __str__(self):
        return f"Record {self.id} ({self.dataset.name})"
