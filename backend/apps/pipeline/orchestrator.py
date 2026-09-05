"""
Phase 3 document processing orchestrator.
Runs in a daemon thread after upload.
"""
import logging
import traceback
import threading
from datetime import datetime, timezone
from typing import Optional

from django.db import transaction, close_old_connections
from django.utils import timezone as dj_timezone

from apps.documents.models import Document, DocumentStatus, ProcessingJob, JobStatus
from apps.datasets.models import StructuredDataset, StructuredRecord
from apps.storage.service import get_storage_service

from .extractor.pdf_extractor import extract_pdf
from .extractor.docx_extractor import extract_docx
from .extractor.xlsx_extractor import extract_xlsx
from .extractor.csv_extractor import extract_csv
from .extractor.txt_extractor import extract_txt
from .extractor.image_extractor import extract_image
from .schema.detector import map_columns
from .schema.normalizer import normalize_row
from .validation.engine import validate_dataset, ValidationFinding
from .models import ExtractionResult, ExtractionProvenance, ValidationResult

logger = logging.getLogger(__name__)

EXTRACTOR_MAP = {
    '.pdf': extract_pdf,
    '.docx': extract_docx,
    '.xlsx': extract_xlsx,
    '.csv': extract_csv,
    '.txt': extract_txt,
    '.png': extract_image,
    '.jpg': extract_image,
    '.jpeg': extract_image,
}


def trigger_processing(document_id: int) -> None:
    """Launch pipeline in a daemon thread."""
    t = threading.Thread(
        target=_run_pipeline,
        args=(document_id,),
        daemon=True,
        name=f'pipeline-doc-{document_id}'
    )
    t.start()
    logger.info('Pipeline thread started for document %d', document_id)


def _run_pipeline(document_id: int) -> None:
    """Main pipeline — runs in daemon thread."""
    # Django requires explicit DB connection management in threads
    close_old_connections()
    
    try:
        doc = Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        logger.error('Pipeline: document %d not found', document_id)
        return

    logger.info('Pipeline started: document %d (%s)', document_id, doc.original_filename)

    # --- Step 1: Mark as PROCESSING ---
    _update_doc_status(doc, DocumentStatus.PROCESSING)
    extraction_job = _create_job(doc, ProcessingJob.JobType.TEXT_EXTRACTION)
    
    # --- Step 2: Read file from storage ---
    try:
        storage = get_storage_service()
        file_bytes = storage.open(doc.storage_key)  # returns bytes directly
        if not isinstance(file_bytes, bytes):
            # Defensive: handle file-like objects (future S3 backend)
            file_bytes = file_bytes.read()
    except Exception as exc:
        _fail(doc, extraction_job, f'Cannot read file from storage: {exc}')
        return

    # --- Step 3: Dispatch extractor ---
    ext = doc.file_extension.lower() if doc.file_extension else ''
    extractor_fn = EXTRACTOR_MAP.get(ext)
    if not extractor_fn:
        _fail(doc, extraction_job, f'No extractor for file extension "{ext}"')
        return

    _update_doc_status(doc, DocumentStatus.EXTRACTING)
    _start_job(extraction_job)

    extracted = extractor_fn(file_bytes)

    # --- Step 4: Save ExtractionResult ---
    ex_status = 'completed'
    if extracted.error:
        if not extracted.raw_text and not extracted.tables:
            ex_status = 'failed'
        # else partial success
    
    # Check for OCR unavailable case
    if hasattr(extracted, 'status_note') and extracted.status_note == 'ocr_unavailable':
        ex_status = 'ocr_unavailable'

    # Serialize tables for JSON storage
    tables_json = [
        {
            'source_ref': t.source_ref,
            'headers': t.headers,
            'rows': t.rows,
            'page_number': t.page_number,
            'sheet_name': t.sheet_name,
            'section_heading': t.section_heading,
        }
        for t in extracted.tables
    ]

    try:
        with transaction.atomic():
            ex_result, created = ExtractionResult.objects.update_or_create(
                document=doc,
                defaults={
                    'extractor_type': extracted.extractor_type,
                    'ocr_used': extracted.ocr_used,
                    'page_count': extracted.page_count,
                    'extraction_metadata': extracted.metadata,
                    'raw_text': extracted.raw_text[:500000],  # cap at 500k chars
                    'extracted_tables': tables_json,
                    'status': ex_status,
                    'error_message': extracted.error or '',
                }
            )
    except Exception as exc:
        _fail(doc, extraction_job, f'Failed to save extraction result: {exc}')
        return

    if ex_status == 'failed':
        _fail(doc, extraction_job, extracted.error or 'Extraction failed')
        return

    _complete_job(extraction_job, metadata={
        'extractor': extracted.extractor_type,
        'ocr_used': extracted.ocr_used,
        'page_count': extracted.page_count,
        'tables_found': len(extracted.tables),
    })

    # --- Step 5: Schema detection + persistence ---
    dataset = None
    if extracted.tables:
        try:
            dataset = _persist_structured_data(doc, extracted)
        except Exception as exc:
            logger.error('Structured data persistence failed for doc %d: %s', document_id, exc, exc_info=True)
            # Non-fatal — continue to validation

    # --- Step 6: Validation ---
    _update_doc_status(doc, DocumentStatus.VALIDATING)
    validation_job = _create_job(doc, ProcessingJob.JobType.VALIDATION)
    _start_job(validation_job)

    try:
        # Build a column_map from all tables' headers
        all_headers = set()
        for t in extracted.tables:
            all_headers.update(t.headers)
        column_map = map_columns(list(all_headers))
        
        findings = validate_dataset(extracted.tables, column_map)
        _persist_validation_results(doc, findings)
        
        # Determine final status
        has_errors = any(f.severity == 'ERROR' for f in findings)
        final_status = DocumentStatus.NEEDS_REVIEW if has_errors else DocumentStatus.INDEXED
    except Exception as exc:
        logger.error('Validation failed for doc %d: %s', document_id, exc, exc_info=True)
        findings = []
        final_status = DocumentStatus.INDEXED  # degraded — skip validation, still indexed

    _complete_job(validation_job, metadata={
        'findings_total': len(findings),
        'errors': sum(1 for f in findings if f.severity == 'ERROR'),
        'warnings': sum(1 for f in findings if f.severity == 'WARNING'),
    })

    _update_doc_status(doc, final_status)
    logger.info('Pipeline complete: document %d → %s', document_id, final_status)


