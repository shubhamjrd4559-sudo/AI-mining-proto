"""
apps.analytics.query_engine — Dynamic Analytics Query & KPI Engine (Phase 6)

Builds a real analytics layer over validated, normalized, and maintained StructuredRecords.
Guarantees:
  1. Real persisted data only — zero mock/hardcoded data.
  2. Owner-scoped and authorized data access.
  3. Safe dynamic filtering — no raw SQL, validated fields only.
  4. Data-quality aware — automatically excludes ERROR-level records.
  5. Accurate Financial Year sorting and comparisons (FY 2024-25 != 2024).
  6. Preserves contributing record IDs for full provenance drill-down.
"""

import re
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Set

from apps.datasets.models import StructuredDataset, StructuredRecord
from apps.pipeline.models import ExtractionProvenance, ValidationResult

logger = logging.getLogger(__name__)

FY_PATTERN = re.compile(
    r'(?:fy|f\.y\.|financial\s*year)?\s*(\d{2,4})[\-/](\d{2,4})',
    re.IGNORECASE
)

NUMERIC_CONCEPT_NAMES = {
    'production', 'target', 'dispatch', 'reserve', 'resource',
    'seam_thickness', 'borehole_depth', 'depth', 'count', 'value', 'amount'
}

DIMENSION_CONCEPT_NAMES = {
    'subsidiary', 'mine', 'coalfield', 'block', 'project', 'state',
    'district', 'financial_year', 'reporting_period', 'month',
    'coal_type', 'grade', 'status', 'organization'
}


