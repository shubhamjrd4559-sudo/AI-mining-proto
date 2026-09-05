"""
apps.documents — Views

Phase 2 Real Document Upload, Storage, and Management API.
Endpoints:
  POST /api/documents/            → Upload single or multiple documents
  GET  /api/documents/            → List documents (filters: status, search, archived, pagination)
  GET  /api/documents/<id>/       → Retrieve document details with jobs
  GET  /api/documents/<id>/status/→ Lightweight status query
  GET  /api/documents/<id>/download/ → Download original file
  POST /api/documents/<id>/retry/ → Reset status for processing retry
  POST /api/documents/<id>/archive/ → Archive / soft-delete document
  DELETE /api/documents/<id>/     → Delete document (soft or ?hard=true)
"""

import io
import os
import re
import uuid
import hashlib
import logging
import mimetypes
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone as dj_timezone

from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.storage.service import get_storage_service
from apps.audit.models import AuditEvent, AuditEventType
from .models import Document, DocumentStatus, ProcessingJob, JobStatus
from .serializers import DocumentSerializer, DocumentDetailSerializer

logger = logging.getLogger(__name__)


def get_client_ip(request) -> str | None:
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal or invalid characters."""
    clean = os.path.basename(filename)
    clean = re.sub(r'[^a-zA-Z0-9_.\- ]', '_', clean)
    clean = clean.strip()
    return clean or 'unnamed_document'


def _validate_openxml_structure(content: bytes, ext: str, raw_name: str) -> tuple[bool, str | None]:
    """
    Validate DOCX/XLSX internal ZIP structure.
    A valid OpenXML file must:
      - Be openable as a ZIP archive
      - Contain [Content_Types].xml
      - Contain word/document.xml  (DOCX) or xl/workbook.xml (XLSX)
    Rejects arbitrary ZIP files masquerading as Office documents.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = zf.namelist()
    except zipfile.BadZipFile:
        return False, f"File '{raw_name}' cannot be opened as a ZIP archive (corrupt or invalid OpenXML)."

    if '[Content_Types].xml' not in names:
        return False, (
            f"File '{raw_name}' is missing '[Content_Types].xml' — not a valid OpenXML Office document."
        )

    if ext == '.docx' and 'word/document.xml' not in names:
        return False, (
            f"File '{raw_name}' is missing 'word/document.xml' — not a valid DOCX document."
        )

    if ext == '.xlsx' and 'xl/workbook.xml' not in names:
        return False, (
            f"File '{raw_name}' is missing 'xl/workbook.xml' — not a valid XLSX spreadsheet."
        )

    return True, None


def validate_file_content_and_signature(content: bytes, ext: str, raw_name: str) -> tuple[bool, str | None]:
    """
    Validate file magic bytes and content structure against declared extension.
    Rejects spoofed, renamed, or malformed files.
    For DOCX/XLSX: also validates internal OpenXML ZIP structure.
    """
    if len(content) == 0:
        return False, f"File '{raw_name}' contains no readable data (0 bytes)."

    # 1. PDF: must begin with %PDF
    if ext == '.pdf':
        if not content.startswith(b'%PDF'):
            return False, f"File '{raw_name}' is not a valid PDF (invalid signature header)."

    # 2. PNG: must begin with standard PNG signature
    elif ext == '.png':
        if not content.startswith(b'\x89PNG\r\n\x1a\n'):
            return False, f"File '{raw_name}' is not a valid PNG image (invalid signature header)."

    # 3. JPEG / JPG: must begin with standard JPEG SOI marker
    elif ext in ('.jpg', '.jpeg'):
        if not content.startswith(b'\xff\xd8\xff'):
            return False, f"File '{raw_name}' is not a valid JPEG image (invalid signature header)."

    # 4. DOCX / XLSX: ZIP-based OpenXML formats — validate magic bytes AND internal structure
    elif ext in ('.docx', '.xlsx'):
        if not content.startswith(b'PK\x03\x04'):
            return False, f"File '{raw_name}' is not a valid OpenXML document (missing ZIP container signature)."
        # Validate internal OpenXML structure (rejects arbitrary ZIPs)
        ok, err = _validate_openxml_structure(content, ext, raw_name)
        if not ok:
            return False, err

    # 5. TXT / CSV: Plain text formats
    elif ext in ('.txt', '.csv'):
        # Reject executable signatures
        if (content.startswith(b'MZ') or content.startswith(b'\x7fELF')
                or content.startswith(b'%PDF-') or content.startswith(b'\x89PNG')):
            return False, f"File '{raw_name}' contains binary executable/image data for text format '{ext}'."
        # Verify text decodability and absence of NUL bytes
        if b'\x00' in content[:4096]:
            return False, f"File '{raw_name}' contains binary null bytes and is not valid text/CSV."
        try:
            content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                content.decode('latin-1')
            except Exception:
                return False, f"File '{raw_name}' cannot be decoded as text."

    return True, None


