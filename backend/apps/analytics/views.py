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

from .query_engine import (
    AnalyticsQueryEngine, NUMERIC_CONCEPT_NAMES, parse_numeric,
    record_metric_value, record_financial_year, format_financial_year, dataset_metric_total,
)

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
    if doc.is_archived:
        return None, Response(
            {'error': 'Dataset belongs to an archived document.'},
            status=status.HTTP_404_NOT_FOUND
        )
    return dataset, None


class ScopedAnalyticsEngine(AnalyticsQueryEngine):
    """
    AnalyticsQueryEngine supporting partition filtering between:
      - Historical Baseline Reference data (is_reference=True)
      - User Uploaded data (is_reference=False)
      - Single dataset or full consolidated data (is_reference=None)
    Also supports fallback extraction of Metric/Value rows (e.g. Total Production, Total Target, Total Dispatch).
    """

    def __init__(self, dataset: Optional[StructuredDataset] = None, user=None, is_reference: Optional[bool] = None):
        super().__init__(dataset=dataset, user=user)
        self.is_reference = is_reference

    def get_available_fields(self) -> dict:
        if self._available_fields is not None:
            return self._available_fields

        fields = {}
        if self.dataset is not None:
            schema = self.dataset.schema_json or {}
            cols = schema.get('columns', [])
            cmap = schema.get('column_map', {})
            for c in cols:
                concept = cmap.get(c, {}).get('concept') or c
                fields[concept] = 'numeric' if concept in NUMERIC_CONCEPT_NAMES else 'categorical'
        elif self.user is not None:
            qs = StructuredDataset.objects.filter(
                source_document__uploaded_by=self.user,
                source_document__is_archived=False
            )
            if self.is_reference is not None:
                qs = qs.filter(source_document__is_reference=self.is_reference)
            for ds in qs:
                schema = ds.schema_json or {}
                cols = schema.get('columns', [])
                cmap = schema.get('column_map', {})
                for c in cols:
                    concept = cmap.get(c, {}).get('concept') or c
                    if concept not in fields:
                        fields[concept] = 'numeric' if concept in NUMERIC_CONCEPT_NAMES else 'categorical'

        records = self._load_records()[:100]
        for r in records:
            for k, v in r.data_json.items():
                if k.endswith('_original') or k.endswith('_original_before_apply'):
                    continue
                if k not in fields:
                    if k in NUMERIC_CONCEPT_NAMES:
                        fields[k] = 'numeric'
                    elif parse_numeric(v) is not None:
                        fields[k] = 'numeric'
                    else:
                        fields[k] = 'categorical'

        self._available_fields = fields
        return fields

    def _load_records(self) -> list:
        if self._records_cache is None:
            if self.dataset is not None:
                qs = StructuredRecord.objects.filter(dataset=self.dataset).select_related('dataset', 'dataset__source_document')
            elif self.user is not None:
                qs = StructuredRecord.objects.filter(
                    dataset__source_document__uploaded_by=self.user,
                    dataset__source_document__is_archived=False
                )
                if self.is_reference is not None:
                    qs = qs.filter(dataset__source_document__is_reference=self.is_reference)
                qs = qs.select_related('dataset', 'dataset__source_document')
            else:
                qs = StructuredRecord.objects.none()
            self._records_cache = list(qs.order_by('row_index', 'id'))
        return self._records_cache

    def _load_provenance(self) -> dict:
        if self._provenance_cache is None:
            if self.dataset is not None:
                provs = ExtractionProvenance.objects.filter(record__dataset=self.dataset)
            elif self.user is not None:
                provs = ExtractionProvenance.objects.filter(
                    record__dataset__source_document__uploaded_by=self.user,
                    record__dataset__source_document__is_archived=False
                )
                if self.is_reference is not None:
                    provs = provs.filter(record__dataset__source_document__is_reference=self.is_reference)
            else:
                provs = []
            cache = defaultdict(list)
            for p in provs:
                cache[p.record_id].append(p)
            self._provenance_cache = cache
        return self._provenance_cache

    def calculate_kpis(self, filters: Optional[dict] = None, sheet: Optional[str] = None) -> dict:
        kpis = super().calculate_kpis(filters=filters, sheet=sheet)
        records = self.filter_records(filters=filters, sheet=sheet, exclude_errors=True)

        needs_prod = kpis.get('total_production') is None
        needs_target = kpis.get('total_target') is None
        needs_dispatch = kpis.get('total_dispatch') is None

        if needs_prod or needs_target or needs_dispatch:
            for r in records:
                m = str(r.data_json.get('Metric') or r.data_json.get('metric') or r.data_json.get('Field') or r.data_json.get('field') or '').strip().lower()
                val = parse_numeric(r.data_json.get('Value') or r.data_json.get('value'))
                unit = r.data_json.get('unit') or r.data_json.get('Unit') or 'MT'
                if val is not None:
                    if needs_prod and 'production' in m and 'target' not in m:
                        kpis['total_production'] = (kpis.get('total_production') or 0.0) + val
                        kpis['production_unit'] = unit
                    elif needs_target and 'target' in m:
                        kpis['total_target'] = (kpis.get('total_target') or 0.0) + val
                        kpis['target_unit'] = unit
                    elif needs_dispatch and 'dispatch' in m:
                        kpis['total_dispatch'] = (kpis.get('total_dispatch') or 0.0) + val
                        kpis['dispatch_unit'] = unit

        if kpis.get('total_production') is not None and kpis.get('total_target') and kpis['total_target'] > 0:
            kpis['achievement_pct'] = round((kpis['total_production'] / kpis['total_target']) * 100, 1)

        return kpis

    def calculate_trends(self, filters=None, sheet=None, metric='production', time_field='financial_year'):
        """Support canonical rows and extracted Metric/Value report rows."""
        # 1. First try record-level trend calculation (handles datasets with multi-period rows)
        base_trends = super().calculate_trends(filters=filters, sheet=sheet, metric=metric, time_field=time_field)
        if base_trends.get('series'):
            return base_trends

        if time_field != 'financial_year':
            return base_trends

        # 2. Fallback: single-period datasets or datasets with Metric/Value rows
        periods = defaultdict(lambda: {'value': 0.0, 'count': 0, 'record_ids': [], 'target': 0.0, 'dispatch': 0.0})
        by_dataset = defaultdict(list)
        for record in self.filter_records(filters=filters, sheet=sheet, exclude_errors=True):
            by_dataset[record.dataset_id].append(record)
        for dataset_records in by_dataset.values():
            fy = None
            for r in dataset_records:
                fy = record_financial_year(r)
                if fy:
                    break
            value = dataset_metric_total(dataset_records, metric)
            if not fy or value is None:
                continue
            item = periods[fy]
            item['value'] += value
            item['count'] += len(dataset_records)
            item['record_ids'].extend(r.id for r in dataset_records)
            target = dataset_metric_total(dataset_records, 'target')
            dispatch = dataset_metric_total(dataset_records, 'dispatch')
            if target is not None:
                item['target'] += target
            if dispatch is not None:
                item['dispatch'] += dispatch
        series = []
        for fy in sorted(periods):
            item = periods[fy]
            row = {'period': format_financial_year(fy), 'value': round(item['value'], 2), 'count': item['count'], 'record_ids': item['record_ids'][:100]}
            if item['target']:
                row['target'] = round(item['target'], 2)
                row['achievement_pct'] = round(item['value'] / item['target'] * 100, 1)
            if item['dispatch']:
                row['dispatch'] = round(item['dispatch'], 2)
            series.append(row)
        for index in range(1, len(series)):
            previous = series[index - 1]['value']
            if previous > 0:
                series[index]['growth_pct'] = round((series[index]['value'] - previous) / previous * 100, 1)
        return {'metric': metric, 'time_field': time_field, 'series': series, 'total_periods': len(series)}


