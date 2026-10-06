"""
Retrieval engine for CMPDI Mining Intelligence.

Supports:
  - User-scoped access filtering during retrieval
  - BM25 ranked document chunk retrieval with heading and phrase boosts
  - Deterministic structured data querying and aggregations (sum, max, min, avg)
  - Full provenance retrieval (page, section, table, row, sheet, record)
  - Baseline/reference-scoped retrieval for authorized historical comparison queries
    (read-only; no ownership filter required — baseline data is shared for all
    authenticated users but is never modified through this layer)
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
    words = [w.strip('.') for w in re.findall(r'[a-zA-Z0-9_\-\.]+', text.lower())]
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


def _resolve_records_metric(
    records_qs,
    entities: Dict[str, Any],
    raw_query: str = '',
    is_baseline: bool = False,
) -> Dict[str, Any]:
    """
    Field-aware structured metric resolution across structured records.
    Distinguishes document-level summary rows from subsidiary-specific rows.
    Prefers exact matching canonical fields, and never arbitrarily selects a subsidiary
    record when the user did not specify one.
    """
    sub_target = entities.get('subsidiary')
    year_target = entities.get('year')
    agg_type = entities.get('aggregation')
    metric_type = entities.get('metric')
    if not metric_type:
        return {'found': False, 'reason': 'No structured metric identified in query.'}

    doc_candidates = []
    sub_candidates = []

    for rec in records_qs:
        data = rec.data_json or {}

        # Match financial year if requested
        if year_target:
            yr_val = str(data.get('financial_year', data.get('year', ''))).lower()
            all_vals_str = ' '.join(str(v) for v in data.values()).lower()
            yr_clean = year_target.lower().replace('fy', '').replace(' ', '').replace('–', '-')
            if yr_clean not in yr_val.replace('–', '-') and yr_clean not in all_vals_str.replace('–', '-'):
                continue

        # --- Type A: Key-Value Summary Records (Document-Level) ---
        field_desc = None
        for k in ('Field', 'Metric', 'Parameter', 'Indicator', 'Item', 'Key'):
            if k in data and data[k]:
                field_desc = str(data[k]).strip()
                break

        if field_desc:
            f_lower = field_desc.lower()
            val_raw = str(data.get('Value') or data.get('Value_original') or data.get('value') or '').strip()
            val_clean = re.sub(r'^[n=\s]+', '', val_raw).strip()

            matched = False
            disp_name = field_desc

            if metric_type == 'production_target' and re.search(r'\btarget\b', f_lower):
                matched = True
                disp_name = 'Production target'
            elif metric_type == 'production' and re.search(r'\bproduction\b', f_lower) and not re.search(r'\btarget\b', f_lower):
                matched = True
                disp_name = 'Production'
            elif metric_type == 'dispatch' and (re.search(r'\bdispatch\b', f_lower) or re.search(r'\bofftake\b', f_lower)):
                matched = True
                disp_name = 'Dispatch'
            elif metric_type == 'achievement' and re.search(r'\bachievement\b', f_lower):
                matched = True
                disp_name = 'Achievement'
            elif metric_type in ('sales', 'pbt', 'pat', 'eps', 'dividend', 'capex', 'net_worth', 'overburden', 'grade', 'reserve', 'borehole'):
                key_match = metric_type.replace('_', ' ')
                if re.search(r'\b' + re.escape(key_match) + r'\b', f_lower):
                    matched = True
                    disp_name = field_desc

            if matched:
                num = _extract_numeric(val_clean)
                unit = 'MT'
                if 'tonne' in val_clean.lower():
                    unit = 'Tonnes'
                elif 'crore' in val_clean.lower():
                    unit = 'Crore'
                elif '%' in val_clean:
                    unit = '%'
                elif 'bcm' in val_clean.lower():
                    unit = 'Million BCM'

                doc_candidates.append({
                    'record': rec,
                    'data': data,
                    'field_display': disp_name,
                    'formatted_value': val_clean,
                    'raw_value': val_raw,
                    'numeric_value': num,
                    'unit': unit,
                    'is_doc_level': True,
                    'subsidiary': None,
                })
            continue

        # --- Type B: Tabular / Subsidiary Records ---
        sub_val = _record_subsidiary(data)

        matched_col = None
        disp_name = metric_type
        if metric_type == 'production_target' and ('target' in data or 'production_target' in data):
            matched_col = 'target' if 'target' in data else 'production_target'
            disp_name = 'Production target'
        elif metric_type == 'production' and 'production' in data:
            matched_col = 'production'
            disp_name = 'Production'
        elif metric_type == 'dispatch' and ('dispatch' in data or 'offtake' in data):
            matched_col = 'dispatch' if 'dispatch' in data else 'offtake'
            disp_name = 'Dispatch'
        elif metric_type in data:
            matched_col = metric_type
            disp_name = metric_type.replace('_', ' ').capitalize()

        if matched_col:
            val_num = _extract_numeric(data[matched_col])
            val_fmt = data.get(f'{matched_col}_original') or str(data.get(matched_col) or '')
            unit = data.get(f'{matched_col}_unit') or 'MT'
            if 'tonne' in str(val_fmt).lower():
                unit = 'Tonnes'

            sub_candidates.append({
                'record': rec,
                'data': data,
                'field_display': disp_name,
                'formatted_value': str(val_fmt).strip(),
                'numeric_value': val_num,
                'unit': unit,
                'is_doc_level': False,
                'subsidiary': sub_val,
            })

    # --- Selection Logic ---
    selected_items = []
    calc_type = agg_type or 'lookup'

    # Case 0: User specified a specific mine name (e.g. "production of Aadocm mine")
    q_lower = raw_query.lower()
    mine_match = None
    for c in sub_candidates:
        m_name = str(c['data'].get('mine') or c['data'].get('mine_name') or c['data'].get('Mine Name') or '').strip().lower()
        m_clean = re.sub(r'\(.*?\)', '', m_name).strip()
        if (m_name and len(m_name) >= 3 and m_name in q_lower) or (m_clean and len(m_clean) >= 3 and m_clean in q_lower):
            mine_match = c
            break

    if mine_match:
        selected_items = [mine_match]
        calc_type = 'lookup'

    # Case 1: User explicitly specified a subsidiary (e.g. "What was MCL production?")
    elif sub_target:
        matching_sub = [c for c in sub_candidates if str(c['subsidiary']).upper() == sub_target.upper()]
        if matching_sub:
            selected_items = [matching_sub[0]]
        else:
            return {'found': False, 'reason': f'No record found for subsidiary {sub_target}'}

    # Case 2: Document-level query (sub_target is None)
    else:
        # Prefer document-level summary row if available
        if doc_candidates:
            selected_items = [doc_candidates[0]]
        elif sub_candidates:
            if agg_type == 'sum' or 'total' in raw_query.lower():
                vals = [c['numeric_value'] for c in sub_candidates if c.get('numeric_value') is not None]
                if vals:
                    tot = sum(vals)
                    unit = sub_candidates[0]['unit']
                    fmt = f"{tot:,.0f} {unit}" if tot.is_integer() else f"{tot:,.2f} {unit}"
                    first_c_copy = dict(sub_candidates[0])
                    first_c_copy['numeric_value'] = tot
                    first_c_copy['formatted_value'] = fmt
                    first_c_copy['field_display'] = f"Total {metric_type}"
                    first_c_copy['subsidiary'] = None
                    selected_items = [first_c_copy]
                    calc_type = 'sum'
            elif agg_type == 'max':
                items_with_num = [c for c in sub_candidates if c['numeric_value'] is not None]
                if items_with_num:
                    best = max(items_with_num, key=lambda x: x['numeric_value'])
                    selected_items = [best]
                    calc_type = 'max'
            elif agg_type == 'min':
                items_with_num = [c for c in sub_candidates if c['numeric_value'] is not None]
                if items_with_num:
                    best = min(items_with_num, key=lambda x: x['numeric_value'])
                    selected_items = [best]
                    calc_type = 'min'
            elif agg_type == 'avg':
                items_with_num = [c for c in sub_candidates if c['numeric_value'] is not None]
                if items_with_num:
                    avg_val = sum(c['numeric_value'] for c in items_with_num) / len(items_with_num)
                    unit = items_with_num[0]['unit']
                    fmt = f"{avg_val:,.2f} {unit}"
                    first_c_copy = dict(items_with_num[0])
                    first_c_copy['numeric_value'] = avg_val
                    first_c_copy['formatted_value'] = fmt
                    first_c_copy['field_display'] = f"Average {metric_type}"
                    first_c_copy['subsidiary'] = None
                    selected_items = [first_c_copy]
                    calc_type = 'avg'
            else:
                # User asked document-level question without subsidiary, but document only
                # has subsidiary breakdown. Return sum across subsidiaries or state total.
                vals = [c['numeric_value'] for c in sub_candidates if c.get('numeric_value') is not None]
                if vals:
                    tot = sum(vals)
                    unit = sub_candidates[0]['unit']
                    fmt = f"{tot:,.0f} {unit}" if tot.is_integer() else f"{tot:,.2f} {unit}"
                    first_c_copy = dict(sub_candidates[0])
                    first_c_copy['numeric_value'] = tot
                    first_c_copy['formatted_value'] = fmt
                    first_c_copy['field_display'] = f"Total {metric_type}"
                    first_c_copy['subsidiary'] = None
                    selected_items = [first_c_copy]
                    calc_type = 'sum'

    if not selected_items:
        return {'found': False, 'reason': 'I could not find a sufficiently specific value for that field in the selected document.'}

    item = selected_items[0]
    rec = item['record']
    doc = rec.dataset.source_document
    prov = rec.provenance.first()

    citations = [{
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
        'field': item.get('field_display') or metric_type,
        'value': item.get('formatted_value') or item.get('numeric_value'),
        'extraction_method': prov.extraction_method if prov else 'extracted',
        'ocr_used': prov.ocr_used if prov else False,
        'source_ref': prov.source_reference if prov else (f"baseline:record:{rec.pk}" if is_baseline else f"record:{rec.pk}"),
        'is_baseline': is_baseline,
    }]

    return {
        'found': True,
        'calculation_type': calc_type,
        'metric': metric_type,
        'metric_display': item.get('field_display'),
        'subsidiary': item.get('subsidiary'),
        'mine': item['data'].get('mine') or item['data'].get('mine_name') or item['data'].get('Mine Name'),
        'year': year_target,
        'result_value': item.get('numeric_value'),
        'formatted_value': item.get('formatted_value'),
        'unit': item.get('unit', 'MT'),
        'record_count': len(selected_items),
        'records_data': [item['data']],
        'citations': citations,
    }


def retrieve_structured_data(
    user,
    entities: Dict[str, Any],
    raw_query: str = '',
    document_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Retrieve and calculate structured data strictly from user's datasets & records.
    Never hallucinates calculations or values.
    """
    if not user or not user.is_authenticated:
        return {'found': False, 'reason': 'User unauthenticated'}

    # Strict multi-tenancy: Only search user's unarchived datasets
    records_qs = StructuredRecord.objects.filter(
        dataset__source_document__uploaded_by=user,
        dataset__source_document__is_archived=False,
    ).select_related('dataset', 'dataset__source_document').prefetch_related('provenance')

    if document_id:
        records_qs = records_qs.filter(dataset__source_document_id=document_id)

    if not records_qs.exists():
        return {'found': False, 'reason': 'No structured datasets available for user.'}

    return _resolve_records_metric(records_qs, entities, raw_query, is_baseline=False)


