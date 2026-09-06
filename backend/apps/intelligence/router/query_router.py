"""
Query routing module for CMPDI Mining Intelligence.

Routes user queries into:
  1. STRUCTURED — Deterministic DB queries and calculations (e.g. production figures, subsidiary comparisons)
  2. DOCUMENT   — Document chunk semantic/keyword retrieval (e.g. geological exploration services, guidelines)
  3. HYBRID     — Combination of structured metric calculation and narrative document context
"""

import re
from typing import Dict, Any, Optional

SUBSIDIARIES = {
    'MCL': ['mcl', 'mahanadi coalfields', 'mahanadi'],
    'ECL': ['ecl', 'eastern coalfields'],
    'BCCL': ['bccl', 'bharat coking coal'],
    'CCL': ['ccl', 'central coalfields'],
    'WCL': ['wcl', 'western coalfields'],
    'SECL': ['secl', 'south eastern coalfields'],
    'NCL': ['ncl', 'northern coalfields'],
    'CMPDI': ['cmpdi', 'central mine planning'],
    'CIL': ['cil', 'coal india'],
    'NEC': ['nec', 'north eastern coalfields'],
}

AGGREGATION_TERMS = {
    'max': ['highest', 'maximum', 'max', 'most', 'top', 'peak', 'greatest'],
    'min': ['lowest', 'minimum', 'min', 'least', 'bottom', 'smallest'],
    'sum': ['total', 'sum', 'overall', 'aggregate', 'combined'],
    'avg': ['average', 'mean', 'avg'],
}

METRIC_TERMS = {
    'production': ['production', 'produced', 'output', 'extracted', 'mining output'],
    'dispatch': ['dispatch', 'dispatched', 'offtake', 'supply'],
    'reserve': ['reserve', 'reserves', 'resources', 'geological reserve'],
    'overburden': ['overburden', 'ob removal', 'stripping'],
    'grade': ['grade', 'gcv', 'calorific', 'ash content'],
    'borehole': ['borehole', 'drilling', 'meterage', 'seam'],
}

DOCUMENT_NARRATIVE_PATTERNS = [
    r'\baccording to\b',
    r'\bas per\b',
    r'\breport\b',
    r'\bannual report\b',
    r'\bexplain\b',
    r'\bdescribe\b',
    r'\boverview\b',
    r'\bservices?\b',
    r'\bactivities\b',
    r'\bwhat does .* say\b',
    r'\bwhy\b',
    r'\bdetails\b',
    r'\bmethodology\b',
    r'\bfindings\b',
    r'\bpolicy\b',
    r'\bguidelines?\b',
]

FY_REGEX = re.compile(r'\b(?:fy\s*)?(20\d{2})[-–/](\d{2,4})\b|\b(20\d{2})\b', re.IGNORECASE)


def extract_entities(query: str) -> Dict[str, Any]:
    """Extract known mining entities, metrics, and parameters from query."""
    q_lower = query.lower()
    entities: Dict[str, Any] = {
        'subsidiary': None,
        'metric': None,
        'aggregation': None,
        'year': None,
    }

    # Match subsidiary
    for sub_code, aliases in SUBSIDIARIES.items():
        if any(re.search(r'\b' + re.escape(alias) + r'\b', q_lower) for alias in aliases):
            entities['subsidiary'] = sub_code
            break

    # Match metric
    for metric, terms in METRIC_TERMS.items():
        if any(re.search(r'\b' + re.escape(t) + r'\b', q_lower) for t in terms):
            entities['metric'] = metric
            break

    # Match aggregation
    for agg, terms in AGGREGATION_TERMS.items():
        if any(re.search(r'\b' + re.escape(t) + r'\b', q_lower) for t in terms):
            entities['aggregation'] = agg
            break

    # Match financial year or year
    match = FY_REGEX.search(q_lower)
    if match:
        if match.group(1) and match.group(2):
            entities['year'] = f"{match.group(1)}-{match.group(2)}"
        elif match.group(3):
            entities['year'] = match.group(3)

    return entities


def classify_query(query: str) -> Dict[str, Any]:
    """
    Classify query into STRUCTURED, DOCUMENT, or HYBRID.
    Returns:
      {
        'query_type': 'STRUCTURED' | 'DOCUMENT' | 'HYBRID',
        'entities': {...},
        'reason': '...'
      }
    """
    clean_q = query.strip()
    q_lower = clean_q.lower()
    entities = extract_entities(clean_q)

    # Narrative / Document context markers
    has_narrative_context = any(re.search(p, q_lower) for p in DOCUMENT_NARRATIVE_PATTERNS)

    # Structured markers
    has_metric = bool(entities['metric'])
    has_sub = bool(entities['subsidiary'])
    has_agg = bool(entities['aggregation'])
    has_year = bool(entities['year'])

    is_numerical_or_calc = (
        (has_sub and (has_metric or has_year)) or
        (has_agg and has_metric) or
        (has_metric and has_year) or
        (has_agg and has_sub) or
        re.search(r'\b(what was|which subsidiary|how much|total production|highest production)\b', q_lower)
    )

    # HYBRID: Has specific structured entity/metric AND explicit document narrative cue
    if is_numerical_or_calc and has_narrative_context:
        return {
            'query_type': 'HYBRID',
            'entities': entities,
            'reason': 'Query requests structured metrics alongside document context/narrative.',
        }

    # STRUCTURED: Clear numerical query, aggregation, or subsidiary data lookup
    if is_numerical_or_calc and not has_narrative_context:
        return {
            'query_type': 'STRUCTURED',
            'entities': entities,
            'reason': 'Query asks for structured metrics, comparisons, or deterministic figures.',
        }

    # DOCUMENT: Qualitative, explanatory, or document-level questions
    return {
        'query_type': 'DOCUMENT',
        'entities': entities,
        'reason': 'Query asks for qualitative description, geological details, or document text.',
    }
