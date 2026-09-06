"""
apps.maintainer — Optional AI-assisted suggestion fallback.

This module is OPTIONAL. If AI API keys are unavailable, it raises ImportError-like
conditions or returns 0 gracefully. The deterministic pipeline always works without it.

Environment variables required:
  OPENAI_API_KEY  — OpenAI GPT key, OR
  GEMINI_API_KEY  — Google Gemini key

NEVER exposes API keys in frontend code or responses.
NEVER calls AI per-cell. Groups context and makes bounded calls per dataset/table.
"""

import os
import json
import logging
from typing import Optional
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


def _get_ai_client():
    """Return an AI client if configured, else raise RuntimeError."""
    openai_key = os.environ.get('OPENAI_API_KEY', '').strip()
    if openai_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openai_key)
            return 'openai', client
        except ImportError:
            raise RuntimeError('openai package not installed. Install with: pip install openai')

    gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            return 'gemini', genai
        except ImportError:
            raise RuntimeError('google-generativeai package not installed.')

    raise RuntimeError(
        'No AI API key configured. '
        'Set OPENAI_API_KEY or GEMINI_API_KEY in environment to enable AI suggestions.'
    )


def _build_context_prompt(dataset_name: str, columns: list, sample_rows: list) -> str:
    """Build a bounded context prompt for column-level AI insight."""
    sample_str = json.dumps(sample_rows[:5], indent=2)
    col_str = ', '.join(columns[:20])
    return (
        f"You are a data quality assistant for Indian coal mining datasets.\n"
        f"Dataset: {dataset_name}\n"
        f"Columns: {col_str}\n"
        f"Sample rows (up to 5):\n{sample_str}\n\n"
        "Identify any data quality issues in these columns/values that deterministic rules "
        "might miss. Focus on: ambiguous column meanings, contextual name normalisation, "
        "suspicious values needing explanation. Respond as a JSON array of objects with "
        "keys: field_name, original_value, suggested_value, reason, confidence (0-1), "
        "issue_type (one of: contextual, suspicious_value, capitalization). "
        "Return empty array [] if no issues found. Be conservative."
    )


def generate_ai_suggestions(dataset, user=None) -> int:
    """
    Generate AI-assisted suggestions for a dataset.
    Groups all records into context — never calls AI per cell.
    Returns count of suggestions created.
    Only called if AI is available.
    """
    from .models import MaintainerSuggestion, SuggestionIssueType, SuggestionSource, SuggestionStatus

    try:
        provider, client = _get_ai_client()
    except RuntimeError as exc:
        logger.info('AI suggestion skipped: %s', exc)
        return 0

    schema = dataset.schema_json or {}
    columns = schema.get('columns', [])
    records = list(dataset.records.all().order_by('row_index')[:20])
    sample_rows = [r.data_json for r in records]

    if not columns or not sample_rows:
        return 0

    prompt = _build_context_prompt(dataset.name, columns, sample_rows)

    raw_response = ''
    try:
        if provider == 'openai':
            resp = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=800,
                temperature=0.2,
            )
            raw_response = resp.choices[0].message.content
        elif provider == 'gemini':
            model = client.GenerativeModel('gemini-1.5-flash')
            resp = model.generate_content(prompt)
            raw_response = resp.text
    except Exception as exc:
        logger.warning('AI API call failed: %s', exc)
        return 0

    # Parse response
    try:
        # Strip possible markdown fencing
        clean = raw_response.strip()
        if clean.startswith('```'):
            clean = clean.split('```')[1]
            if clean.startswith('json'):
                clean = clean[4:]
        items = json.loads(clean.strip())
        if not isinstance(items, list):
            return 0
    except (json.JSONDecodeError, IndexError) as exc:
        logger.warning('AI response parse failed: %s | raw=%s', exc, raw_response[:200])
        return 0

    valid_issue_types = {c[0] for c in SuggestionIssueType.choices}
    created = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        field = item.get('field_name', '')
        orig = str(item.get('original_value', ''))
        suggested = str(item.get('suggested_value', ''))
        reason = item.get('reason', 'AI-detected issue.')
        confidence = float(item.get('confidence', 0.6))
        issue_raw = item.get('issue_type', 'contextual')
        issue_type = issue_raw if issue_raw in valid_issue_types else 'contextual'

        if not field or orig == suggested:
            continue

        # Find the first matching record+field
        record = None
        for r in records:
            if field in (r.data_json or {}) and str(r.data_json[field]) == orig:
                record = r
                break

        MaintainerSuggestion.objects.create(
            dataset=dataset,
            record=record,
            document=dataset.source_document,
            field_name=field,
            original_value=orig,
            suggested_value=suggested,
            issue_type=issue_type,
            reason=reason,
            confidence=min(max(confidence, 0.0), 1.0),
            suggestion_source=SuggestionSource.AI,
            status=SuggestionStatus.PENDING,
            created_by=user,
        )
        created += 1

    logger.info('AI suggestions created for dataset %d: %d', dataset.pk, created)
    return created
