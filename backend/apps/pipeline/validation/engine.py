"""
Structured validation engine for extracted mining document data.
"""
import re
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

IMPORTANT_FIELDS = {
    'production', 'financial_year', 'mine', 'subsidiary', 'organization'
}

COORDINATE_PATTERN = re.compile(
    r'^[\-+]?(?:90(?:\.0+)?|[0-8]?\d(?:\.\d+)?)$'  # latitude: -90 to 90
)

LAT_RANGE = (-90.0, 90.0)
LON_RANGE = (-180.0, 180.0)


@dataclass
class ValidationFinding:
    """A single validation finding."""
    issue_type: str
    severity: str  # INFO, WARNING, ERROR
    field_name: str = ''
    original_value: str = ''
    suggested_value: str = ''
    explanation: str = ''
    confidence: float = 1.0
    row_index: Optional[int] = None


NUMERIC_PATTERN = re.compile(
    r'([+\-]?(?:\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?:[eE][+\-]?\d+)?)'
)


def parse_numeric_and_unit(raw: Any) -> tuple[Optional[float], Optional[str]]:
    """
    Extract numeric value and unit from a raw value string.
    Returns (numeric_value, unit_string) or (None, None) if not parseable.
    Handles:
      - Numbers with commas: '4,250', '1,23,456.78'
      - Units: 'Tonnes', 'MT', 'Million BCM', 'Crore', '%', etc.
      - Currency symbols & prefixes: '₹ 4,820 Crore', '$100'
      - Preserves valid numeric values without invalidating due to unit characters.
    """
    if raw is None:
        return None, None
    raw_str = str(raw).strip()
    if not raw_str:
        return None, None

    m = NUMERIC_PATTERN.search(raw_str)
    if not m:
        return None, None

    num_str = m.group(1).replace(',', '')
    try:
        num = float(num_str)
    except ValueError:
        return None, None

    prefix = raw_str[:m.start()].strip()
    suffix = raw_str[m.end():].strip()

    unit_parts = []
    if prefix:
        clean_pref = prefix.strip(' \t\r\n:=-[]()')
        if clean_pref and clean_pref not in ('n', 'n.', '-'):
            unit_parts.append(clean_pref)
    if suffix:
        clean_suff = suffix.strip(' \t\r\n:=-[]()')
        if clean_suff:
            unit_parts.append(clean_suff)

    unit = ' '.join(unit_parts) if unit_parts else (suffix or None)
    return num, unit


