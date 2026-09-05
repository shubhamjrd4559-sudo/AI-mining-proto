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


def validate_dataset(
    tables,  # List[ExtractedTable]
    column_map: Dict[str, Dict],
) -> List[ValidationFinding]:
    """
    Run validation rules across all extracted tables.
    Returns a list of ValidationFinding objects.
    """
    findings = []
    
    for table in tables:
        findings.extend(_validate_table(table, column_map))
    
    return findings


def _validate_table(table, column_map: Dict) -> List[ValidationFinding]:
    findings = []
    headers = table.headers
    rows = table.rows
    
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
    
    # Check important fields present
    detected_concepts = {v.get('concept') for v in column_map.values() if v.get('concept')}
    for imp_field in IMPORTANT_FIELDS:
        if imp_field not in detected_concepts:
            findings.append(ValidationFinding(
                issue_type='missing_required',
                severity='INFO',
                field_name=imp_field,
                explanation=f'Important field "{imp_field}" not detected in {table.source_ref}.',
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
    # Strip units and try to parse
    clean = re.sub(r'[^\d.,\-+eE]', '', value.replace(',', ''))
    if not clean:
        # Non-empty original value has no numeric content at all — flag it
        findings.append(ValidationFinding(
            issue_type='invalid_numeric',
            severity='ERROR',
            field_name=field,
            original_value=value,
            explanation=(
                f'Value "{value}" for field "{field}" contains no numeric content '
                f'(row {row_idx} in {source}).'
            ),
            row_index=row_idx,
        ))
        return findings
    try:
        num = float(clean)
    except ValueError:
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
