"""
Value and unit normalization for mining/geological document data.
Always preserves original_value alongside normalized_value.
"""
import re
import logging
from typing import Any, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Unit conversion table: (source_unit_pattern, base_unit, multiplier_to_base)
UNIT_TABLE = [
    (r'\bmt\b|million ?tonnes?', 'MT', 1.0),
    (r'\bkt\b|000 ?t|thousand ?tonnes?', 'MT', 0.001),
    (r'\btonnes?\b|\bt\b', 'MT', 0.000001),
    (r'\bkg\b', 'MT', 0.000000001),
    (r'\bkm\b', 'km', 1.0),
    (r'\bm\b', 'm', 1.0),
    (r'%|percent', '%', 1.0),
]

FY_PATTERN = re.compile(
    r'(?:fy|f\.y\.|financial year)?\s*'
    r'(\d{2,4})[\-/](\d{2,4})',
    re.IGNORECASE
)

NUMERIC_PATTERN = re.compile(r'[\-+]?[\d,\.]+(?:[eE][\-+]?\d+)?')


def normalize_numeric(raw: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Extract numeric value and unit from a raw string.
    Returns (numeric_value, unit_string) or (None, None) if not parseable.
    Never performs unsafe conversion.
    """
    if not raw or not raw.strip():
        return None, None
    
    clean = raw.strip()
    
    # Find numeric part
    m = NUMERIC_PATTERN.search(clean)
    if not m:
        return None, None
    
    num_str = m.group(0).replace(',', '')
    try:
        value = float(num_str)
    except ValueError:
        return None, None
    
    # Find unit part (everything after numeric)
    remainder = clean[m.end():].strip()
    unit = remainder if remainder else None
    
    return value, unit


def normalize_financial_year(raw: str) -> Optional[str]:
    """Normalize financial year to standard 'YYYY-YY' format."""
    if not raw:
        return None
    m = FY_PATTERN.search(raw.strip())
    if not m:
        return None
    start, end = m.group(1), m.group(2)
    if len(start) == 2:
        start = '20' + start
    if len(end) == 2:
        end = end
    return f'{start}-{end[-2:]}'


def normalize_date(raw: str) -> Optional[str]:
    """Attempt to parse and normalize date strings to ISO 8601."""
    if not raw or not raw.strip():
        return None
    formats = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%m/%d/%Y', '%d %b %Y', '%B %Y', '%b %Y']
    for fmt in formats:
        try:
            return datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def normalize_value(raw: Any, concept: Optional[str] = None) -> Dict[str, Any]:
    """
    Normalize a raw value, preserving the original.
    Returns {'original_value': ..., 'normalized_value': ..., 'unit': ..., 'normalized_unit': ...}
    """
    raw_str = str(raw).strip() if raw is not None else ''
    result = {'original_value': raw_str, 'normalized_value': None, 'unit': None, 'normalized_unit': None}
    
    if not raw_str:
        return result
    
    if concept == 'financial_year':
        norm = normalize_financial_year(raw_str)
        result['normalized_value'] = norm or raw_str
        return result
    
    if concept in ('reporting_period',):
        # Try FY first, then date
        norm = normalize_financial_year(raw_str) or normalize_date(raw_str)
        result['normalized_value'] = norm or raw_str
        return result
    
    # Try numeric extraction for production/target/dispatch/etc.
    if concept in ('production', 'target', 'dispatch', 'resource', 'reserve',
                   'seam_thickness', 'borehole_depth'):
        val, unit = normalize_numeric(raw_str)
        if val is not None:
            result['normalized_value'] = val
            result['unit'] = unit
            # Identify and store normalized unit where clear
            if unit:
                for pattern, base_unit, _ in UNIT_TABLE:
                    if re.search(pattern, unit, re.IGNORECASE):
                        result['normalized_unit'] = base_unit
                        break
        return result
    
    # Default: strip whitespace
    result['normalized_value'] = ' '.join(raw_str.split())
    return result


def normalize_row(row_dict: Dict[str, Any], column_map: Dict[str, Dict]) -> Dict[str, Any]:
    """
    Normalize all values in a row according to detected column concepts.
    Returns a new dict with normalized values; originals preserved with _original suffix.
    """
    normalized = {}
    for raw_col, raw_val in row_dict.items():
        info = column_map.get(raw_col, {})
        concept = info.get('concept')
        norm_result = normalize_value(raw_val, concept=concept)
        
        # Use concept name as key if available, else raw column
        key = concept or raw_col
        normalized[key] = norm_result['normalized_value'] if norm_result['normalized_value'] is not None else raw_val
        normalized[f'{key}_original'] = norm_result['original_value']
        if norm_result.get('unit'):
            normalized[f'{key}_unit'] = norm_result['unit']
        if norm_result.get('normalized_unit'):
            normalized[f'{key}_normalized_unit'] = norm_result['normalized_unit']
    
    return normalized
