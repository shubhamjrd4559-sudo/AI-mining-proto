"""
Dynamic schema/field detector for mining and geological documents.
Maps raw column names to normalized conceptual field names using keyword matching.
"""
import re
from typing import Dict, Optional

# Conceptual field name → list of keyword patterns (case-insensitive)
FIELD_PATTERNS = {
    'organization':      [r'organ', r'company', r'entity', r'authority'],
    'subsidiary':        [r'subsidiar', r'coal company', r'ccl', r'bccl', r'ecl', r'ncl', r'wecl', r'secl', r'mcl', r'cil'],
    'mine':              [r'\bmine\b', r'colliery', r'opencast', r'oc\b', r'pit\b'],
    'coalfield':         [r'coalfield', r'coal field'],
    'block':             [r'\bblock\b', r'lease block'],
    'project':           [r'project', r'scheme'],
    'state':             [r'\bstate\b', r'province'],
    'district':          [r'district', r'tehsil'],
    'financial_year':    [r'fin.*year', r'fy\b', r'financial year', r'fiscal'],
    'reporting_period':  [r'report.*period', r'period', r'quarter', r'month', r'year'],
    'production':        [r'produc', r'\bprod\.?\b', r'output'],
    'target':            [r'target', r'plan', r'budget'],
    'dispatch':          [r'dispatch', r'despatch', r'offtake', r'supply', r'sales'],
    'grade':             [r'\bgrade\b', r'quality', r'ash\b', r'gcv', r'grc'],
    'seam':              [r'\bseam\b'],
    'seam_thickness':    [r'seam.*thick', r'thickness'],
    'borehole':          [r'borehole', r'bore hole', r'bh\b', r'drill'],
    'borehole_depth':    [r'depth', r'bore.*depth'],
    'exploration':       [r'explor'],
    'resource':          [r'resource', r'geological reserve'],
    'reserve':           [r'\breserve\b', r'minable', r'proved'],
    'latitude':          [r'lat\b', r'latitude'],
    'longitude':         [r'lon\b', r'long\b', r'longitude'],
    'coordinates':       [r'coord', r'location', r'easting', r'northing'],
    'survey':            [r'survey'],
    'seismic':           [r'seismic', r'geophysic'],
    'unit':              [r'\bunit\b', r'uom', r'measure'],
    'remarks':           [r'remark', r'note', r'comment'],
}


def detect_field(column_name: str) -> Optional[str]:
    """Map a single raw column name to a normalized mining concept field."""
    normalized = column_name.lower().strip()
    for concept, patterns in FIELD_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, normalized):
                return concept
    return None  # unknown field — keep raw name


def map_columns(headers: list[str]) -> Dict[str, Dict]:
    """
    Map a list of raw column headers to normalized concept fields.
    
    Returns: {raw_header: {'concept': str|None, 'confidence': float}}
    """
    result = {}
    for header in headers:
        concept = detect_field(header)
        result[header] = {
            'concept': concept,
            'confidence': 0.85 if concept else 0.0,
            'raw': header,
        }
    return result
