"""
apps.analytics — Views (Phase 6)

All endpoints enforce:
  - TokenAuthentication / SessionAuthentication (IsAuthenticated)
  - Strict owner-scoping (source_document.uploaded_by == request.user)
  - Safe field validation (no arbitrary injection)
"""

import json
import logging
from collections import defaultdict
from typing import Optional, Tuple, Any
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.datasets.models import StructuredDataset, StructuredRecord
from apps.pipeline.models import ExtractionProvenance, ValidationResult

from .query_engine import AnalyticsQueryEngine

logger = logging.getLogger(__name__)


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


def _extract_filters(params) -> dict:
    """Extract filter parameters from query params or request body."""
    raw_filters = {}
    if hasattr(params, 'getlist'):
        for k in params.keys():
            if k in ('dataset_id', 'metric', 'group_by', 'time_field', 'aggregation', 'sheet', 'limit', 'sort_by', 'sort_dir', 'page', 'page_size', 'search'):
                continue
            raw_filters[k] = params.get(k)
    elif isinstance(params, dict):
        if 'filters' in params and isinstance(params['filters'], dict):
            raw_filters = params['filters']
        else:
            for k, v in params.items():
                if k in ('dataset_id', 'metric', 'group_by', 'time_field', 'aggregation', 'sheet', 'limit', 'sort_by', 'sort_dir', 'page', 'page_size', 'search'):
                    continue
                raw_filters[k] = v
    return raw_filters


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dataset_list(request):
    """
    GET /api/analytics/datasets/
    List all structured datasets owned by the authenticated user.
    """
    datasets = (
        StructuredDataset.objects.filter(source_document__uploaded_by=request.user)
        .select_related('source_document')
        .order_by('-created_at')
    )

    data = []
    for ds in datasets:
        schema = ds.schema_json or {}
        cols = schema.get('columns', [])
        cmap = schema.get('column_map', {})
        detected_concepts = [v.get('concept') for v in cmap.values() if v.get('concept')]

        doc = ds.source_document
        data.append({
            'id': ds.id,
            'name': ds.name,
            'description': ds.description,
            'record_count': ds.record_count,
            'created_at': ds.created_at.isoformat(),
            'source_document': {
                'id': doc.id if doc else None,
                'title': doc.title if doc else '',
                'original_filename': doc.original_filename if doc else '',
            } if doc else None,
            'columns': cols,
            'detected_concepts': detected_concepts,
            'has_production': 'production' in detected_concepts or 'production' in cols,
            'has_target': 'target' in detected_concepts or 'target' in cols,
            'has_dispatch': 'dispatch' in detected_concepts or 'dispatch' in cols,
            'has_financial_year': 'financial_year' in detected_concepts or 'financial_year' in cols,
        })

    return Response({'datasets': data}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kpi_view(request):
    """
    GET /api/analytics/kpi/?dataset_id=<id>&...
    Calculates dynamic KPIs for the dataset.
    """
    dataset_id = request.query_params.get('dataset_id')
    if not dataset_id:
        return Response({'error': 'dataset_id parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    dataset, err = _get_owned_dataset(dataset_id, request)
    if err:
        return err

    sheet = request.query_params.get('sheet')
    filters = _extract_filters(request.query_params)

    engine = AnalyticsQueryEngine(dataset)
    kpis = engine.calculate_kpis(filters=filters, sheet=sheet)
    filter_options = engine.get_distinct_filter_options()

    return Response({
        'dataset_id': dataset.id,
        'dataset_name': dataset.name,
        'kpis': kpis,
        'available_filters': filter_options,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trends_view(request):
    """
    GET /api/analytics/trends/?dataset_id=<id>&metric=production&time_field=financial_year&...
    Calculates time-series trend data.
    """
    dataset_id = request.query_params.get('dataset_id')
    if not dataset_id:
        return Response({'error': 'dataset_id parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    dataset, err = _get_owned_dataset(dataset_id, request)
    if err:
        return err

    metric = request.query_params.get('metric', 'production').strip()
    time_field = request.query_params.get('time_field', 'financial_year').strip()
    sheet = request.query_params.get('sheet')
    filters = _extract_filters(request.query_params)

    engine = AnalyticsQueryEngine(dataset)
    fields = engine.get_available_fields()

    if metric not in fields and metric not in ('count',):
        return Response(
            {'error': f"Metric '{metric}' is not available in dataset schema."},
            status=status.HTTP_400_BAD_REQUEST
        )

    trends = engine.calculate_trends(
        filters=filters,
        sheet=sheet,
        metric=metric,
        time_field=time_field,
    )

    return Response({
        'dataset_id': dataset.id,
        'dataset_name': dataset.name,
        **trends,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def breakdown_view(request):
    """
    GET /api/analytics/breakdown/?dataset_id=<id>&group_by=subsidiary&metric=production&...
    Calculates grouped comparisons.
    """
    dataset_id = request.query_params.get('dataset_id')
    if not dataset_id:
        return Response({'error': 'dataset_id parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    dataset, err = _get_owned_dataset(dataset_id, request)
    if err:
        return err

    group_by = request.query_params.get('group_by', 'subsidiary').strip()
    metric = request.query_params.get('metric', 'production').strip()
    sheet = request.query_params.get('sheet')
    limit_raw = request.query_params.get('limit', 20)
    try:
        limit = min(max(1, int(limit_raw)), 100)
    except (ValueError, TypeError):
        limit = 20

    filters = _extract_filters(request.query_params)

    engine = AnalyticsQueryEngine(dataset)
    fields = engine.get_available_fields()

    if group_by not in fields:
        return Response(
            {'error': f"Group dimension '{group_by}' is not present in dataset schema."},
            status=status.HTTP_400_BAD_REQUEST
        )

    breakdown = engine.calculate_breakdown(
        group_by=group_by,
        metric=metric,
        filters=filters,
        sheet=sheet,
        limit=limit,
    )

    return Response({
        'dataset_id': dataset.id,
        'dataset_name': dataset.name,
        **breakdown,
    }, status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def query_view(request):
    """
    GET / POST /api/analytics/query/
    General aggregation query endpoint.
    """
    data = request.data if request.method == 'POST' else request.query_params

    dataset_id = data.get('dataset_id')
    if not dataset_id:
        return Response({'error': 'dataset_id parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    dataset, err = _get_owned_dataset(dataset_id, request)
    if err:
        return err

    aggregation = data.get('aggregation', 'sum')
    metric = data.get('metric', 'production')
    group_by = data.get('group_by')
    sheet = data.get('sheet')
    sort_by = data.get('sort_by', 'value')
    sort_dir = data.get('sort_dir', 'desc')
    exclude_errors = str(data.get('exclude_errors', 'true')).lower() in ('true', '1')

    try:
        limit = min(max(1, int(data.get('limit', 50))), 200)
    except (ValueError, TypeError):
        limit = 50

    filters = _extract_filters(data)

    engine = AnalyticsQueryEngine(dataset)
    fields = engine.get_available_fields()

    # Validate metric and group_by
    if metric != 'count' and metric not in fields:
        return Response(
            {'error': f"Metric '{metric}' is not a recognized column in dataset."},
            status=status.HTTP_400_BAD_REQUEST
        )
    if group_by and group_by not in fields:
        return Response(
            {'error': f"group_by '{group_by}' is not a recognized column in dataset."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        res = engine.execute_query(
            aggregation=aggregation,
            metric=metric,
            group_by=group_by,
            filters=filters,
            sheet=sheet,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            exclude_errors=exclude_errors,
        )
        return Response({
            'dataset_id': dataset.id,
            'dataset_name': dataset.name,
            **res,
        }, status=status.HTTP_200_OK)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def drilldown_view(request):
    """
    GET /api/analytics/drilldown/?dataset_id=<id>&record_ids=1,2,3...
    Retrieve full record details and extraction provenance for contributing data points.
    """
    dataset_id = request.query_params.get('dataset_id')
    if not dataset_id:
        return Response({'error': 'dataset_id parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    dataset, err = _get_owned_dataset(dataset_id, request)
    if err:
        return err

    ids_str = request.query_params.get('record_ids', '')
    if not ids_str:
        return Response({'error': 'record_ids parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        id_list = [int(x.strip()) for x in ids_str.split(',') if x.strip().isdigit()][:100]
    except Exception:
        return Response({'error': 'Invalid record_ids format.'}, status=status.HTTP_400_BAD_REQUEST)

    records = StructuredRecord.objects.filter(dataset=dataset, id__in=id_list).order_by('row_index')
    provs = ExtractionProvenance.objects.filter(record__in=records).select_related('document')
    prov_map = defaultdict(list)
    for p in provs:
        prov_map[p.record_id].append({
            'id': p.id,
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
            'document_title': p.document.title if p.document else '',
        })

    results = []
    for r in records:
        results.append({
            'record_id': r.id,
            'row_index': r.row_index,
            'data': r.data_json,
            'is_valid': r.is_valid,
            'validation_errors': r.validation_errors,
            'provenance': prov_map.get(r.id, []),
        })

    return Response({
        'dataset_id': dataset.id,
        'dataset_name': dataset.name,
        'records': results,
        'total_count': len(results),
    }, status=status.HTTP_200_OK)
