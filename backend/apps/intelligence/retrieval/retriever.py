"""
Retrieval engine for CMPDI Mining Intelligence.

Supports:
  - User-scoped access filtering during retrieval
  - BM25 ranked document chunk retrieval with heading and phrase boosts
  - Deterministic structured data querying and aggregations (sum, max, min, avg)
  - Full provenance retrieval (page, section, table, row, sheet, record)
"""

import math
import re
from typing import List, Dict, Any, Optional
from collections import Counter

from django.db.models import Q

from apps.intelligence.models import DocumentChunk
from apps.datasets.models import StructuredDataset, StructuredRecord
from apps.pipeline.models import ExtractionProvenance

# Stopwords for lightweight BM25 filtering
STOPWORDS = {
    'a', 'an', 'the', 'in', 'on', 'at', 'of', 'for', 'to', 'from', 'by',
    'with', 'about', 'into', 'through', 'during', 'before', 'after',
    'above', 'below', 'under', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'do', 'does', 'did', 'and', 'or',
    'but', 'if', 'because', 'as', 'what', 'which', 'who', 'whom', 'this',
    'that', 'these', 'those', 'am', 'it', 'its', 'they', 'them', 'their'
}


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric tokens without stopwords."""
    words = re.findall(r'[a-zA-Z0-9_\-\.]+', text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def bm25_score_chunks(query_tokens: List[str], chunks: List[DocumentChunk], k1: float = 1.5, b: float = 0.75) -> List[tuple]:
    """
    Score DocumentChunks using BM25 ranking algorithm.
    Returns list of (chunk, score) sorted descending by score.
    """
    if not query_tokens or not chunks:
        return []

    # Pre-tokenize all chunks
    chunk_docs = []
    total_len = 0
    df = Counter()

    for chunk in chunks:
        tokens = tokenize(chunk.content)
        # Also include section heading in searchable tokens with extra weight
        if chunk.section_heading:
            tokens.extend(tokenize(chunk.section_heading))
        chunk_docs.append(tokens)
        total_len += len(tokens)
        # Document frequency: unique terms in this chunk
        for term in set(tokens):
            df[term] += 1

    N = len(chunks)
    avgdl = max(1.0, total_len / max(1, N))

    scored = []
    query_text = ' '.join(query_tokens)

    for idx, chunk in enumerate(chunks):
        doc_tokens = chunk_docs[idx]
        doc_len = len(doc_tokens)
        tf = Counter(doc_tokens)
        score = 0.0

        for q in query_tokens:
            if q not in tf:
                continue
            # Term IDF
            n_q = df.get(q, 0)
            idf = math.log(1.0 + (N - n_q + 0.5) / (n_q + 0.5))
            term_freq = tf[q]
            denom = term_freq + k1 * (1.0 - b + b * (doc_len / avgdl))
            score += idf * ((term_freq * (k1 + 1.0)) / max(1e-5, denom))

        # Exact phrase match boost
        if query_text in chunk.content.lower():
            score += 0.5

        # Section heading term match boost
        if chunk.section_heading:
            heading_lower = chunk.section_heading.lower()
            if any(q in heading_lower for q in query_tokens):
                score += 0.3

        if score > 0:
            scored.append((chunk, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def retrieve_document_chunks(
    user,
    query: str,
    top_k: int = 5,
    min_score: float = 0.1,
    document_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve user-authorized document chunks matching the query.
    Enforces owner filtering strictly during retrieval.
    """
    if not user or not user.is_authenticated:
        return []

    # This is also a service boundary used by future callers; retain the UI's
    # small default and prevent an accidental unbounded evidence/context load.
    try:
        top_k = max(1, min(int(top_k), 20))
    except (TypeError, ValueError):
        top_k = 5

    # Strict multi-tenancy: Only search user's unarchived documents
    qs = DocumentChunk.objects.filter(
        document__uploaded_by=user,
        document__is_archived=False,
    ).select_related('document')

    if document_id:
        qs = qs.filter(document_id=document_id)

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    # Fast DB candidate pre-filtering: chunks containing at least one query term
    # or if few chunks total, score all directly
    total_chunk_count = qs.count()
    if total_chunk_count == 0:
        return []

    if total_chunk_count > 100:
        q_filter = Q()
        for token in query_tokens[:5]:
            q_filter |= Q(content__icontains=token) | Q(section_heading__icontains=token)
        candidate_chunks = list(qs.filter(q_filter)[:80])
    else:
        candidate_chunks = list(qs[:100])

    if not candidate_chunks:
        return []

    scored_chunks = bm25_score_chunks(query_tokens, candidate_chunks)

    results = []
    for chunk, score in scored_chunks[:top_k]:
        if score < min_score:
            continue
        meta = chunk.metadata or {}
        results.append({
            'chunk_id': chunk.pk,
            'document_id': chunk.document_id,
            'document_title': chunk.document.title or chunk.document.original_filename,
            'page_number': chunk.page_number,
            'section_heading': chunk.section_heading,
            'content': chunk.content,
            'score': round(score, 3),
            'table_reference': meta.get('table_reference', ''),
            'sheet_name': meta.get('sheet_name', ''),
            'extractor_type': meta.get('extractor_type', ''),
            'ocr_used': meta.get('ocr_used', False),
            'source_ref': f"doc:{chunk.document_id}:page:{chunk.page_number or 'N/A'}:chunk:{chunk.chunk_index}",
        })

    return results


