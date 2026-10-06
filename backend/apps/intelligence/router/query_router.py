"""
Query routing module for CMPDI Mining Intelligence.

Routes user queries into:
  1. STRUCTURED — Deterministic DB queries and calculations (e.g. production figures, subsidiary comparisons)
  2. DOCUMENT   — Document chunk semantic/keyword retrieval (e.g. geological exploration services, guidelines)
  3. HYBRID     — Combination of structured metric calculation and narrative document context

Comparison intent:
  Queries that explicitly ask to compare current data against historical/baseline data are flagged
  with entities['comparison_intent'] = True.  The answer engine uses this flag to fetch both the
  user's current document evidence AND authorized protected baseline/reference data, then returns a
  deterministic side-by-side answer with dual citations.
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
    'production_target': [
        'production target', 'target production', 'planned production', 'production goal', 'target'
    ],
    'achievement': [
        'achievement percentage', 'achievement percent', 'target achievement', 'achievement'
    ],
    'dispatch': [
        'total dispatch', 'total offtake', 'dispatch', 'dispatched', 'offtake', 'supply'
    ],
    'sales': [
        'sales', 'revenue', 'turnover'
    ],
    'pbt': [
        'pbt', 'profit before tax'
    ],
    'pat': [
        'pat', 'profit after tax'
    ],
    'eps': [
        'eps', 'earning per share', 'earnings per share'
    ],
    'dividend': [
        'dividend'
    ],
    'capex': [
        'capex', 'capital expenditure'
    ],
    'net_worth': [
        'net worth', 'networth'
    ],
    'overburden': [
        'overburden removal', 'overburden', 'ob removal', 'stripping'
    ],
    'production': [
        'total production', 'production', 'produced', 'output', 'extracted', 'mining output', 'how much was produced'
    ],
    'reserve': [
        'reserve', 'reserves', 'resources', 'geological reserve'
    ],
    'grade': [
        'coal grade', 'grade', 'gcv', 'calorific', 'ash content'
    ],
    'borehole': [
        'borehole', 'drilling', 'meterage', 'seam'
    ],
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

# Patterns that signal the user explicitly wants to compare current data against
# historical / baseline / reference data.
COMPARISON_INTENT_PATTERNS = [
    r'\bcompar\w*\b',               # compare, comparing, comparison
    r'\bvs\b',
    r'\bversus\b',
    r'\bagainst\b',
    r'\bdifference\b',
    r'\bchange\b',
    r'\byear.on.year\b',
    r'\byoy\b',
    r'\bgrowth\b',
    r'\bimprovement\b',
    r'\bwhat\s+is\s+new\b',
    r'\bhow\s+much\s+(?:did|has)\s+.*(?:increase|decrease|grow|change)\b',
    r'\bpichl\w*\b',
    r'\bprevious\s+record\w*\b',
    r'\bloaded\s+record\w*\b',
    r'\bmatch\s+kiya\b',
    r'\bkitna\s+(?:kam|jyada|zyada)\b',
    r'\bkam\s+hai\b',
    r'\bjyada\s+hai\b',
]

# Patterns that signal the user explicitly asks for authorized organization / historical /
# baseline reference data without comparison against current upload.
ORGANIZATION_INTENT_PATTERNS = [
    r'\borganization\b',
    r'\bhistor\w*\b',
    r'\bbaseline\b',
    r'\breference\s+data\b',
    r'\bpast\s+report\b',
    r'\bpast\s+data\b',
    r'\bprevious\s+period\b',
    r'\bprevious\s+year\b',
    r'\blast\s+year\b',
    r'\bpichla\s+record\b',
    r'\bpichle\s+record\b',
    r'\bsystem\s+me\s+loaded\b',
]

DOCUMENT_FIELDS = {
    'mine_name': {
        'display': 'Mine Name',
        'query_patterns': [r'\bmine\s+name\b', r'\bname\s+of\s+(?:the\s+)?mine\b', r'\bmine\'s\s+name\b', r'\bwhich\s+mine\b'],
    },
    'location': {
        'display': 'Location',
        'query_patterns': [r'\blocation\b', r'\bwhere\s+(?:is|was)\s+(?:the\s+)?(?:mine|it)\s+located\b', r'\blocated\b', r'\bplace\b', r'\bdistrict\b', r'\bstate\b'],
    },
    'mine_type': {
        'display': 'Mine Type',
        'query_patterns': [r'\bmine\s+type\b', r'\btype\s+of\s+(?:the\s+)?mine\b'],
    },
    'production_target': {
        'display': 'Production Target',
        'query_patterns': [r'\bproduction\s+target\b', r'\btarget\s+production\b', r'\btarget\b', r'\bplanned\s+production\b'],
    },
    'production': {
        'display': 'Production',
        'query_patterns': [r'\bproduction\b', r'\bproduced\b', r'\boutput\b', r'\bhow\s+much\s+was\s+produced\b', r'\bcoal\s+production\b'],
    },
    'dispatch': {
        'display': 'Dispatch',
        'query_patterns': [r'\bdispatch\b', r'\bofftake\b', r'\bsupply\b'],
    },
    'achievement': {
        'display': 'Achievement',
        'query_patterns': [r'\bachievement\b', r'\btarget\s+achievement\b'],
    },
    'coal_grade': {
        'display': 'Coal Grade',
        'query_patterns': [r'\bcoal\s+grade\b', r'\bgrade\s+of\s+coal\b', r'\bgrade\b', r'\bgcv\b', r'\bcalorific\b'],
    },
    'year': {
        'display': 'Year',
        'query_patterns': [r'\byear\b', r'\breporting\s+year\b', r'\bfinancial\s+year\b', r'\bfy\b', r'\bperiod\b'],
    },
    'overburden': {
        'display': 'Overburden Removal',
        'query_patterns': [r'\boverburden\s+removal\b', r'\boverburden\b', r'\bob\s+removal\b', r'\bstripping\b'],
    },
    'sales': {
        'display': 'Sales',
        'query_patterns': [r'\bsales\b', r'\brevenue\b', r'\bturnover\b', r'\bnet\s+sales\b'],
    },
    'pbt': {
        'display': 'PBT',
        'query_patterns': [r'\bpbt\b', r'\bprofit\s+before\s+tax\b'],
    },
    'pat': {
        'display': 'PAT',
        'query_patterns': [r'\bpat\b', r'\bprofit\s+after\s+tax\b'],
    },
    'capex': {
        'display': 'Capex',
        'query_patterns': [r'\bcapex\b', r'\bcapital\s+expenditure\b'],
    },
    'net_worth': {
        'display': 'Net Worth',
        'query_patterns': [r'\bnet\s*worth\b', r'\bnetworth\b'],
    },
    'eps': {
        'display': 'EPS',
        'query_patterns': [r'\beps\b', r'\bearnings?\s+per\s+share\b'],
    },
    'dividend': {
        'display': 'Dividend',
        'query_patterns': [r'\bdividends?\b'],
    },
    'reserve': {
        'display': 'Reserve',
        'query_patterns': [r'\breserves?\b', r'\bgeological\s+reserve\b', r'\bresources\b'],
    },
    'employee_count': {
        'display': 'Employee Count',
        'query_patterns': [r'\bemployee\s+count\b', r'\bnumber\s+of\s+employees\b', r'\bemployees?\b', r'\bworkforce\b', r'\bmanpower\b', r'\bheadcount\b'],
    },
}

ALL_MINING_PATTERNS = [
    r'\ball(?:\s+available)?\s+mining\s+details\b',
    r'\ball(?:\s+available)?\s+details\b',
]

FY_REGEX = re.compile(r'\b(?:fy\s*)?(20\d{2})[-–/](\d{2,4})\b|\b(20\d{2})\b', re.IGNORECASE)


def extract_entities(query: str) -> Dict[str, Any]:
    """Extract known mining entities, metrics, parameters, and requested fields from query."""
    q_lower = query.lower()
    entities: Dict[str, Any] = {
        'subsidiary': None,
        'metric': None,
        'metrics': [],
        'aggregation': None,
        'year': None,
        'comparison_intent': False,
        'organization_intent': False,
        'requested_fields': [],
        'is_multi_field': False,
    }

    # Match subsidiary
    for sub_code, aliases in SUBSIDIARIES.items():
        if any(re.search(r'\b' + re.escape(alias) + r'\b', q_lower) for alias in aliases):
            entities['subsidiary'] = sub_code
            break

    # Match all metrics (preserve first in entities['metric'] for backwards compatibility)
    matched_metrics = []
    for metric, terms in METRIC_TERMS.items():
        if any(re.search(r'\b' + re.escape(t) + r'\b', q_lower) for t in terms):
            matched_metrics.append(metric)
    entities['metrics'] = matched_metrics
    if matched_metrics:
        entities['metric'] = matched_metrics[0]

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

    # Detect explicit comparison intent
    has_comparison = any(re.search(p, q_lower) for p in COMPARISON_INTENT_PATTERNS)
    has_organization = any(re.search(p, q_lower) for p in ORGANIZATION_INTENT_PATTERNS)

    entities['comparison_intent'] = has_comparison
    # Organization intent is active only when asking about baseline/organization data WITHOUT comparison
    entities['organization_intent'] = has_organization and not has_comparison

    # Extract all requested fields in query order
    if any(re.search(p, q_lower) for p in ALL_MINING_PATTERNS):
        entities['requested_fields'] = [
            'mine_name', 'location', 'mine_type', 'production', 'production_target',
            'dispatch', 'achievement', 'coal_grade', 'year', 'overburden'
        ]
    else:
        matches = []
        for field_id, meta in DOCUMENT_FIELDS.items():
            for p in meta['query_patterns']:
                m = re.search(p, q_lower)
                if m:
                    if field_id == 'production':
                        target_spans = [tm.span() for tm in re.finditer(r'\b(?:production\s+target|target\s+production)\b', q_lower)]
                        occ_spans = [om.span() for om in re.finditer(r'\bproduction\b', q_lower)]
                        outside = [s for s in occ_spans if not any(ts[0] <= s[0] and s[1] <= ts[1] for ts in target_spans)]
                        if not outside:
                            continue
                        m_start = outside[0][0]
                    else:
                        m_start = m.start()
                    matches.append((m_start, field_id))
                    break
        matches.sort(key=lambda x: x[0])
        seen = set()
        req_fields = []
        for _, f in matches:
            if f not in seen:
                seen.add(f)
                req_fields.append(f)
        entities['requested_fields'] = req_fields

    entities['is_multi_field'] = len(entities['requested_fields']) >= 2

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

    # Multi-field query classification
    if entities.get('is_multi_field'):
        req_fields = entities.get('requested_fields', [])
        has_descriptive = any(f in {'mine_name', 'location', 'mine_type', 'reserve'} for f in req_fields)
        has_struct = any(f not in {'mine_name', 'location', 'mine_type', 'reserve'} for f in req_fields)
        if has_descriptive and has_struct:
            return {
                'query_type': 'HYBRID',
                'entities': entities,
                'reason': 'Multi-field query requesting both structured metrics and document descriptive fields.',
            }
        elif has_struct:
            return {
                'query_type': 'STRUCTURED',
                'entities': entities,
                'reason': 'Multi-field query requesting structured dataset metrics.',
            }
        else:
            return {
                'query_type': 'DOCUMENT',
                'entities': entities,
                'reason': 'Multi-field query requesting document descriptive text.',
            }

    # Narrative / Document context markers
    has_narrative_context = any(re.search(p, q_lower) for p in DOCUMENT_NARRATIVE_PATTERNS)

    # Structured markers
    has_metric = bool(entities['metric'])
    has_sub = bool(entities['subsidiary'])
    has_agg = bool(entities['aggregation'])
    has_year = bool(entities['year'])

    is_numerical_or_calc = (
        has_metric or
        (has_sub and (has_year or has_agg)) or
        bool(re.search(r'\b(which subsidiary|how much|total production|highest production)\b', q_lower))
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
