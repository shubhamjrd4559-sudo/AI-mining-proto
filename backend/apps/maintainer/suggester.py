"""
apps.maintainer — Deterministic Suggestion Engine

Generates correction suggestions from StructuredRecord data.
Reuses Phase 3 normalizers wherever possible.
NEVER automatically applies suggestions — only creates MaintainerSuggestion records.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from django.contrib.auth import get_user_model

from apps.datasets.models import StructuredDataset, StructuredRecord
from apps.pipeline.schema.normalizer import (
    normalize_financial_year,
    normalize_date,
    normalize_numeric,
)
from .models import MaintainerSuggestion, SuggestionIssueType, SuggestionSource, SuggestionStatus

logger = logging.getLogger(__name__)
User = get_user_model()

# ─────────────────────────────────────────────
# Individual rule functions → (suggested, issue_type, reason, confidence) or None
# ─────────────────────────────────────────────

def _check_whitespace(value: str) -> Optional[Tuple]:
    """Detect leading/trailing/excessive internal whitespace."""
    stripped = value.strip()
    normalised = ' '.join(stripped.split())
    if normalised != value:
        return (
            normalised,
            SuggestionIssueType.WHITESPACE,
            f'Value has leading/trailing/extra whitespace: "{value}" → "{normalised}".',
            1.0,
        )
    return None


def _check_comma_number(value: str) -> Optional[Tuple]:
    """Detect comma-formatted numbers like '1,250' that should be '1250'."""
    # Only flag if it looks like a number with commas (Indian/Western grouping)
    stripped = value.strip()
    comma_num = re.match(r'^[\-+]?\d{1,3}(?:,\d{2,3})+(?:\.\d+)?$', stripped)
    if comma_num:
        suggested = stripped.replace(',', '')
        return (
            suggested,
            SuggestionIssueType.COMMA_NUMBER,
            f'Comma-formatted number "{stripped}" → "{suggested}" (removed grouping commas).',
            0.95,
        )
    return None


def _check_percentage(value: str) -> Optional[Tuple]:
    """Normalise percentage representations."""
    stripped = value.strip()
    # e.g. '85%' is fine; '85 %' or '85percent' → '85%'
    m = re.match(r'^([\-+]?\d+(?:\.\d+)?)\s*(?:percent|pct)$', stripped, re.IGNORECASE)
    if m:
        suggested = f'{m.group(1)}%'
        if suggested != stripped:
            return (
                suggested,
                SuggestionIssueType.PERCENTAGE,
                f'Non-standard percentage "{stripped}" → "{suggested}".',
                0.9,
            )
    # Normalize '85 %' → '85%'
    m2 = re.match(r'^([\-+]?\d+(?:\.\d+)?)\s+%$', stripped)
    if m2:
        suggested = f'{m2.group(1)}%'
        return (
            suggested,
            SuggestionIssueType.PERCENTAGE,
            f'Percentage with extra space "{stripped}" → "{suggested}".',
            1.0,
        )
    return None


def _check_financial_year(value: str) -> Optional[Tuple]:
    """Normalise financial year strings."""
    stripped = value.strip()
    norm = normalize_financial_year(stripped)
    if norm and norm != stripped:
        return (
            norm,
            SuggestionIssueType.FINANCIAL_YEAR,
            f'Financial year "{stripped}" → standardised "{norm}".',
            0.95,
        )
    return None


def _check_date(value: str) -> Optional[Tuple]:
    """Normalise date strings to ISO 8601."""
    stripped = value.strip()
    norm = normalize_date(stripped)
    if norm and norm != stripped:
        return (
            norm,
            SuggestionIssueType.DATE_FORMAT,
            f'Date "{stripped}" → ISO 8601 "{norm}".',
            0.9,
        )
    return None


# Safe unit normalisation patterns  (source → normalised display)
_UNIT_FIXES = [
    (re.compile(r'\bmt\b', re.IGNORECASE), 'MT'),
    (re.compile(r'\bkt\b', re.IGNORECASE), 'KT'),
    (re.compile(r'\bkm\b', re.IGNORECASE), 'km'),
]


def _check_unit(value: str) -> Optional[Tuple]:
    """Normalise obvious unit casing/formatting."""
    stripped = value.strip()
    result = stripped
    for pattern, replacement in _UNIT_FIXES:
        result = pattern.sub(replacement, result)
    if result != stripped:
        return (
            result,
            SuggestionIssueType.UNIT_NORMALIZATION,
            f'Unit notation "{stripped}" → standardised "{result}".',
            0.85,
        )
    return None


def _check_capitalization(value: str, field_name: str) -> Optional[Tuple]:
    """Flag ALL-CAPS values for obvious name fields that should be title case."""
    stripped = value.strip()
    # Only suggest for name-like fields and only if fully upper-case (2+ words or 4+ chars)
    name_fields = ('mine', 'subsidiary', 'organization', 'district', 'state', 'coalfield')
    is_name_field = any(nf in field_name.lower() for nf in name_fields)
    if is_name_field and len(stripped) >= 4 and stripped.isupper() and ' ' in stripped:
        suggested = stripped.title()
        return (
            suggested,
            SuggestionIssueType.CAPITALIZATION,
            f'ALL-CAPS name "{stripped}" → title case "{suggested}".',
            0.75,
        )
    return None


def _check_numeric_format(value: str, field_name: str) -> Optional[Tuple]:
    """Detect non-standard numeric formatting such as '+1250' or '.50'."""
    stripped = value.strip()
    if stripped.startswith('+') and re.match(r'^\+\d+(?:\.\d+)?$', stripped):
        suggested = stripped[1:]
        return (
            suggested,
            SuggestionIssueType.NUMERIC_FORMAT,
            f'Redundant leading plus sign in "{stripped}" → "{suggested}".',
            0.95,
        )
    if re.match(r'^\.\d+$', stripped):
        suggested = f'0{stripped}'
        return (
            suggested,
            SuggestionIssueType.NUMERIC_FORMAT,
            f'Missing leading zero in decimal "{stripped}" → "{suggested}".',
            0.95,
        )
    return None


# ─────────────────────────────────────────────
# Main suggester
# ─────────────────────────────────────────────

def _suggest_for_value(
    raw_value: Any,
    field_name: str,
) -> List[Tuple]:
    """Run all deterministic rules against a single cell value.
    Returns list of (suggested, issue_type, reason, confidence).
    """
    if raw_value is None:
        return []
    value_str = str(raw_value)

    suggestions = []

    # Rules applied in order; each is independent (a value may trigger multiple rules)
    checkers = [
        lambda v: _check_whitespace(v),
        lambda v: _check_comma_number(v),
        lambda v: _check_numeric_format(v, field_name),
        lambda v: _check_percentage(v),
        lambda v: _check_financial_year(v),
        lambda v: _check_date(v),
        lambda v: _check_unit(v),
        lambda v: _check_capitalization(v, field_name),
    ]
    for checker in checkers:
        result = checker(value_str)
        if result:
            suggestions.append(result)

    return suggestions


def generate_suggestions_for_dataset(
    dataset: StructuredDataset,
    user: Optional[User] = None,
    ai_enabled: bool = False,
) -> Dict[str, int]:
    """
    Main entry point: generate deterministic suggestions for all records in a dataset.
    Optionally call AI fallback for contextual suggestions.
    Returns summary dict.

    NEVER auto-applies any suggestion.
    """
    created_count = 0
    skipped_count = 0

    # Remove existing PENDING suggestions to avoid duplication on re-run
    deleted = MaintainerSuggestion.objects.filter(
        dataset=dataset,
        status=SuggestionStatus.PENDING,
        suggestion_source=SuggestionSource.DETERMINISTIC,
    ).delete()
    logger.info('Cleared %s old pending deterministic suggestions for dataset %d', deleted, dataset.pk)

    records = dataset.records.all().order_by('row_index')
    doc = dataset.source_document

    for record in records:
        row = record.data_json or {}

        for field_name, raw_value in row.items():
            # Skip internal provenance suffixes
            if field_name.endswith('_original') or field_name.endswith('_unit') or field_name.endswith('_normalized_unit'):
                continue

            cell_suggestions = _suggest_for_value(raw_value, field_name)

            # Fetch first provenance for this record (if available)
            prov = record.provenance.first()

            for (suggested_val, issue_type, reason, confidence) in cell_suggestions:
                # Skip if suggested == original (no change)
                if str(raw_value) == suggested_val:
                    skipped_count += 1
                    continue

                MaintainerSuggestion.objects.create(
                    dataset=dataset,
                    record=record,
                    document=doc,
                    field_name=field_name,
                    original_value=str(raw_value),
                    suggested_value=suggested_val,
                    issue_type=issue_type,
                    reason=reason,
                    confidence=confidence,
                    suggestion_source=SuggestionSource.DETERMINISTIC,
                    provenance=prov,
                    status=SuggestionStatus.PENDING,
                    created_by=user,
                )
                created_count += 1

    # Optional AI fallback (bounded — not per-cell)
    ai_created = 0
    if ai_enabled:
        try:
            from .ai_maintainer import generate_ai_suggestions
            ai_created = generate_ai_suggestions(dataset, user)
        except ImportError:
            logger.debug('AI maintainer module not available.')
        except Exception as exc:
            logger.warning('AI suggestion generation failed (skipped): %s', exc)

    logger.info(
        'Dataset %d: %d deterministic suggestions created, %d skipped, %d AI suggestions.',
        dataset.pk, created_count, skipped_count, ai_created
    )
    return {
        'created': created_count,
        'skipped': skipped_count,
        'ai_created': ai_created,
        'total': created_count + ai_created,
    }