# ---------------------------------------------------------------------------
# Baseline / Historical Reference Retrieval
# ---------------------------------------------------------------------------
# These functions are READ-ONLY access paths to documents and datasets that
# carry Document.is_reference=True.  They deliberately omit the
# uploaded_by=user ownership filter because reference/baseline data is
# globally readable by all authenticated users for comparison purposes.
#
# IMPORTANT: nothing in this module ever writes, modifies, archives,
# reclassifies, or deletes reference data.  Only SELECT queries are issued.
# ---------------------------------------------------------------------------


def retrieve_baseline_chunks(
    query: str,
    top_k: int = 5,
    min_score: float = 0.1,
) -> List[Dict[str, Any]]:
    """
    Retrieve document chunks from authorized protected baseline/reference
    documents (Document.is_reference=True).

    Access policy: readable by any authenticated user for comparison only.
    No user-ownership filter is applied — baseline documents are shared
    across the system but are strictly read-only.
    """
    try:
        top_k = max(1, min(int(top_k), 20))
    except (TypeError, ValueError):
        top_k = 5

    qs = DocumentChunk.objects.filter(
        document__is_reference=True,
        document__is_archived=False,
    ).select_related('document')

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

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
            'source_ref': f"baseline:doc:{chunk.document_id}:page:{chunk.page_number or 'N/A'}:chunk:{chunk.chunk_index}",
            'is_baseline': True,
        })

    return results


def retrieve_baseline_structured_data(
    entities: Dict[str, Any],
    raw_query: str = '',
) -> Dict[str, Any]:
    """
    Retrieve and calculate structured data from authorized protected baseline
    datasets (Document.is_reference=True).

    Mirrors retrieve_structured_data() in structure and return shape so the
    answer engine can treat both sources uniformly.

    Access policy: readable by any authenticated user for comparison only.
    STRICTLY READ-ONLY — no inserts, updates, deletes, or reclassifications.
    """
    # Scope strictly to reference/baseline documents
    records_qs = StructuredRecord.objects.filter(
        dataset__source_document__is_reference=True,
        dataset__source_document__is_archived=False,
    ).select_related('dataset', 'dataset__source_document').prefetch_related('provenance')

    if not records_qs.exists():
        return {'found': False, 'reason': 'No baseline structured datasets available.'}

    return _resolve_records_metric(records_qs, entities, raw_query, is_baseline=True)
