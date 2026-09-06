"""
Document and structured data indexing pipeline.

Ensures:
  - Only successfully processed documents are indexed
  - Safe, atomic re-indexing
  - Idempotent indexing preventing duplicate chunking of unchanged content
  - Full provenance tracking
"""

import hashlib
import logging
from typing import Tuple, Optional

from django.db import transaction
from django.utils import timezone

from apps.documents.models import Document, DocumentStatus
from apps.pipeline.models import ExtractionResult
from apps.intelligence.models import DocumentChunk
from .chunker import chunk_text, chunk_extracted_tables

logger = logging.getLogger(__name__)

INDEXABLE_STATUSES = {
    DocumentStatus.INDEXED,
    DocumentStatus.NEEDS_REVIEW,
    DocumentStatus.COMPLETED,
    DocumentStatus.PROCESSED,
}


def compute_doc_fingerprint(raw_text: str, tables: list) -> str:
    """Generate fingerprint to verify if document content has changed since last index."""
    hasher = hashlib.sha256()
    hasher.update((raw_text or '').encode('utf-8'))
    hasher.update(str(tables or []).encode('utf-8'))
    return hasher.hexdigest()


def index_document(doc_or_id, force: bool = False) -> Tuple[int, Optional[str]]:
    """
    Index an extracted document into discrete, searchable DocumentChunks.

    Returns:
      (chunks_created_count, error_message_or_note)
    """
    if isinstance(doc_or_id, Document):
        doc = doc_or_id
    else:
        try:
            doc = Document.objects.get(pk=doc_or_id)
        except Document.DoesNotExist:
            return 0, f'Document {doc_or_id} does not exist.'

    # Guard: Only index successfully extracted/validated documents
    if doc.status not in INDEXABLE_STATUSES:
        return 0, f'Document {doc.pk} status "{doc.status}" is not ready for indexing.'

    try:
        extraction = doc.extraction_result
    except ExtractionResult.DoesNotExist:
        return 0, f'No ExtractionResult found for document {doc.pk}.'

    if extraction.status not in ('completed', 'ocr_unavailable'):
        return 0, f'ExtractionResult for document {doc.pk} is incomplete ({extraction.status}).'

    raw_text = extraction.raw_text or ''
    tables = extraction.extracted_tables or []
    current_fingerprint = compute_doc_fingerprint(raw_text, tables)

    # Check if already indexed with matching fingerprint
    existing_chunks = DocumentChunk.objects.filter(document=doc)
    existing_count = existing_chunks.count()
    if existing_count > 0 and not force:
        first_chunk = existing_chunks.first()
        if first_chunk and first_chunk.metadata.get('doc_fingerprint') == current_fingerprint:
            logger.info('Document %d content unchanged; skipping duplicate indexing.', doc.pk)
            return existing_count, 'Unchanged'

    # Build chunk candidate list
    all_chunks = []
    base_meta = {
        'doc_id': doc.pk,
        'doc_title': doc.title or doc.original_filename,
        'doc_filename': doc.original_filename,
        'extractor_type': extraction.extractor_type,
        'ocr_used': extraction.ocr_used,
        'doc_fingerprint': current_fingerprint,
    }

    # 1. Text chunking
    # Check if we have page metadata to preserve exact page numbers
    page_meta_list = (extraction.extraction_metadata or {}).get('pages', [])
    if page_meta_list and len(page_meta_list) > 1:
        # If raw text contains multiple pages, we estimate split or slice
        # If pages are distinct in metadata, process per page if available
        paragraphs = raw_text.split('\n\n')
        # Approximate page assignment based on total paragraphs
        total_p = len(paragraphs)
        page_cnt = max(1, extraction.page_count or len(page_meta_list))
        for idx, para in enumerate(paragraphs):
            est_page = min(page_cnt, int((idx / max(1, total_p)) * page_cnt) + 1)
            para_chunks = chunk_text(
                para,
                page_number=est_page,
                metadata=base_meta,
            )
            all_chunks.extend(para_chunks)
    else:
        text_chunks = chunk_text(
            raw_text,
            page_number=1 if extraction.page_count == 1 else None,
            metadata=base_meta,
        )
        all_chunks.extend(text_chunks)

    # 2. Table chunking
    if tables:
        table_chunks = chunk_extracted_tables(tables, doc.pk)
        for tc in table_chunks:
            tc['metadata'].update(base_meta)
        all_chunks.extend(table_chunks)

    # Atomically replace chunks for safe re-indexing
    with transaction.atomic():
        DocumentChunk.objects.filter(document=doc).delete()

        chunk_objects = []
        for idx, item in enumerate(all_chunks):
            chunk_objects.append(DocumentChunk(
                document=doc,
                chunk_index=idx,
                content=item['content'],
                content_hash=item['content_hash'],
                page_number=item.get('page_number'),
                section_heading=item.get('section_heading') or '',
                metadata=item.get('metadata') or {},
                token_count=item.get('token_count') or 0,
            ))

        if chunk_objects:
            DocumentChunk.objects.bulk_create(chunk_objects)

    logger.info('Indexed document %d: created %d chunks.', doc.pk, len(chunk_objects))
    return len(chunk_objects), None


def reindex_all_documents(user=None, force: bool = True) -> Tuple[int, int]:
    """
    Re-index all documents (optionally filtered by user).
    Returns (total_docs_indexed, total_chunks_created).
    """
    qs = Document.objects.filter(status__in=INDEXABLE_STATUSES, is_archived=False)
    if user:
        qs = qs.filter(uploaded_by=user)

    total_chunks = 0
    indexed_docs = 0
    for doc in qs:
        count, err = index_document(doc, force=force)
        if count > 0:
            total_chunks += count
            indexed_docs += 1

    return indexed_docs, total_chunks
