"""
apps.intelligence — Mining Intelligence RAG Models.

Defines:
  - DocumentChunk: Granular, traceable text chunks indexed from extracted documents.
  - AIQueryLog: Query history storing questions, answers, sources, and confidence metadata.
"""

from django.db import models
from django.conf import settings


class DocumentChunk(models.Model):
    """
    A discrete chunk of text extracted from a Document, retaining page and section context.
    """
    document = models.ForeignKey(
        'documents.Document',
        on_delete=models.CASCADE,
        related_name='chunks',
        help_text='Source document for this chunk.',
    )
    chunk_index = models.PositiveIntegerField(
        help_text='0-indexed sequential position of this chunk within the document.',
    )
    content = models.TextField(
        help_text='Textual content of the chunk.',
    )
    content_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text='SHA-256 hash of the content for deduplication and idempotency.',
    )
    page_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='1-based page number where this chunk originated, if applicable.',
    )
    section_heading = models.CharField(
        max_length=512,
        blank=True,
        help_text='Heading or section title under which this chunk appears.',
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional metadata (e.g. table_reference, extractor_type, ocr_used).',
    )
    token_count = models.PositiveIntegerField(
        default=0,
        help_text='Approximate token count for the chunk.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document', 'chunk_index']
        unique_together = ('document', 'chunk_index')
        verbose_name = 'Document Chunk'
        verbose_name_plural = 'Document Chunks'

    def __str__(self):
        return f'Chunk {self.chunk_index} of {self.document.title} (Page {self.page_number or "N/A"})'


class AIQueryLog(models.Model):
    """
    Log of natural language queries, grounded answers, citations, and confidence scores.
    """
    class QueryType(models.TextChoices):
        STRUCTURED = 'STRUCTURED', 'Structured Data'
        DOCUMENT = 'DOCUMENT', 'Document Search'
        HYBRID = 'HYBRID', 'Hybrid (Structured + Document)'

    class ConfidenceLevel(models.TextChoices):
        HIGH = 'HIGH', 'High Confidence'
        MEDIUM = 'MEDIUM', 'Medium Confidence'
        LOW = 'LOW', 'Low Confidence'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_queries',
        help_text='User who submitted the query.',
    )
    question = models.TextField(
        help_text='User query text.',
    )
    query_type = models.CharField(
        max_length=32,
        choices=QueryType.choices,
        default=QueryType.DOCUMENT,
        help_text='Routing classification of the query.',
    )
    answer = models.TextField(
        help_text='Grounded answer generated for the query.',
    )
    confidence = models.CharField(
        max_length=16,
        choices=ConfidenceLevel.choices,
        default=ConfidenceLevel.LOW,
        help_text='Assessed confidence based on evidence quality.',
    )
    sources = models.JSONField(
        default=list,
        blank=True,
        help_text='List of citations with full provenance metadata.',
    )
    evidence_count = models.PositiveIntegerField(
        default=0,
        help_text='Count of evidence units supporting the answer.',
    )
    source_count = models.PositiveIntegerField(
        default=0,
        help_text='Count of distinct source documents or datasets cited.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text='When the query was executed.',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'AI Query Log'
        verbose_name_plural = 'AI Query Logs'

    def __str__(self):
        return f'[{self.confidence}] {self.user.username}: {self.question[:40]}'