def parse_numeric(val: Any) -> Optional[float]:
    """Safely convert a cell value into float, ignoring units or formatted commas."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(',', '')
    if not s:
        return None
    m = re.search(r'[\-+]?\d+(?:\.\d+)?(?:[eE][\-+]?\d+)?', s)
    if m:
        try:
            return float(m.group(0))
        except (ValueError, TypeError):
            return None
    return None


def parse_financial_year(raw: Any) -> Optional[Tuple[int, int]]:
    """
    Parse financial year string into a sortable tuple (start_year, end_year).
    E.g. '2024-25' -> (2024, 2025), 'FY21-22' -> (2021, 2022).
    """
    if not raw:
        return None
    m = FY_PATTERN.search(str(raw).strip())
    if not m:
        return None
    s1, s2 = m.group(1), m.group(2)
    if len(s1) == 2:
        start_year = 2000 + int(s1)
    else:
        start_year = int(s1)
    if len(s2) == 2:
        end_year = (start_year // 100) * 100 + int(s2)
        if end_year < start_year:
            end_year += 100
    else:
        end_year = int(s2)
    return (start_year, end_year)


def format_financial_year(fy_tuple: Tuple[int, int]) -> str:
    """Format (2024, 2025) -> '2024-25'."""
    return f"{fy_tuple[0]}-{str(fy_tuple[1])[-2:]}"


class AnalyticsQueryEngine:
    """
    Query execution and KPI aggregation engine for a single StructuredDataset.
    """

    def __init__(self, dataset: StructuredDataset):
        self.dataset = dataset
        self._records_cache: Optional[List[StructuredRecord]] = None
        self._provenance_cache: Optional[Dict[int, List[ExtractionProvenance]]] = None
        self._error_record_ids: Optional[Set[int]] = None
        self._warning_record_ids: Optional[Set[int]] = None
        self._available_fields: Optional[Dict[str, str]] = None

    def get_available_fields(self) -> Dict[str, str]:
        """
        Returns a dict of {field_name: field_type} discovered from schema and records.
        Field types: 'numeric', 'categorical', 'text'.
        """
        if self._available_fields is not None:
            return self._available_fields

        schema = self.dataset.schema_json or {}
        cols = schema.get('columns', [])
        cmap = schema.get('column_map', {})

        fields = {}
        for c in cols:
            concept = cmap.get(c, {}).get('concept') or c
            fields[concept] = 'numeric' if concept in NUMERIC_CONCEPT_NAMES else 'categorical'

        # Inspect up to first 50 records to discover actual keys in data_json
        records = self._load_records()[:50]
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

    def _load_records(self) -> List[StructuredRecord]:
        if self._records_cache is None:
            self._records_cache = list(
                StructuredRecord.objects.filter(dataset=self.dataset)
                .select_related('dataset')
                .order_by('row_index', 'id')
            )
        return self._records_cache

    def _load_provenance(self) -> Dict[int, List[ExtractionProvenance]]:
        if self._provenance_cache is None:
            provs = ExtractionProvenance.objects.filter(record__dataset=self.dataset)
            cache = defaultdict(list)
            for p in provs:
                cache[p.record_id].append(p)
            self._provenance_cache = cache
        return self._provenance_cache

    def _get_quality_record_ids(self) -> Tuple[Set[int], Set[int]]:
        """Identify records with ERRORs and WARNINGs."""
        if self._error_record_ids is not None and self._warning_record_ids is not None:
            return self._error_record_ids, self._warning_record_ids

        error_ids = set()
        warning_ids = set()

        records = self._load_records()
        for r in records:
            if not r.is_valid:
                error_ids.add(r.id)
            if r.validation_errors:
                if any(isinstance(e, dict) and e.get('severity') == 'ERROR' for e in r.validation_errors):
                    error_ids.add(r.id)
                elif any(isinstance(e, dict) and e.get('severity') == 'WARNING' for e in r.validation_errors):
                    warning_ids.add(r.id)

        doc = self.dataset.source_document
        if doc:
            v_results = ValidationResult.objects.filter(document=doc, status='open')
            for v in v_results:
                if v.severity == 'ERROR':
                    if v.record_id:
                        error_ids.add(v.record_id)
                elif v.severity == 'WARNING':
                    if v.record_id:
                        warning_ids.add(v.record_id)

        self._error_record_ids = error_ids
        self._warning_record_ids = warning_ids
        return error_ids, warning_ids

    def get_distinct_filter_options(self) -> Dict[str, List[str]]:
        """Return available distinct filter values for categorical fields."""
        fields = self.get_available_fields()
        options: Dict[str, Set[str]] = defaultdict(set)
        records = self._load_records()

        # Categorical concepts of interest
        filter_keys = [
            'subsidiary', 'mine', 'state', 'district', 'coalfield',
            'financial_year', 'reporting_period', 'month', 'coal_type',
            'grade', 'project', 'status'
        ]

        for r in records:
            data = r.data_json
            for k in filter_keys:
                if k in data and data[k] not in (None, ''):
                    options[k].add(str(data[k]).strip())
                elif k in fields:
                    # check if raw column mapped to concept
                    raw_val = data.get(k)
                    if raw_val not in (None, ''):
                        options[k].add(str(raw_val).strip())

        # Sort values cleanly (special handling for financial year)
        result: Dict[str, List[str]] = {}
        for k, vals in options.items():
            if not vals:
                continue
            if k == 'financial_year':
                def fy_key(v):
                    p = parse_financial_year(v)
                    return p if p else (9999, 9999)
                result[k] = sorted(list(vals), key=fy_key)
            else:
                result[k] = sorted(list(vals))

        # Also get available sheets from provenance
        prov_cache = self._load_provenance()
        sheets = set()
        for plist in prov_cache.values():
            for p in plist:
                if p.sheet_name:
                    sheets.add(p.sheet_name.strip())
        if sheets:
            result['sheet'] = sorted(list(sheets))

        return result

    def filter_records(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sheet: Optional[str] = None,
        exclude_errors: bool = True,
        search_query: Optional[str] = None,
    ) -> List[StructuredRecord]:
        """
        Filter records based on dynamic criteria, sheet, search, and data quality.
        """
        records = self._load_records()
        error_ids, _ = self._get_quality_record_ids()
        prov_cache = self._load_provenance()

        # Validate filter keys
        valid_fields = self.get_available_fields()
        clean_filters = {}
        if filters:
            for k, v in filters.items():
                if v is None or v == '' or v == 'all' or v == 'All':
                    continue
                # Normalize key
                k_clean = str(k).strip()
                if k_clean in valid_fields or k_clean in ('sheet', 'data_quality'):
                    clean_filters[k_clean] = str(v).strip().lower()

        filtered = []
        q_lower = search_query.strip().lower() if search_query else None

        for r in records:
            if exclude_errors and r.id in error_ids:
                continue

            # Sheet filtering via provenance
            if sheet and sheet != 'all':
                r_provs = prov_cache.get(r.id, [])
                if not any(p.sheet_name and p.sheet_name.strip().lower() == sheet.strip().lower() for p in r_provs):
                    continue

            # Global search
            if q_lower:
                row_str = " ".join(str(v).lower() for k, v in r.data_json.items() if not k.endswith('_original'))
                if q_lower not in row_str:
                    continue

            # Dynamic field filters
            matched = True
            for fk, fval in clean_filters.items():
                if fk in ('sheet', 'data_quality'):
                    continue
                val = r.data_json.get(fk)
                if val is None:
                    matched = False
                    break
                # Check for exact or normalized match
                val_str = str(val).strip().lower()
                if fk == 'financial_year':
                    p1 = parse_financial_year(val_str)
                    p2 = parse_financial_year(fval)
                    if p1 and p2:
                        if p1 != p2:
                            matched = False
                            break
                    elif val_str != fval:
                        matched = False
                        break
                else:
                    if val_str != fval and fval not in val_str:
                        matched = False
                        break

            if matched:
                filtered.append(r)

        return filtered

    def calculate_kpis(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sheet: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate dynamic KPIs from real persisted records.
        """
        all_records = self._load_records()
        error_ids, warning_ids = self._get_quality_record_ids()

        filtered_records = self.filter_records(filters=filters, sheet=sheet, exclude_errors=True)

        # Quality metrics across dataset
        total_count = len(all_records)
        error_count = len(error_ids)
        warning_count = len(warning_ids)
        valid_count = max(0, total_count - error_count)
        valid_pct = round((valid_count / total_count * 100), 1) if total_count > 0 else 100.0

        # Discover present metrics
        fields = self.get_available_fields()

        has_production = 'production' in fields
        has_dispatch = 'dispatch' in fields
        has_target = 'target' in fields
        has_mine = 'mine' in fields
        has_subsidiary = 'subsidiary' in fields

        prod_sum = 0.0
        dispatch_sum = 0.0
        target_sum = 0.0
        prod_count = 0
        dispatch_count = 0
        target_count = 0

        mines = set()
        subsidiaries = set()

        # For YoY Growth calculation
        fy_production: Dict[Tuple[int, int], float] = defaultdict(float)

        for r in filtered_records:
            d = r.data_json

            if has_production:
                v = parse_numeric(d.get('production'))
                if v is not None:
                    prod_sum += v
                    prod_count += 1
                    fy_raw = d.get('financial_year')
                    fy_parsed = parse_financial_year(fy_raw)
                    if fy_parsed:
                        fy_production[fy_parsed] += v

            if has_dispatch:
                v = parse_numeric(d.get('dispatch'))
                if v is not None:
                    dispatch_sum += v
                    dispatch_count += 1

            if has_target:
                v = parse_numeric(d.get('target'))
                if v is not None:
                    target_sum += v
                    target_count += 1

            if has_mine and d.get('mine'):
                mines.add(str(d['mine']).strip())

            if has_subsidiary and d.get('subsidiary'):
                subsidiaries.add(str(d['subsidiary']).strip())

        kpis: Dict[str, Any] = {
            'total_records': len(filtered_records),
            'dataset_total_records': total_count,
            'quality': {
                'total_records': total_count,
                'valid_count': valid_count,
                'warning_count': warning_count,
                'error_count': error_count,
                'valid_pct': valid_pct,
            }
        }

        if prod_count > 0:
            kpis['total_production'] = round(prod_sum, 2)
            kpis['production_unit'] = 'MT'

        if dispatch_count > 0:
            kpis['total_dispatch'] = round(dispatch_sum, 2)
            kpis['dispatch_unit'] = 'MT'

        if target_count > 0:
            kpis['total_target'] = round(target_sum, 2)
            kpis['target_unit'] = 'MT'

        if prod_count > 0 and target_count > 0 and target_sum > 0:
            kpis['achievement_pct'] = round((prod_sum / target_sum * 100), 1)

        # YoY Growth
        if len(fy_production) >= 2:
            sorted_fys = sorted(fy_production.keys())
            prev_fy = sorted_fys[-2]
            curr_fy = sorted_fys[-1]
            prev_val = fy_production[prev_fy]
            curr_val = fy_production[curr_fy]
            if prev_val > 0:
                kpis['growth_pct'] = round(((curr_val - prev_val) / prev_val * 100), 1)
                kpis['growth_periods'] = f"{format_financial_year(prev_fy)} → {format_financial_year(curr_fy)}"

        if len(mines) > 0:
            kpis['mine_count'] = len(mines)

        if len(subsidiaries) > 0:
            kpis['subsidiary_count'] = len(subsidiaries)

        return kpis

    def calculate_trends(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sheet: Optional[str] = None,
        metric: str = 'production',
        time_field: str = 'financial_year',
    ) -> Dict[str, Any]:
        """
        Time-series trend calculation with proper Financial Year chronological ordering.
        """
        records = self.filter_records(filters=filters, sheet=sheet, exclude_errors=True)

        period_data: Dict[Any, Dict[str, Any]] = defaultdict(lambda: {
            'metric_val': 0.0,
            'target_val': 0.0,
            'dispatch_val': 0.0,
            'count': 0,
            'record_ids': [],
        })

        is_fy = (time_field == 'financial_year')

        for r in records:
            d = r.data_json
            period_raw = d.get(time_field)
            if not period_raw:
                continue

            if is_fy:
                key = parse_financial_year(period_raw)
                if not key:
                    continue
            else:
                key = str(period_raw).strip()

            val = parse_numeric(d.get(metric))
            if val is not None:
                period_data[key]['metric_val'] += val
                period_data[key]['count'] += 1
                period_data[key]['record_ids'].append(r.id)

            t_val = parse_numeric(d.get('target'))
            if t_val is not None:
                period_data[key]['target_val'] += t_val

            dis_val = parse_numeric(d.get('dispatch'))
            if dis_val is not None:
                period_data[key]['dispatch_val'] += dis_val

        # Sort periods
        if is_fy:
            sorted_keys = sorted(period_data.keys())
        else:
            sorted_keys = sorted(period_data.keys(), key=lambda x: str(x))

        series = []
        for k in sorted_keys:
            data = period_data[k]
            label = format_financial_year(k) if is_fy else str(k)
            item = {
                'period': label,
                'value': round(data['metric_val'], 2),
                'count': data['count'],
                'record_ids': data['record_ids'][:100],  # bounded provenance references
            }
            if data['target_val'] > 0:
                item['target'] = round(data['target_val'], 2)
                item['achievement_pct'] = round((data['metric_val'] / data['target_val'] * 100), 1)
            if data['dispatch_val'] > 0:
                item['dispatch'] = round(data['dispatch_val'], 2)

            series.append(item)

        # Compute period-over-period growth
        for i in range(1, len(series)):
            prev = series[i - 1]['value']
            curr = series[i]['value']
            if prev > 0:
                series[i]['growth_pct'] = round(((curr - prev) / prev * 100), 1)

        return {
            'metric': metric,
            'time_field': time_field,
            'series': series,
            'total_periods': len(series),
        }

    def calculate_breakdown(
        self,
        group_by: str = 'subsidiary',
        metric: str = 'production',
        filters: Optional[Dict[str, Any]] = None,
        sheet: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Grouped comparisons (e.g. production by subsidiary, production by mine, grade distribution).
        """
        records = self.filter_records(filters=filters, sheet=sheet, exclude_errors=True)

        groups: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'value': 0.0,
            'count': 0,
            'record_ids': [],
        })

        is_count_metric = (metric == 'count')

        for r in records:
            d = r.data_json
            grp_val = d.get(group_by)
            if grp_val in (None, ''):
                continue
            grp_label = str(grp_val).strip()

            if is_count_metric:
                groups[grp_label]['value'] += 1
                groups[grp_label]['count'] += 1
                groups[grp_label]['record_ids'].append(r.id)
            else:
                num_val = parse_numeric(d.get(metric))
                if num_val is not None:
                    groups[grp_label]['value'] += num_val
                    groups[grp_label]['count'] += 1
                    groups[grp_label]['record_ids'].append(r.id)

        # Sort descending by value
        sorted_groups = sorted(
            groups.items(),
            key=lambda item: item[1]['value'],
            reverse=True
        )[:limit]

        total_val = sum(g[1]['value'] for g in sorted_groups)

        series = []
        for label, data in sorted_groups:
            pct = round((data['value'] / total_val * 100), 1) if total_val > 0 else 0.0
            series.append({
                'group': label,
                'value': round(data['value'], 2),
                'count': data['count'],
                'share_pct': pct,
                'record_ids': data['record_ids'][:50],  # drill-down trace
            })

        return {
            'group_by': group_by,
            'metric': metric,
            'total_value': round(total_val, 2),
            'series': series,
        }

    def execute_query(
        self,
        aggregation: str,
        metric: str,
        group_by: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        sheet: Optional[str] = None,
        sort_by: str = 'value',
        sort_dir: str = 'desc',
        limit: int = 50,
        exclude_errors: bool = True,
    ) -> Dict[str, Any]:
        """
        Flexible core aggregation query API:
        Supports SUM, AVG, MIN, MAX, COUNT with optional grouping and dynamic filtering.
        """
        agg = aggregation.lower().strip()
        if agg not in ('sum', 'avg', 'min', 'max', 'count'):
            raise ValueError(f"Unsupported aggregation '{aggregation}'. Must be sum, avg, min, max, or count.")

        records = self.filter_records(filters=filters, sheet=sheet, exclude_errors=exclude_errors)

        if not group_by:
            # Overall single-result aggregation
            values = []
            contributing_ids = []
            for r in records:
                v = parse_numeric(r.data_json.get(metric)) if agg != 'count' else 1.0
                if v is not None:
                    values.append(v)
                    contributing_ids.append(r.id)

            if not values:
                computed = 0.0
            elif agg == 'sum':
                computed = sum(values)
            elif agg == 'avg':
                computed = sum(values) / len(values)
            elif agg == 'min':
                computed = min(values)
            elif agg == 'max':
                computed = max(values)
            elif agg == 'count':
                computed = float(len(values))

            return {
                'aggregation': agg,
                'metric': metric,
                'result': round(computed, 2),
                'record_count': len(values),
                'record_ids': contributing_ids[:100],
            }

        # Grouped aggregation
        grouped_vals: Dict[str, List[float]] = defaultdict(list)
        grouped_ids: Dict[str, List[int]] = defaultdict(list)

        for r in records:
            grp = r.data_json.get(group_by)
            if grp in (None, ''):
                continue
            grp_key = str(grp).strip()
            v = parse_numeric(r.data_json.get(metric)) if agg != 'count' else 1.0
            if v is not None:
                grouped_vals[grp_key].append(v)
                grouped_ids[grp_key].append(r.id)

        series = []
        for grp_key, vals in grouped_vals.items():
            if not vals:
                continue
            if agg == 'sum':
                ans = sum(vals)
            elif agg == 'avg':
                ans = sum(vals) / len(vals)
            elif agg == 'min':
                ans = min(vals)
            elif agg == 'max':
                ans = max(vals)
            elif agg == 'count':
                ans = float(len(vals))
            series.append({
                'group': grp_key,
                'value': round(ans, 2),
                'count': len(vals),
                'record_ids': grouped_ids[grp_key][:50],
            })

        # Sorting
        reverse = (sort_dir.lower() == 'desc')
        if sort_by == 'group':
            if group_by == 'financial_year':
                def fy_sort(x):
                    p = parse_financial_year(x['group'])
                    return p if p else (9999, 9999)
                series.sort(key=fy_sort, reverse=reverse)
            else:
                series.sort(key=lambda x: str(x['group']).lower(), reverse=reverse)
        else:
            series.sort(key=lambda x: x['value'], reverse=reverse)

        return {
            'aggregation': agg,
            'metric': metric,
            'group_by': group_by,
            'series': series[:limit],
            'total_groups': len(series),
        }