def _resolve_engine_and_dataset(dataset_id: Any, request):
    """
    Resolves dataset_id parameter into (engine, dataset_name, resp_dataset_id, error_response).
    Supports:
      - 'baseline' / 'reference': Historical reference datasets (source_document__is_reference=True)
      - 'uploaded' / 'user_uploaded': User-uploaded datasets (source_document__is_reference=False)
      - 'all': All consolidated datasets owned by the user
      - <int>: A specific dataset owned by the user
    """
    dataset_id_str = str(dataset_id).strip().lower()
    if dataset_id_str in ('baseline', 'reference'):
        engine = ScopedAnalyticsEngine(user=request.user, is_reference=True)
        return engine, 'Protected Historical Reference Data', 'baseline', None
    elif dataset_id_str in ('uploaded', 'user_uploaded', 'user'):
        engine = ScopedAnalyticsEngine(user=request.user, is_reference=False)
        return engine, 'User Uploaded Data', 'uploaded', None
    elif dataset_id_str == 'all':
        engine = ScopedAnalyticsEngine(user=request.user, is_reference=None)
        return engine, 'All Uploaded Documents (Consolidated)', 'all', None
    else:
        dataset, err = _get_owned_dataset(dataset_id, request)
        if err:
            return None, None, None, err
        engine = ScopedAnalyticsEngine(dataset=dataset, user=request.user)
        return engine, dataset.name, dataset.id, None


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
        StructuredDataset.objects.filter(
            source_document__uploaded_by=request.user,
            source_document__is_archived=False,
        )
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
        is_ref = bool(doc.is_reference) if doc else False
        data.append({
            'id': ds.id,
            'name': ds.name,
            'description': ds.description,
            'record_count': ds.record_count,
            'created_at': ds.created_at.isoformat(),
            'is_reference': is_ref,
            'source_document': {
                'id': doc.id if doc else None,
                'title': doc.title if doc else '',
                'original_filename': doc.original_filename if doc else '',
                'is_reference': is_ref,
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
    Calculates dynamic KPIs for the dataset, baseline ('baseline'), user uploads ('uploaded'), or cross-dataset records ('all').
    """
    dataset_id = request.query_params.get('dataset_id')
    if not dataset_id:
        return Response({'error': 'dataset_id parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    engine, dataset_name, resp_dataset_id, err = _resolve_engine_and_dataset(dataset_id, request)
    if err:
        return err

    sheet = request.query_params.get('sheet')
    filters = _extract_filters(request.query_params)

    kpis = engine.calculate_kpis(filters=filters, sheet=sheet)
    filter_options = engine.get_distinct_filter_options()

    return Response({
        'dataset_id': resp_dataset_id,
        'dataset_name': dataset_name,
        'kpis': kpis,
        'available_filters': filter_options,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trends_view(request):
    """
    GET /api/analytics/trends/?dataset_id=<id>&metric=production&time_field=financial_year&...
    Calculates time-series trend data across single dataset or all user datasets when dataset_id='all'.
    """
    dataset_id = request.query_params.get('dataset_id')
    if not dataset_id:
        return Response({'error': 'dataset_id parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    engine, dataset_name, resp_dataset_id, err = _resolve_engine_and_dataset(dataset_id, request)
    if err:
        return err

    metric = request.query_params.get('metric', 'production').strip()
    time_field = request.query_params.get('time_field', 'financial_year').strip()
    sheet = request.query_params.get('sheet')
    filters = _extract_filters(request.query_params)

    fields = engine.get_available_fields()

    if metric not in fields and metric not in ('count',):
        is_multi = resp_dataset_id in ('all', 'baseline', 'uploaded')
        if is_multi:
            return Response({
                'dataset_id': resp_dataset_id,
                'dataset_name': dataset_name,
                'series': [],
                'metric': metric,
                'time_field': time_field,
                'has_sufficient_history': False,
                'history_status': 'no_metric',
                'history_message': f"Metric '{metric}' is not present in dataset schemas.",
                'overall_growth_pct': None,
                'growth_periods': None,
            }, status=status.HTTP_200_OK)
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

    series = trends.get('series', [])
    valid_periods = [
        p for p in series
        if p.get('period') and (p.get('value') is not None or p.get('cil') is not None)
    ]
    has_sufficient_history = len(valid_periods) >= 2
    overall_growth_pct = None
    growth_periods = None

    if has_sufficient_history:
        first_val = valid_periods[0].get('value') if valid_periods[0].get('value') is not None else valid_periods[0].get('cil', 0)
        last_val = valid_periods[-1].get('value') if valid_periods[-1].get('value') is not None else valid_periods[-1].get('cil', 0)
        if first_val and first_val > 0:
            overall_growth_pct = round(((last_val - first_val) / first_val) * 100, 2)
            growth_periods = f"{valid_periods[0].get('period')} vs {valid_periods[-1].get('period')}"
        history_status = 'sufficient'
        history_message = f"Historical trend computed across {len(valid_periods)} periods ({growth_periods or ''})."
    else:
        history_status = 'insufficient'
        history_message = "Insufficient historical data for comparison (Upload previous financial year records to activate trend)"

    return Response({
        'dataset_id': resp_dataset_id,
        'dataset_name': dataset_name,
        'has_sufficient_history': has_sufficient_history,
        'history_status': history_status,
        'history_message': history_message,
        'overall_growth_pct': overall_growth_pct,
        'growth_periods': growth_periods,
        **trends,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def breakdown_view(request):
    """
    GET /api/analytics/breakdown/?dataset_id=<id>&group_by=subsidiary&metric=production&...
    Calculates grouped comparisons across single dataset or all user datasets when dataset_id='all'.
    """
    dataset_id = request.query_params.get('dataset_id')
    if not dataset_id:
        return Response({'error': 'dataset_id parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    engine, dataset_name, resp_dataset_id, err = _resolve_engine_and_dataset(dataset_id, request)
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

    fields = engine.get_available_fields()

    KNOWN_OPTIONAL_DIMENSIONS = {'grade', 'mine', 'subsidiary', 'financial_year', 'year', 'state', 'coal_type', 'location', 'area', 'block'}

    if group_by not in fields:
        is_multi = resp_dataset_id in ('all', 'baseline', 'uploaded')
        if is_multi or group_by in KNOWN_OPTIONAL_DIMENSIONS:
            return Response({
                'dataset_id': resp_dataset_id,
                'dataset_name': dataset_name,
                'series': [],
                'group_by': group_by,
                'metric': metric,
                'total_value': 0,
                'available': False,
                'message': f"Group dimension '{group_by}' is not present in dataset schema.",
            }, status=status.HTTP_200_OK)
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
        'dataset_id': resp_dataset_id,
        'dataset_name': dataset_name,
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

    engine, dataset_name, resp_dataset_id, err = _resolve_engine_and_dataset(dataset_id, request)
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
            'dataset_id': resp_dataset_id,
            'dataset_name': dataset_name,
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

    dataset_id_str = str(dataset_id).strip().lower()
    if dataset_id_str in ('baseline', 'reference'):
        records_qs = StructuredRecord.objects.filter(
            dataset__source_document__uploaded_by=request.user,
            dataset__source_document__is_reference=True,
            is_archived=False
        )
        resp_dataset_id = 'baseline'
        resp_dataset_name = 'Protected Historical Reference Data'
    elif dataset_id_str in ('uploaded', 'user_uploaded', 'user'):
        records_qs = StructuredRecord.objects.filter(
            dataset__source_document__uploaded_by=request.user,
            dataset__source_document__is_reference=False,
            is_archived=False
        )
        resp_dataset_id = 'uploaded'
        resp_dataset_name = 'User Uploaded Data'
    elif dataset_id_str == 'all':
        records_qs = StructuredRecord.objects.filter(
            dataset__source_document__uploaded_by=request.user,
            is_archived=False
        )
        resp_dataset_id = 'all'
        resp_dataset_name = 'All Uploaded Documents (Consolidated)'
    else:
        dataset, err = _get_owned_dataset(dataset_id, request)
        if err:
            return err
        records_qs = StructuredRecord.objects.filter(dataset=dataset)
        resp_dataset_id = dataset.id
        resp_dataset_name = dataset.name

    ids_str = request.query_params.get('record_ids', '')
    if not ids_str:
        return Response({'error': 'record_ids parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        id_list = [int(x.strip()) for x in ids_str.split(',') if x.strip().isdigit()][:100]
    except Exception:
        return Response({'error': 'Invalid record_ids format.'}, status=status.HTTP_400_BAD_REQUEST)

    records = records_qs.filter(id__in=id_list).order_by('row_index')
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
        'dataset_id': resp_dataset_id,
        'dataset_name': resp_dataset_name,
        'records': results,
        'total_count': len(results),
    }, status=status.HTTP_200_OK)