def _require_owner(doc: 'Document', request) -> Response | None:
    """
    Return a 403 Response if request.user is not the document owner.
    Returns None if ownership check passes.
    Uses 403 (not 404) because the document ID came from an authenticated
    context — leaking existence is acceptable; allowing access is not.
    """
    if doc.uploaded_by is not None and doc.uploaded_by != request.user:
        return Response(
            {'error': 'You do not have permission to access this document.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def log_audit(request, event_type: str, resource_id: str, description: str,
              metadata: dict | None = None) -> None:
    """
    Create an AuditEvent record.
    Must be called inside a transaction.atomic() block so that audit failure
    triggers a rollback of the enclosing operation.
    Callers outside a transaction should catch exceptions and return 500.
    """
    actor = request.user.username if (request.user and request.user.is_authenticated) else 'anonymous'
    actor_ip = get_client_ip(request)
    AuditEvent.objects.create(
        event_type=event_type,
        actor=actor,
        actor_ip=actor_ip,
        resource_type='document',
        resource_id=str(resource_id),
        description=description,
        metadata_json=metadata or {},
    )


def process_single_upload(uploaded_file, request, custom_title: str | None = None) -> tuple['Document | None', str | None]:
    """
    Validate, store, and create a Document record for a single uploaded file.
    Storage save + Document + ProcessingJob + AuditEvent are all atomic.
    Returns (document_instance, error_message).
    """
    raw_name = getattr(uploaded_file, 'name', '') or 'unnamed'
    clean_name = sanitize_filename(raw_name)
    base_name, ext = os.path.splitext(clean_name)
    ext = ext.lower()

    # 1. Validate extension against allowlist
    allowed_exts = getattr(
        settings,
        'ALLOWED_DOCUMENT_EXTENSIONS',
        {'.pdf', '.docx', '.xlsx', '.csv', '.txt', '.png', '.jpg', '.jpeg'}
    )
    if ext not in allowed_exts:
        return None, (
            f"Unsupported file format '{ext}'. "
            f"Supported formats: {', '.join(sorted(allowed_exts))}"
        )

    # 2. Validate file size and non-empty content
    file_size = getattr(uploaded_file, 'size', 0)
    max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 50 * 1024 * 1024)

    if file_size <= 0:
        return None, f"File '{raw_name}' is empty (0 bytes)."

    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        return None, f"File '{raw_name}' exceeds maximum allowed size of {max_mb:.0f}MB."

    # 3. Read content
    try:
        uploaded_file.seek(0)
        content = uploaded_file.read()
    except Exception as exc:
        logger.error("Failed to read uploaded file '%s': %s", raw_name, exc)
        return None, f"Could not read upload payload for '{raw_name}'."

    # 4. Deep magic-bytes and signature validation (server-side, ignores client MIME header)
    is_valid_sig, sig_error = validate_file_content_and_signature(content, ext, clean_name)
    if not is_valid_sig:
        return None, sig_error

    # 5. Compute SHA-256 hash
    sha256_hash = hashlib.sha256(content).hexdigest()

    # 6. Detect MIME type from extension (do NOT trust client-reported content_type)
    detected_mime = mimetypes.guess_type(clean_name)[0] or 'application/octet-stream'

    # 7. Generate safe storage key
    now = dj_timezone.now()
    unique_prefix = uuid.uuid4().hex[:12]
    safe_base = re.sub(r'[^a-zA-Z0-9_\-]', '_', base_name)[:60]
    storage_filename = f"{unique_prefix}_{safe_base}{ext}"
    storage_key = f"documents/{now.year}/{now.month:02d}/{now.day:02d}/{storage_filename}"

    # 8. Persist to storage (outside transaction — compensating delete on failure)
    storage = get_storage_service()
    try:
        storage.save(storage_key, content)
    except Exception as exc:
        logger.error("Storage backend error saving '%s': %s", storage_key, exc)
        return None, f"Storage error while saving file '{raw_name}'."

    # 9. Create database records + audit inside one atomic transaction
    doc_title = custom_title.strip() if (custom_title and custom_title.strip()) else clean_name
    user = request.user if (request.user and request.user.is_authenticated) else None

    try:
        with transaction.atomic():
            doc = Document.objects.create(
                title=doc_title,
                original_filename=clean_name,
                stored_filename=storage_filename,
                storage_key=storage_key,
                file_extension=ext,
                file_size=len(content),
                mime_type=detected_mime,
                sha256_hash=sha256_hash,
                status=DocumentStatus.UPLOADED,
                uploaded_by=user,
                is_archived=False,
            )

            # Create initial pending ProcessingJob for Phase 3 pipeline
            ProcessingJob.objects.create(
                document=doc,
                job_type=ProcessingJob.JobType.TEXT_EXTRACTION,
                status=JobStatus.PENDING,
                metadata={
                    'original_filename': clean_name,
                    'sha256_hash': sha256_hash,
                    'file_size': len(content),
                    'mime_type': detected_mime,
                },
            )

            # Audit event is INSIDE the transaction — failure rolls back the whole upload
            log_audit(
                request=request,
                event_type=AuditEventType.DOCUMENT_UPLOADED,
                resource_id=doc.id,
                description=f"Uploaded document '{doc.original_filename}' ({doc.file_size_display})",
                metadata={
                    'sha256_hash': sha256_hash,
                    'file_size': len(content),
                    'mime_type': detected_mime,
                },
            )
    except Exception as exc:
        logger.error(
            "Atomic transaction failed for '%s', cleaning up storage: %s",
            storage_key, exc
        )
        try:
            storage.delete(storage_key)
        except Exception as del_exc:
            logger.error("Compensating cleanup failed for '%s': %s", storage_key, del_exc)
        return None, f"Database failure during document registration: {exc}"

    # Trigger Phase 3 pipeline (non-blocking daemon thread)
    try:
        from apps.pipeline.orchestrator import trigger_processing
        trigger_processing(doc.pk)
    except Exception as exc:
        logger.warning('Could not trigger pipeline for doc %d: %s', doc.pk, exc)

    return doc, None


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def document_collection(request):
    """
    GET  /api/documents/ -> List documents (with filters and pagination)
    POST /api/documents/ -> Upload one or multiple files
    """
    if request.method == 'GET':
        # Scope to documents owned by the requesting user
        include_archived = request.query_params.get('archived', 'false').lower() == 'true'
        queryset = Document.objects.filter(
            uploaded_by=request.user,
            is_archived=include_archived,
        )

        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter and status_filter.lower() != 'all':
            queryset = queryset.filter(status=status_filter.lower())

        # Search by title or filename
        search_query = request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(original_filename__icontains=search_query)
            )

        # Ordering
        ordering = request.query_params.get('ordering', '-created_at')
        if ordering in ['created_at', '-created_at', 'title', '-title',
                        'file_size', '-file_size', 'status', '-status']:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-created_at')

        # Pagination
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = DocumentSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)

        serializer = DocumentSerializer(queryset, many=True, context={'request': request})
        return Response({
            'count': queryset.count(),
            'results': serializer.data,
        }, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        # Retrieve uploaded files
        files = []
        if 'files' in request.FILES:
            files = request.FILES.getlist('files')
        elif 'file' in request.FILES:
            files = request.FILES.getlist('file')

        if not files:
            return Response(
                {
                    'error': 'No file was uploaded.',
                    'message': "Please provide a file under the 'file' or 'files' multipart field.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Batch count limit check
        max_batch_count = getattr(settings, 'MAX_BATCH_FILE_COUNT', 10)
        if len(files) > max_batch_count:
            return Response(
                {
                    'error': 'Batch count limit exceeded.',
                    'message': f"Maximum {max_batch_count} files allowed per upload request (received {len(files)}).",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Batch aggregate size check
        max_batch_size = getattr(settings, 'MAX_BATCH_TOTAL_SIZE', 100 * 1024 * 1024)
        aggregate_size = sum(getattr(f, 'size', 0) for f in files)
        if aggregate_size > max_batch_size:
            max_mb = max_batch_size / (1024 * 1024)
            return Response(
                {
                    'error': 'Batch aggregate size limit exceeded.',
                    'message': f"Total batch size exceeds maximum allowed limit of {max_mb:.0f}MB.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        custom_title = request.data.get('title') if len(files) == 1 else None

        created_docs = []
        errors = []

        for f in files:
            doc, err = process_single_upload(f, request, custom_title=custom_title)
            if doc:
                created_docs.append(doc)
            else:
                errors.append({'filename': getattr(f, 'name', 'unnamed'), 'error': err})

        if not created_docs and errors:
            return Response(
                {
                    'error': 'Document upload failed.',
                    'details': errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = {
            'status': 'success',
            'uploaded_count': len(created_docs),
            'results': DocumentSerializer(created_docs, many=True, context={'request': request}).data,
            'documents': DocumentSerializer(created_docs, many=True, context={'request': request}).data,
        }
        if errors:
            response_data['partial_errors'] = errors

        # If single upload, also include single document object for convenience
        if len(files) == 1 and len(created_docs) == 1:
            response_data['document'] = DocumentSerializer(created_docs[0], context={'request': request}).data

        return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def document_detail(request, pk: int):
    """
    GET    /api/documents/<pk>/ -> Document details + jobs
    DELETE /api/documents/<pk>/ -> Archive (soft delete) or hard delete if ?hard=true
    """
    doc = get_object_or_404(Document, pk=pk)

    # Ownership check
    denied = _require_owner(doc, request)
    if denied:
        return denied

    if request.method == 'GET':
        serializer = DocumentDetailSerializer(doc, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == 'DELETE':
        hard_delete = request.query_params.get('hard', 'false').lower() == 'true'

        if hard_delete:
            storage_key = doc.storage_key
            doc_id = doc.id
            filename = doc.original_filename

            if storage_key:
                try:
                    storage = get_storage_service()
                    storage.delete(storage_key)
                except Exception as exc:
                    logger.warning("Could not delete stored file '%s': %s", storage_key, exc)

            try:
                with transaction.atomic():
                    doc.delete()
                    log_audit(
                        request=request,
                        event_type=AuditEventType.DOCUMENT_DELETED,
                        resource_id=doc_id,
                        description=f"Permanently deleted document '{filename}'",
                    )
            except Exception as exc:
                logger.error("Atomic delete+audit failed for doc %s: %s", doc_id, exc)
                return Response(
                    {'error': 'Delete operation failed due to an internal error.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            try:
                with transaction.atomic():
                    doc.is_archived = True
                    doc.save(update_fields=['is_archived', 'updated_at'])
                    log_audit(
                        request=request,
                        event_type=AuditEventType.DOCUMENT_DELETED,
                        resource_id=doc.id,
                        description=f"Archived document '{doc.original_filename}'",
                    )
            except Exception as exc:
                logger.error("Atomic archive+audit failed for doc %s: %s", pk, exc)
                return Response(
                    {'error': 'Archive operation failed due to an internal error.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            return Response({
                'status': 'archived',
                'id': doc.id,
                'message': f"Document '{doc.original_filename}' has been archived.",
            }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_status(request, pk: int):
    """
    GET /api/documents/<pk>/status/ -> Lightweight status polling endpoint
    """
    doc = get_object_or_404(Document, pk=pk)

    denied = _require_owner(doc, request)
    if denied:
        return denied

    return Response({
        'id': doc.id,
        'title': doc.title,
        'status': doc.status,
        'status_display': doc.get_status_display(),
        'error_message': doc.error_message,
        'is_archived': doc.is_archived,
        'updated_at': doc.updated_at,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_download(request, pk: int):
    """
    GET /api/documents/<pk>/download/ -> Download original unmodified file
    """
    doc = get_object_or_404(Document, pk=pk)

    denied = _require_owner(doc, request)
    if denied:
        return denied

    if not doc.storage_key:
        raise Http404("Document file reference is missing.")

    storage = get_storage_service()
    if not storage.exists(doc.storage_key):
        raise Http404(f"Stored file for document '{doc.original_filename}' not found in storage backend.")

    try:
        content = storage.open(doc.storage_key)
    except Exception as exc:
        logger.error("Error opening stored document '%s': %s", doc.storage_key, exc)
        return Response(
            {'error': 'Could not read document from storage backend.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    response = HttpResponse(content, content_type=doc.mime_type or 'application/octet-stream')
    safe_filename = sanitize_filename(doc.original_filename) or f'document_{doc.id}{doc.file_extension}'
    response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
    response['Content-Length'] = len(content)
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def document_retry(request, pk: int):
    """
    POST /api/documents/<pk>/retry/ -> Reset status to queued/pending for processing retry.
    Only permitted for documents in failed or needs_review status.
    Prevents duplicate active jobs.
    """
    doc = get_object_or_404(Document, pk=pk)

    denied = _require_owner(doc, request)
    if denied:
        return denied

    allowed_retry_statuses = [DocumentStatus.FAILED, DocumentStatus.NEEDS_REVIEW]
    if doc.status not in allowed_retry_statuses:
        return Response(
            {
                'error': f"Cannot retry document in '{doc.status}' status.",
                'message': f"Only documents with status in {allowed_retry_statuses} can be retried.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check for existing active/pending jobs
    active_jobs = doc.jobs.filter(status__in=[JobStatus.PENDING, JobStatus.RUNNING])
    if active_jobs.exists():
        return Response(
            {
                'error': 'Duplicate retry rejected.',
                'message': 'Document already has an active or pending processing job in progress.',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            doc.status = DocumentStatus.QUEUED
            doc.error_message = ''
            doc.save(update_fields=['status', 'error_message', 'updated_at'])

            ProcessingJob.objects.create(
                document=doc,
                job_type=ProcessingJob.JobType.TEXT_EXTRACTION,
                status=JobStatus.PENDING,
                metadata={'retry': True, 'requested_at': dj_timezone.now().isoformat()},
            )

            log_audit(
                request=request,
                event_type=AuditEventType.DOCUMENT_REVIEWED,
                resource_id=doc.id,
                description=f"Queued document '{doc.original_filename}' for processing retry.",
            )
    except Exception as exc:
        logger.error("Atomic retry+audit failed for doc %s: %s", pk, exc)
        return Response(
            {'error': 'Retry operation failed due to an internal error.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        DocumentSerializer(doc, context={'request': request}).data,
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def document_archive(request, pk: int):
    """
    POST /api/documents/<pk>/archive/ -> Archive / soft-delete document
    """
    doc = get_object_or_404(Document, pk=pk)

    denied = _require_owner(doc, request)
    if denied:
        return denied

    try:
        with transaction.atomic():
            doc.is_archived = True
            doc.save(update_fields=['is_archived', 'updated_at'])

            log_audit(
                request=request,
                event_type=AuditEventType.DOCUMENT_DELETED,
                resource_id=doc.id,
                description=f"Archived document '{doc.original_filename}'",
            )
    except Exception as exc:
        logger.error("Atomic archive+audit failed for doc %s: %s", pk, exc)
        return Response(
            {'error': 'Archive operation failed due to an internal error.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response({
        'status': 'archived',
        'id': doc.id,
        'message': f"Document '{doc.original_filename}' archived successfully.",
    }, status=status.HTTP_200_OK)