def _extract_numeric(val: Any) -> Optional[float]:
    """Extract float from number, string, or normalized dict."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, dict):
        if 'value' in val and val['value'] is not None:
            try:
                return float(val['value'])
            except (ValueError, TypeError):
                pass
    if isinstance(val, str):
        # strip unit suffixes like MT, Mt, Tonnes
        clean = re.sub(r'[^\d\.\-]', '', val.split()[0] if val.split() else val)
        try:
            return float(clean)
        except ValueError:
            return None
    return None


def _record_subsidiary(data: Dict[str, Any]) -> Optional[str]:
    """Return the subsidiary value from a structured record, preserving its source value."""
    for key, value in data.items():
        if key.lower() in {'subsidiary', 'company', 'company_name'} and value not in (None, ''):
            return str(value).strip()
    return None


def retrieve_structured_data(
    user,
    entities: Dict[str, Any],
    raw_query: str = '',
) -> Dict[str, Any]:
    """
    Retrieve and calculate structured data strictly from user's datasets & records.
    Never hallucinates calculations or values.
    """
    if not user or not user.is_authenticated:
        return {'found': False, 'reason': 'User unauthenticated'}

    sub_target = entities.get('subsidiary')
    year_target = entities.get('year')
    agg_type = entities.get('aggregation')
    metric_type = entities.get('metric') or 'production'

    # Strict multi-tenancy: Only search user's unarchived datasets
    records_qs = StructuredRecord.objects.filter(
        dataset__source_document__uploaded_by=user,
        dataset__source_document__is_archived=False,
    ).select_related('dataset', 'dataset__source_document').prefetch_related('provenance')

    if not records_qs.exists():
        return {'found': False, 'reason': 'No structured datasets available for user.'}

    matching_records = []

    for rec in records_qs:
        data = rec.data_json or {}
        # Match subsidiary if requested
        if sub_target:
            sub_val = str(data.get('subsidiary', '')).upper()
            all_vals_str = ' '.join(str(v) for v in data.values()).upper()
            if sub_target not in sub_val and sub_target not in all_vals_str:
                continue

        # Match financial year if requested
        if year_target:
            yr_val = str(data.get('financial_year', data.get('year', ''))).lower()
            all_vals_str = ' '.join(str(v) for v in data.values()).lower()
            yr_clean = year_target.lower().replace('fy', '').replace(' ', '').replace('–', '-')
            if yr_clean not in yr_val.replace('–', '-') and yr_clean not in all_vals_str.replace('–', '-'):
                continue

        # Find metric numeric value
        num_val = None
        metric_field_name = None
        for k, v in data.items():
            k_lower = k.lower()
            if metric_type in k_lower or ('production' in k_lower and metric_type == 'production'):
                num = _extract_numeric(v)
                if num is not None:
                    num_val = num
                    metric_field_name = k
                    break

        if num_val is not None or not (agg_type or metric_type):
            matching_records.append({
                'record': rec,
                'data': data,
                'numeric_value': num_val,
                'metric_field': metric_field_name,
            })

    if not matching_records:
        return {'found': False, 'reason': f'No records found matching subsidiary={sub_target}, year={year_target}'}

    # Deterministic calculations
    result_val: Optional[float] = None
    selected_items: List[Dict[str, Any]] = []
    unit = 'MT'

    if agg_type == 'max':
        # Find item with highest numeric value
        items_with_num = [m for m in matching_records if m['numeric_value'] is not None]
        if items_with_num:
            best = max(items_with_num, key=lambda x: x['numeric_value'])
            result_val = best['numeric_value']
            selected_items = [best]
    elif agg_type == 'min':
        items_with_num = [m for m in matching_records if m['numeric_value'] is not None]
        if items_with_num:
            best = min(items_with_num, key=lambda x: x['numeric_value'])
            result_val = best['numeric_value']
            selected_items = [best]
    elif agg_type == 'sum':
        items_with_num = [m for m in matching_records if m['numeric_value'] is not None]
        if items_with_num:
            result_val = sum(m['numeric_value'] for m in items_with_num)
            selected_items = items_with_num
    elif agg_type == 'avg':
        items_with_num = [m for m in matching_records if m['numeric_value'] is not None]
        if items_with_num:
            result_val = sum(m['numeric_value'] for m in items_with_num) / len(items_with_num)
            selected_items = items_with_num
    else:
        # Single record or lookup
        selected_items = matching_records[:5]
        if selected_items and selected_items[0]['numeric_value'] is not None:
            result_val = selected_items[0]['numeric_value']

    # Build provenance citations
    citations = []
    for item in selected_items:
        rec = item['record']
        doc = rec.dataset.source_document
        prov = rec.provenance.first()
        citations.append({
            'document_id': doc.pk if doc else None,
            'document_title': (doc.title or doc.original_filename) if doc else rec.dataset.name,
            'dataset_id': rec.dataset.pk,
            'dataset_name': rec.dataset.name,
            'record_id': rec.pk,
            'row_index': prov.row_index if prov else rec.row_index,
            'page_number': prov.page_number if prov else None,
            'section_heading': prov.section_heading if prov else '',
            'table_reference': prov.table_reference if prov else '',
            'sheet_name': prov.sheet_name if prov else '',
            'field': item.get('metric_field') or 'record_data',
            'value': item.get('numeric_value'),
            'extraction_method': prov.extraction_method if prov else 'extracted',
            'ocr_used': prov.ocr_used if prov else False,
            'source_ref': prov.source_reference if prov else f"record:{rec.pk}",
        })

    # An aggregate query such as "Which subsidiary had the highest production?"
    # does not supply a subsidiary entity.  Return the entity from the selected
    # authoritative record so the answer can identify the actual winner.
    result_subsidiary = sub_target
    if not result_subsidiary and selected_items:
        result_subsidiary = _record_subsidiary(selected_items[0]['data'])

    return {
        'found': True,
        'calculation_type': agg_type or 'lookup',
        'metric': metric_type,
        'subsidiary': result_subsidiary,
        'year': year_target,
        'result_value': round(result_val, 2) if result_val is not None else None,
        'unit': unit,
        'record_count': len(selected_items),
        'records_data': [item['data'] for item in selected_items],
        'citations': citations,
    }
