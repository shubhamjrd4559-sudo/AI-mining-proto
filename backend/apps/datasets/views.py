"""
apps.datasets — Views (Phase 6 Data Explorer)

Provides:
  - Backward-compatible Phase 1 stub: dataset_list_stub (name='api-datasets')
  - Owner-scoped dataset listing: dataset_list
  - Dynamic column & schema discovery: dataset_schema
  - Server-side search, filtering, sorting & pagination: dataset_records
  - Record detail with full provenance & validation findings: dataset_record_detail
  - Filtered CSV Export (P2): dataset_export_csv
"""

import csv
import io
import math
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.datasets.models import StructuredDataset, StructuredRecord
from apps.pipeline.models import ExtractionProvenance, ValidationResult
from apps.maintainer.models import MaintainerSuggestion
from apps.analytics.query_engine import (
    AnalyticsQueryEngine,
    parse_numeric,
    parse_financial_year,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Phase 1 Backward Compatibility Stub
# ─────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def dataset_list_stub(request):
    """GET /api/datasets/ — Phase 1 stub preserved for test compatibility."""
    return Response(
        {
            'status': 'not_implemented',
            'endpoint': 'datasets',
            'phase': 2,
            'message': 'Dataset listing will be implemented in Phase 2.',
        },
        status=status.HTTP_200_OK,
    )


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _get_owned_dataset(dataset_id: Any, request) -> Tuple[Optional[StructuredDataset], Optional[Response]]:
    """Verify dataset exists and belongs to the requesting user."""
    try:
        dataset = StructuredDataset.objects.select_related('source_document').get(pk=dataset_id)
    except (StructuredDataset.DoesNotExist, ValueError):
        return None, Response({'error': 'Dataset not found.'}, status=status.HTTP_404_NOT_FOUND)

    doc = dataset.source_document
    if not doc or not doc.uploaded_by or doc.uploaded_by != request.user:
        return None, Response(
            {'error': 'You do not have permission to access this dataset.'},
            status=status.HTTP_403_FORBIDDEN
        )
    return dataset, None


# ─────────────────────────────────────────────
# Data Explorer Endpoints
# ─────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dataset_list(request):
    """
    GET /api/datasets/list/
    Lists all structured datasets owned by the requesting user.
    """
    datasets = (
        StructuredDataset.objects.filter(source_document__uploaded_by=request.user)
        .select_related('source_document')
        .order_by('-created_at')
    )

    data = []
    for ds in datasets:
        doc = ds.source_document
        schema = ds.schema_json or {}
        cols = schema.get('columns', [])
        data.append({
            'id': ds.id,
            'name': ds.name,
            'description': ds.description,
            'record_count': ds.record_count,
            'columns': cols,
            'created_at': ds.created_at.isoformat(),
            'source_document': {
                'id': doc.id if doc else None,
                'title': doc.title if doc else '',
                'original_filename': doc.original_filename if doc else '',
            } if doc else None,
        })

    return Response({'datasets': data}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dataset_schema(request, dataset_id):
    """
    GET /api/datasets/<id>/schema/
    Dynamic column discovery, available sheets, and filter options.
    """
    dataset, err = _get_owned_dataset(dataset_id, request)
    if err:
        return err

    engine = AnalyticsQueryEngine(dataset)
    fields = engine.get_available_fields()
    filter_options = engine.get_distinct_filter_options()

    schema_json = dataset.schema_json or {}
    columns_list = []
    seen = set()

    for col_name in schema_json.get('columns', []):
        col_clean = str(col_name).strip()
        if col_clean and col_clean not in seen:
            seen.add(col_clean)
            ftype = fields.get(col_clean, 'categorical')
            columns_list.append({
                'name': col_clean,
                'type': ftype,
                'filterable': col_clean in filter_options,
            })

    # Also include any fields found in records not yet in schema_json
    for f, ftype in fields.items():
        if f not in seen:
            seen.add(f)
            columns_list.append({
                'name': f,
                'type': ftype,
                'filterable': f in filter_options,
            })

    doc = dataset.source_document
    return Response({
        'dataset_id': dataset.id,
        'dataset_name': dataset.name,
        'source_document': {
            'id': doc.id if doc else None,
            'title': doc.title if doc else '',
            'original_filename': doc.original_filename if doc else '',
        } if doc else None,
        'columns': columns_list,
        'sheets': filter_options.get('sheet', []),
        'filters': filter_options,
        'total_records': dataset.record_count,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dataset_records(request, dataset_id):
    """
    GET /api/datasets/<id>/records/
    Server-side pagination, global search, safe field filtering, and sorting.
    """
    dataset, err = _get_owned_dataset(dataset_id, request)
    if err:
        return err

    engine = AnalyticsQueryEngine(dataset)
    fields = engine.get_available_fields()

    # Pagination params
    try:
        page = max(1, int(request.query_params.get('page', 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        page_size = min(max(1, int(request.query_params.get('page_size', 25))), 100)
    except (ValueError, TypeError):
        page_size = 25

    # Filters
    search_q = request.query_params.get('search')
    sheet = request.query_params.get('sheet')
    data_quality = request.query_params.get('data_quality', 'all').lower()

    # Dynamic field filters
    filters = {}
    for k in request.query_params.keys():
        if k in ('page', 'page_size', 'search', 'sheet', 'sort_by', 'sort_dir', 'data_quality'):
            continue
        filters[k] = request.query_params.get(k)

    # Filter records
    exclude_errors = (data_quality == 'valid_only')
    matched_records = engine.filter_records(
        filters=filters,
        sheet=sheet,
        exclude_errors=exclude_errors,
        search_query=search_q,
    )

    error_ids, warning_ids = engine._get_quality_record_ids()

    # Filter further if data_quality specifies warnings or errors only
    if data_quality == 'with_warnings':
        matched_records = [r for r in matched_records if r.id in warning_ids]
    elif data_quality == 'with_errors':
        matched_records = [r for r in matched_records if r.id in error_ids]

    # Sorting
    sort_by = request.query_params.get('sort_by')
    sort_dir = request.query_params.get('sort_dir', 'asc').lower()
    reverse = (sort_dir == 'desc')

    if sort_by and sort_by in fields:
        is_num = (fields[sort_by] == 'numeric')
        is_fy = (sort_by == 'financial_year')

        def sort_key(rec):
            val = rec.data_json.get(sort_by)
            if val is None:
                return (1, 0)
            if is_num:
                n = parse_numeric(val)
                return (0, n if n is not None else float('-inf'))
            if is_fy:
                p = parse_financial_year(val)
                return (0, p if p is not None else (0, 0))
            return (0, str(val).lower())

        matched_records.sort(key=sort_key, reverse=reverse)
    else:
        # Default stable sorting by row_index
        matched_records.sort(key=lambda r: r.row_index)

    total_records = len(matched_records)
    total_pages = max(1, math.ceil(total_records / page_size)) if total_records > 0 else 1

    # Slice page
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_records = matched_records[start_idx:end_idx]

    # Pre-fetch provenance and maintainer indicators for page records
    prov_cache = engine._load_provenance()

    maintained_record_ids = set(
        MaintainerSuggestion.objects.filter(
            dataset=dataset,
            record__in=page_records,
            status='applied'
        ).values_list('record_id', flat=True)
    )

    rows = []
    for r in page_records:
        r_provs = prov_cache.get(r.id, [])
        first_p = r_provs[0] if r_provs else None
        prov_summary = {
            'sheet_name': first_p.sheet_name if first_p else '',
            'page_number': first_p.page_number if first_p else None,
            'source_reference': first_p.source_reference if first_p else '',
            'extraction_method': first_p.extraction_method if first_p else '',
        } if first_p else None

        # Clean display data (hide internal metadata keys from main view)
        display_data = {
            k: v for k, v in r.data_json.items()
            if not k.endswith('_original') and not k.endswith('_original_before_apply')
        }

        rows.append({
            'record_id': r.id,
            'row_index': r.row_index,
            'data': display_data,
            'is_valid': r.is_valid and r.id not in error_ids,
            'has_warnings': r.id in warning_ids,
            'has_errors': r.id in error_ids or not r.is_valid,
            'is_maintained': r.id in maintained_record_ids,
            'provenance': prov_summary,
        })

    # Available columns for table rendering
    schema_cols = dataset.schema_json.get('columns', [])
    if not schema_cols:
        schema_cols = list(fields.keys())

    return Response({
        'dataset': {
            'id': dataset.id,
            'name': dataset.name,
        },
        'sheet': sheet or 'all',
        'columns': schema_cols,
        'page': page,
        'page_size': page_size,
        'total_records': total_records,
        'total_pages': total_pages,
        'rows': rows,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dataset_record_detail(request, dataset_id, record_id):
    """
    GET /api/datasets/<id>/records/<record_id>/
    Deep record detail: all normalized vs original fields, provenance, and validation findings.
    """
    dataset, err = _get_owned_dataset(dataset_id, request)
    if err:
        return err

    try:
        record = StructuredRecord.objects.get(pk=record_id, dataset=dataset)
    except StructuredRecord.DoesNotExist:
        return Response({'error': 'Record not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Build fields breakdown
    fields_breakdown = []
    data = record.data_json or {}

    seen_fields = set()
    for k, v in data.items():
        if k.endswith('_original') or k.endswith('_original_before_apply'):
            continue
        seen_fields.add(k)
        orig_val = data.get(f'{k}_original', v)
        before_apply = data.get(f'{k}_original_before_apply')

        fields_breakdown.append({
            'field': k,
            'current_value': str(v) if v is not None else '',
            'original_value': str(orig_val) if orig_val is not None else '',
            'was_maintained': before_apply is not None,
            'before_apply_value': str(before_apply) if before_apply is not None else None,
        })

    # Extraction Provenance
    provs = ExtractionProvenance.objects.filter(record=record).select_related('document')
    prov_list = []
    for p in provs:
        prov_list.append({
            'id': p.id,
            'document_id': p.document_id,
            'document_title': p.document.title if p.document else '',
            'sheet_name': p.sheet_name,
            'page_number': p.page_number,
            'section_heading': p.section_heading,
            'table_reference': p.table_reference,
            'row_index': p.row_index,
            'col_index': p.col_index,
            'extraction_method': p.extraction_method,
            'ocr_used': p.ocr_used,
            'confidence': p.confidence,
            'source_reference': p.source_reference,
        })

    # Validation findings
    doc = dataset.source_document
    validation_list = []
    if doc:
        v_results = ValidationResult.objects.filter(document=doc, record=record)
        for v in v_results:
            validation_list.append({
                'id': v.id,
                'field_name': v.field_name,
                'issue_type': v.issue_type,
                'severity': v.severity,
                'original_value': v.original_value,
                'suggested_value': v.suggested_value,
                'explanation': v.explanation,
                'confidence': v.confidence,
                'status': v.status,
            })

    # Maintainer history
    suggestions = MaintainerSuggestion.objects.filter(record=record).order_by('-created_at')
    suggestion_list = []
    for s in suggestions:
        suggestion_list.append({
            'id': s.id,
            'field_name': s.field_name,
            'original_value': s.original_value,
            'suggested_value': s.suggested_value,
            'applied_value': s.applied_value,
            'status': s.status,
            'issue_type': s.issue_type,
            'reason': s.reason,
            'confidence': s.confidence,
        })

    return Response({
        'record_id': record.id,
        'row_index': record.row_index,
        'dataset_id': dataset.id,
        'dataset_name': dataset.name,
        'is_valid': record.is_valid,
        'fields': fields_breakdown,
        'provenance': prov_list,
        'validation_findings': validation_list,
        'maintainer_suggestions': suggestion_list,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dataset_export_csv(request, dataset_id):
    """
    GET /api/datasets/<id>/export/csv/
    P2: Export filtered Data Explorer rows as clean CSV.
    """
    dataset, err = _get_owned_dataset(dataset_id, request)
    if err:
        return err

    engine = AnalyticsQueryEngine(dataset)
    fields = engine.get_available_fields()

    # Dynamic filters identically matching dataset_records
    search_q = request.query_params.get('search')
    sheet = request.query_params.get('sheet')
    data_quality = request.query_params.get('data_quality', 'all').lower()

    filters = {}
    for k in request.query_params.keys():
        if k in ('search', 'sheet', 'sort_by', 'sort_dir', 'data_quality'):
            continue
        filters[k] = request.query_params.get(k)

    exclude_errors = (data_quality == 'valid_only')
    matched_records = engine.filter_records(
        filters=filters,
        sheet=sheet,
        exclude_errors=exclude_errors,
        search_query=search_q,
    )

    error_ids, warning_ids = engine._get_quality_record_ids()
    if data_quality == 'with_warnings':
        matched_records = [r for r in matched_records if r.id in warning_ids]
    elif data_quality == 'with_errors':
        matched_records = [r for r in matched_records if r.id in error_ids]

    # Columns
    cols = dataset.schema_json.get('columns', [])
    if not cols:
        cols = list(fields.keys())

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(cols)

    for r in matched_records:
        row = [str(r.data_json.get(c, '')) for c in cols]
        writer.writerow(row)

    csv_data = output.getvalue()
    safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in dataset.name)
    response = HttpResponse(csv_data, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{safe_name}_export.csv"'
    return response
