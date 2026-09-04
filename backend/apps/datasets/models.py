"""
apps.datasets — StructuredDataset and StructuredRecord models

StructuredDataset: A named collection of tabular data extracted from documents.
StructuredRecord:  A single row within a dataset, stored as JSON.

Phase 1: Models and DB tables only.
Phase 3: Populated by the document processing pipeline.
"""

from django.db import models


class StructuredDataset(models.Model):
    """
    A named tabular dataset extracted from one or more source documents.

    schema_json: describes the columns/fields of the records.
    Example:
      {"columns": ["mine_name", "coal_type", "production_mt", "year"]}
    """

    name = models.CharField(
        max_length=256,
        help_text='Human-readable name for this dataset.',
    )
    description = models.TextField(
        blank=True,
        help_text='Optional description of what this dataset contains.',
    )
    source_document = models.ForeignKey(
        'documents.Document',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='datasets',
        help_text='Primary source document (if derived from one document).',
    )
    schema_json = models.JSONField(
        default=dict,
        blank=True,
        help_text='JSON schema describing the columns/fields of records.',
    )
    record_count = models.PositiveIntegerField(
        default=0,
        help_text='Cached count of records (updated after bulk inserts).',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Structured Dataset'
        verbose_name_plural = 'Structured Datasets'

    def __str__(self):
        return f'{self.name} ({self.record_count} records)'


class StructuredRecord(models.Model):
    """
    A single data row within a StructuredDataset.

    data_json stores the actual row data as a JSON object.
    Example:
      {"mine_name": "Jharia", "coal_type": "Coking", "production_mt": 4.2, "year": 2025}
    """

    dataset = models.ForeignKey(
        StructuredDataset,
        on_delete=models.CASCADE,
        related_name='records',
    )
    row_index = models.PositiveIntegerField(
        default=0,
        help_text='Original row index from the source document.',
    )
    data_json = models.JSONField(
        default=dict,
        help_text='The actual record data as a JSON object.',
    )
    is_valid = models.BooleanField(
        default=True,
        help_text='Set to False if validation failed for this record.',
    )
    validation_errors = models.JSONField(
        default=list,
        blank=True,
        help_text='List of validation error messages.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['dataset', 'row_index']
        verbose_name = 'Structured Record'
        verbose_name_plural = 'Structured Records'

    def __str__(self):
        return f'Record {self.row_index} in {self.dataset}'