def _persist_structured_data(doc, extracted) -> Optional[object]:
    """Create StructuredDataset and StructuredRecords from extracted tables."""
    all_headers_set = set()
    for t in extracted.tables:
        all_headers_set.update(t.headers)
    column_map = map_columns(list(all_headers_set))
    
    schema = {
        'columns': list(all_headers_set),
        'column_map': column_map,
        'extractor_type': extracted.extractor_type,
    }
    
    with transaction.atomic():
        dataset = StructuredDataset.objects.create(
            name=f'{doc.original_filename} — Extracted Data',
            description=f'Auto-extracted from document ID {doc.pk} by Phase 3 pipeline.',
            source_document=doc,
            schema_json=schema,
        )
        
        record_count = 0
        for table in extracted.tables:
            if not table.headers or not table.rows:
                continue
            for r_idx, row in enumerate(table.rows):
                row_dict = {}
                for c_idx, header in enumerate(table.headers):
                    cell = row[c_idx] if c_idx < len(row) else ''
                    row_dict[header] = cell
                
                normalized = normalize_row(row_dict, column_map)
                
                source_ref = f'doc:{doc.pk}:{table.source_ref}:row:{r_idx}'
                record = StructuredRecord.objects.create(
                    dataset=dataset,
                    row_index=r_idx,
                    data_json=normalized,
                    is_valid=True,
                )
                record_count += 1
                
                # Create provenance
                ExtractionProvenance.objects.create(
                    record=record,
                    document=doc,
                    page_number=table.page_number,
                    section_heading=table.section_heading or '',
                    table_reference=table.source_ref,
                    sheet_name=table.sheet_name or '',
                    row_index=r_idx,
                    extraction_method=extracted.extractor_type,
                    ocr_used=extracted.ocr_used,
                    source_reference=source_ref,
                )
        
        dataset.record_count = record_count
        dataset.save(update_fields=['record_count'])
    
    logger.info('Persisted dataset %d with %d records for doc %d', dataset.pk, record_count, doc.pk)
    return dataset


def _persist_validation_results(doc, findings):
    """Save ValidationResult records to the database."""
    with transaction.atomic():
        objs = [
            ValidationResult(
                document=doc,
                field_name=f.field_name or '',
                issue_type=f.issue_type,
                severity=f.severity,
                original_value=str(f.original_value),
                suggested_value=str(f.suggested_value),
                explanation=f.explanation,
                confidence=f.confidence,
                status='open',
            )
            for f in findings
        ]
        if objs:
            ValidationResult.objects.bulk_create(objs)


def _update_doc_status(doc: Document, status: str) -> None:
    try:
        Document.objects.filter(pk=doc.pk).update(status=status, updated_at=dj_timezone.now())
        doc.status = status
    except Exception as exc:
        logger.error('Cannot update doc %d status to %s: %s', doc.pk, status, exc)


def _create_job(doc: Document, job_type: str) -> ProcessingJob:
    return ProcessingJob.objects.create(
        document=doc,
        job_type=job_type,
        status=JobStatus.PENDING,
    )


def _start_job(job: ProcessingJob) -> None:
    job.status = JobStatus.RUNNING
    job.started_at = dj_timezone.now()
    job.save(update_fields=['status', 'started_at'])


def _complete_job(job: ProcessingJob, metadata: dict = None) -> None:
    job.status = JobStatus.COMPLETED
    job.completed_at = dj_timezone.now()
    if metadata:
        job.metadata = metadata
    job.save(update_fields=['status', 'completed_at', 'metadata'])


def _fail(doc: Document, job: Optional[ProcessingJob], error_msg: str) -> None:
    logger.error('Pipeline FAILED for doc %d: %s', doc.pk, error_msg)
    # Truncate error message for storage
    safe_msg = str(error_msg)[:1000]
    
    if job:
        job.status = JobStatus.FAILED
        job.completed_at = dj_timezone.now()
        job.error_message = safe_msg
        job.save(update_fields=['status', 'completed_at', 'error_message'])
    
    _update_doc_status(doc, DocumentStatus.FAILED)
    
    try:
        Document.objects.filter(pk=doc.pk).update(error_message=safe_msg)
    except Exception:
        pass
