"""
apps.reports.services.base_generator — Base Report Generator

Provides core extraction, KPI aggregation, provenance collection, and narrative synthesis
for all Phase 7 report types.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from django.utils import timezone

from apps.datasets.models import StructuredDataset, StructuredRecord
from apps.documents.models import Document
from apps.pipeline.models import ExtractionProvenance
from apps.analytics.query_engine import AnalyticsQueryEngine, parse_numeric, parse_financial_year, format_financial_year

logger = logging.getLogger(__name__)

NOT_AVAILABLE_MSG = "Data not available in selected sources."


class BaseReportGenerator:
    """
    Abstract base generator providing shared capabilities across all report types.
    """
    report_type_name: str = "Base Report"

    def __init__(
        self,
        user,
        organization: str = "CMPDI (HQ)",
        date_range: str = "All Available",
        filters: Optional[Dict[str, Any]] = None,
        datasets: Optional[List[StructuredDataset]] = None,
        documents: Optional[List[Document]] = None,
    ):
        self.user = user
        self.organization = organization or "CMPDI (HQ)"
        self.date_range = date_range or "All Available"
        self.filters = filters or {}
        self.datasets = datasets or []
        self.documents = documents or []
        self.provenance_records: List[Dict[str, Any]] = []

    def get_scoped_datasets(self) -> List[StructuredDataset]:
        """Return owner-scoped datasets passed or all available to user."""
        if self.datasets:
            return [d for d in self.datasets if d.source_document and d.source_document.uploaded_by == self.user]
        return list(
            StructuredDataset.objects.filter(source_document__uploaded_by=self.user)
            .select_related('source_document')
            .order_by('-created_at')
        )

    def get_scoped_documents(self) -> List[Document]:
        """Return owner-scoped documents passed or all available to user."""
        if self.documents:
            return [d for d in self.documents if d.uploaded_by == self.user]
        return list(
            Document.objects.filter(uploaded_by=self.user).order_by('-uploaded_at')
        )

    def extract_matching_records(self) -> List[StructuredRecord]:
        """
        Extract and filter valid structured records matching organization and date range filters.
        """
        all_records = []
        datasets = self.get_scoped_datasets()
        org_filter = None
        if self.organization and self.organization not in ("CMPDI (HQ)", "All", "All / CMPDI", "CIL (National)"):
            org_filter = self.organization.strip().upper()

        fy_filter = None
        if self.date_range and self.date_range not in ("All Available", "All", "Custom Range"):
            # Extract FY if present e.g. "FY 2024-25" -> "2024-25"
            m = re.search(r'(\d{2,4}[\-/]\d{2,4})', self.date_range)
            if m:
                fy_filter = m.group(1)

        for ds in datasets:
            engine = AnalyticsQueryEngine(ds)
            filters = dict(self.filters)
            if org_filter:
                filters['subsidiary'] = org_filter
            if fy_filter:
                filters['financial_year'] = fy_filter

            matched = engine.filter_records(filters=filters, exclude_errors=True)
            all_records.extend(matched)

        return all_records

    def collect_provenance_for_records(self, records: List[StructuredRecord], max_items: int = 50) -> List[Dict[str, Any]]:
        """
        Collect traceable provenance records for a given set of records.
        """
        if not records:
            return []

        rec_ids = [r.id for r in records[:max_items]]
        prov_qs = ExtractionProvenance.objects.filter(record_id__in=rec_ids).select_related('record', 'record__dataset', 'record__dataset__source_document')

        citations = []
        for p in prov_qs:
            doc = p.record.dataset.source_document if p.record and p.record.dataset else None
            doc_title = doc.title if doc else "Structured Dataset"
            doc_id = doc.id if doc else None
            citations.append({
                'source_type': 'dataset',
                'name': p.record.dataset.name if p.record and p.record.dataset else doc_title,
                'document_id': doc_id,
                'document_title': doc_title,
                'dataset_id': p.record.dataset_id if p.record else None,
                'page_number': p.page_number,
                'section_heading': p.section_heading,
                'sheet_name': p.sheet_name,
                'row_index': p.row_index or (p.record.row_index if p.record else None),
                'field': getattr(p, 'field_name', None) or 'data',
                'value': None,
                'extractor_type': p.extraction_method or 'xlsx',
                'confidence': p.confidence if p.confidence is not None else 1.0,
                'source_ref': p.source_reference or f"Row {p.row_index or 'N/A'}, Sheet: {p.sheet_name or 'Main'}",
            })
        return citations

    def retrieve_narrative_context(self, search_query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve relevant document chunks using existing Phase 5 intelligence retrieval.
        """
        try:
            from apps.intelligence.retrieval.retriever import retrieve_document_chunks
            chunks = retrieve_document_chunks(self.user, search_query, top_k=top_k)
            for c in chunks:
                self.provenance_records.append({
                    'source_type': 'document',
                    'name': c.get('document_title', 'Document'),
                    'document_id': c.get('document_id'),
                    'document_title': c.get('document_title'),
                    'page_number': c.get('page_number'),
                    'section_heading': c.get('section_heading'),
                    'sheet_name': c.get('sheet_name'),
                    'row_index': None,
                    'field': 'text_content',
                    'value': c.get('content', '')[:100],
                    'extractor_type': c.get('extractor_type', 'doc'),
                    'confidence': 1.0,
                    'source_ref': c.get('source_ref', f"Doc: {c.get('document_title')} (p. {c.get('page_number', '1')})"),
                })
            return chunks
        except Exception as e:
            logger.warning(f"Could not retrieve narrative document chunks: {e}")
            return []

    def calculate_production_aggregates(self, records: List[StructuredRecord]) -> Dict[str, Any]:
        """
        Calculate key aggregates from records: total production, target, dispatch, achievement %, growth %.
        """
        if not records:
            return {
                'total_production': 0.0,
                'total_target': 0.0,
                'total_dispatch': 0.0,
                'achievement_pct': None,
                'mine_count': 0,
                'subsidiary_count': 0,
                'record_count': 0,
            }

        prod_sum = 0.0
        target_sum = 0.0
        dispatch_sum = 0.0
        mines = set()
        subs = set()

        for r in records:
            data = r.data_json or {}
            p = parse_numeric(data.get('production'))
            t = parse_numeric(data.get('target'))
            d = parse_numeric(data.get('dispatch'))

            if p is not None:
                prod_sum += p
            if t is not None:
                target_sum += t
            if d is not None:
                dispatch_sum += d

            mine = data.get('mine') or data.get('mine_name')
            if mine:
                mines.add(str(mine).strip())

            sub = data.get('subsidiary')
            if sub:
                subs.add(str(sub).strip().upper())

        ach_pct = round((prod_sum / target_sum * 100), 2) if target_sum > 0 else None

        return {
            'total_production': round(prod_sum, 2),
            'total_target': round(target_sum, 2),
            'total_dispatch': round(dispatch_sum, 2),
            'achievement_pct': ach_pct,
            'mine_count': len(mines),
            'subsidiary_count': len(subs),
            'record_count': len(records),
        }

    def generate(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Execute report generation. Subclasses must implement this.
        Returns (content_json, provenance_json).
        """
        raise NotImplementedError("Subclasses must implement generate()")