def extract_document_metadata(
    doc_context: Optional[Dict[str, Any]] = None,
    tables: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Extract document-level metadata (mine, financial_year, organization, location, etc.)
    from document context (raw text, document attributes) and key-value tables.
    """
    metadata = {}
    if not doc_context and not tables:
        return metadata

    raw_text = ''
    doc_meta_dict = {}
    if doc_context:
        raw_text = doc_context.get('raw_text') or ''
        doc_meta_dict = doc_context.get('metadata') or {}
        title = doc_context.get('title') or ''
        filename = doc_context.get('filename') or ''
        search_text = f'{title}\n{filename}\n{raw_text}'
    else:
        search_text = ''

    kv_data = {}
    if tables:
        for t in tables:
            headers = [h.strip().lower() for h in getattr(t, 'headers', [])]
            rows = getattr(t, 'rows', [])
            if len(headers) == 2 and any(k in headers[0] for k in ('field', 'key', 'property', 'metric', 'parameter')):
                for row in rows:
                    if len(row) >= 2 and row[0] and row[1]:
                        kv_data[str(row[0]).strip().lower()] = str(row[1]).strip()

    # 1. Financial Year
    for k in ('financial_year', 'reporting_year', 'year', 'fy'):
        if doc_meta_dict.get(k):
            metadata['financial_year'] = str(doc_meta_dict[k]).strip()
            break
    if 'financial_year' not in metadata:
        for k, v in kv_data.items():
            if any(term in k for term in ('year', 'financial year', 'reporting year', 'fy')):
                metadata['financial_year'] = v
                break
    if 'financial_year' not in metadata and search_text:
        fy_match = re.search(
            r'(?:Reporting\s+Year|Financial\s+Year|Year|FY)\s*[:\-=]?\s*(FY\s*\d{2,4}[-–/]\d{2,4}|\d{4}[-–/]\d{2,4}|\bFY\d{2,4}\b)',
            search_text,
            re.IGNORECASE
        )
        if not fy_match:
            fy_match = re.search(r'\b(?:FY\s*20\d{2}[-–/]\d{2,4}|20\d{2}[-–/]\d{2})\b', search_text, re.IGNORECASE)
        if fy_match:
            metadata['financial_year'] = fy_match.group(1).strip() if fy_match.groups() else fy_match.group(0).strip()

    # 2. Mine Name / Mine
    for k in ('mine', 'mine_name', 'name_of_mine'):
        if doc_meta_dict.get(k):
            metadata['mine'] = str(doc_meta_dict[k]).strip()
            break
    if 'mine' not in metadata:
        for k, v in kv_data.items():
            if 'mine' in k:
                metadata['mine'] = v
                break
    if 'mine' not in metadata and search_text:
        mine_match = re.search(
            r'(?:Mine\s+Name|Name\s+of\s+Mine|Mine)\s*[:\-=]\s*([^\r\n,]+)',
            search_text,
            re.IGNORECASE
        )
        if mine_match:
            metadata['mine'] = mine_match.group(1).strip()

    # 3. Organization / Subsidiary
    for k in ('organization', 'company', 'subsidiary', 'source', 'operator', 'owner'):
        if doc_meta_dict.get(k):
            metadata['organization'] = str(doc_meta_dict[k]).strip()
            break
    if 'organization' not in metadata:
        for k, v in kv_data.items():
            if any(term in k for term in ('organization', 'company', 'subsidiary', 'source', 'operator')):
                metadata['organization'] = v
                break
    if 'organization' not in metadata and search_text:
        org_match = re.search(
            r'(?:Organization|Company|Source|Operator|Owner|Corporation|Ministry)\s*[:\-=]\s*([^\r\n]+)',
            search_text,
            re.IGNORECASE
        )
        if org_match:
            metadata['organization'] = org_match.group(1).strip()
        else:
            entity_match = re.search(
                r'\b(Coal India(?: Limited)?|CIL|CMPDI|CMPDIL|MCL|NCL|SECL|ECL|CCL|WCL|BCCL|SCCL|NLC|Ministry of Coal)\b',
                search_text,
                re.IGNORECASE
            )
            if entity_match:
                metadata['organization'] = entity_match.group(0).strip()
    if 'organization' not in metadata and tables:
        for t in tables:
            for h in getattr(t, 'headers', []):
                h_low = h.strip().lower()
                if h_low in ('subsidiary', 'organization', 'company', 'psu'):
                    metadata['organization'] = h.strip()
                    break

    # 4. Location
    for k in ('location', 'place', 'district', 'state'):
        if doc_meta_dict.get(k):
            metadata['location'] = str(doc_meta_dict[k]).strip()
            break
    if 'location' not in metadata:
        for k, v in kv_data.items():
            if any(term in k for term in ('location', 'place', 'district', 'state')):
                metadata['location'] = v
                break
    if 'location' not in metadata and search_text:
        loc_match = re.search(r'Location\s*[:\-=]\s*([^\r\n]+)', search_text, re.IGNORECASE)
        if loc_match:
            metadata['location'] = loc_match.group(1).strip()

    return metadata


def validate_dataset(
    tables,  # List[ExtractedTable]
    column_map: Dict[str, Dict],
    doc_context: Optional[Dict[str, Any]] = None,
) -> List[ValidationFinding]:
    """
    Run validation rules across all extracted tables.
    Returns a list of ValidationFinding objects.
    """
    findings = []
    doc_metadata = extract_document_metadata(doc_context, tables)

    for table in tables:
        findings.extend(_validate_table(table, column_map, doc_metadata=doc_metadata))

    return findings


def _validate_table(
    table,
    column_map: Dict,
    doc_metadata: Optional[Dict] = None,
) -> List[ValidationFinding]:
    findings = []
    headers = table.headers
    rows = table.rows
    doc_metadata = doc_metadata or {}

    if not headers and not rows:
        findings.append(ValidationFinding(
            issue_type='extraction_failure',
            severity='WARNING',
            explanation=f'Table {table.source_ref} is empty — no headers or rows extracted.'
        ))
        return findings

    # Check duplicate column headers
    seen_headers = {}
    for i, h in enumerate(headers):
        if h in seen_headers:
            findings.append(ValidationFinding(
                issue_type='duplicate',
                severity='WARNING',
                field_name=h,
                original_value=h,
                explanation=f'Duplicate column "{h}" at positions {seen_headers[h]} and {i} in {table.source_ref}.',
            ))
        else:
            seen_headers[h] = i

    # Check important fields present:
    # Distinguish document-level metadata from table-level schema.
    # If the field is satisfied at document level, do not create false table-level errors.
    detected_concepts = {v.get('concept') for v in column_map.values() if v.get('concept')}
    for imp_field in IMPORTANT_FIELDS:
        if imp_field in doc_metadata:
            continue
        if imp_field not in detected_concepts:
            findings.append(ValidationFinding(
                issue_type='missing_required',
                severity='INFO',
                field_name=imp_field,
                explanation=f'Important field "{imp_field}" not detected in {table.source_ref} or document metadata.',
            ))
    
    # Per-row validation
    seen_rows = set()
    for r_idx, row in enumerate(rows):
        row_dict = dict(zip(headers, row)) if len(row) >= len(headers) else dict(zip(headers, row + [''] * (len(headers) - len(row))))
        
        # Schema mismatch — row has more cells than headers
        if len(row) > len(headers) and headers:
            findings.append(ValidationFinding(
                issue_type='schema_mismatch',
                severity='WARNING',
                explanation=f'Row {r_idx} in {table.source_ref} has {len(row)} cells but only {len(headers)} headers.',
                row_index=r_idx,
            ))
        
        # Duplicate rows
        row_sig = tuple(row)
        if row_sig in seen_rows:
            findings.append(ValidationFinding(
                issue_type='duplicate_record',
                severity='WARNING',
                explanation=f'Duplicate row at index {r_idx} in {table.source_ref}.',
                row_index=r_idx,
            ))
        seen_rows.add(row_sig)
        
        # Numeric field validation
        for col_name, cell_val in row_dict.items():
            col_info = column_map.get(col_name, {})
            concept = col_info.get('concept')
            
            if not cell_val or not cell_val.strip():
                continue
            
            if concept in ('production', 'target', 'dispatch', 'resource', 'reserve'):
                findings.extend(_validate_numeric(cell_val, col_name, concept, r_idx, table.source_ref))
            
            if concept in ('latitude', 'coordinates'):
                findings.extend(_validate_coordinate(cell_val, col_name, 'latitude', r_idx, table.source_ref))
            
            if concept == 'longitude':
                findings.extend(_validate_coordinate(cell_val, col_name, 'longitude', r_idx, table.source_ref))
    
    return findings


def _validate_numeric(value: str, field: str, concept: str, row_idx: int, source: str) -> List[ValidationFinding]:
    findings = []
    num, unit = parse_numeric_and_unit(value)
    if num is None:
        findings.append(ValidationFinding(
            issue_type='invalid_numeric',
            severity='ERROR',
            field_name=field,
            original_value=value,
            explanation=f'Cannot parse "{value}" as numeric for field "{field}" (row {row_idx} in {source}).',
            row_index=row_idx,
        ))
        return findings

    # Suspicious values
    if num < 0 and concept in ('production', 'target', 'dispatch'):
        findings.append(ValidationFinding(
            issue_type='suspicious_value',
            severity='WARNING',
            field_name=field,
            original_value=value,
            explanation=f'Negative value {num} for "{field}" (row {row_idx} in {source}) — verify source.',
            row_index=row_idx,
        ))
    return findings


def _validate_coordinate(value: str, field: str, coord_type: str, row_idx: int, source: str) -> List[ValidationFinding]:
    findings = []
    clean = value.strip().replace(',', '.')
    try:
        coord = float(clean)
    except ValueError:
        findings.append(ValidationFinding(
            issue_type='coordinate_error',
            severity='WARNING',
            field_name=field,
            original_value=value,
            explanation=f'Cannot parse "{value}" as coordinate for field "{field}" (row {row_idx} in {source}).',
            row_index=row_idx,
        ))
        return findings
    
    low, high = LAT_RANGE if coord_type == 'latitude' else LON_RANGE
    if not (low <= coord <= high):
        findings.append(ValidationFinding(
            issue_type='coordinate_error',
            severity='ERROR',
            field_name=field,
            original_value=value,
            explanation=f'{coord_type.capitalize()} {coord} out of valid range [{low}, {high}] (row {row_idx} in {source}).',
            row_index=row_idx,
        ))
    
    return findings
