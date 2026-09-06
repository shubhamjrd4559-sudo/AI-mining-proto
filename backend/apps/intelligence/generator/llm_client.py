"""
Configurable LLM client for Gemini provider.

Features:
  - API key strictly loaded from settings / environment (never committed or logged)
  - Timeout and exception safety
  - Graceful degradation when key is missing or service is unreachable
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Tuple, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """Lightweight HTTP client for Gemini models using standard urllib."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'GEMINI_API_KEY', None)
        self.model = model or getattr(settings, 'GEMINI_MODEL', 'gemini-2.5-flash')

    @property
    def is_available(self) -> bool:
        """Check if LLM provider has an API key configured."""
        return bool(self.api_key and str(self.api_key).strip())

    def generate_content(
        self,
        system_instruction: str,
        prompt: str,
        timeout: int = 10,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Call Gemini generateContent API.
        Returns:
          (generated_text, error_message)
        """
        if not self.is_available:
            return None, 'Gemini API key is not configured in environment.'

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 800,
            }
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        body_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url=url,
            data=body_bytes,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'CMPDI-AI-MiningIntelligence/1.0',
            },
            method='POST',
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_data = json.loads(resp.read().decode('utf-8'))
                candidates = resp_data.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    if parts and 'text' in parts[0]:
                        return parts[0]['text'].strip(), None
                return None, 'No text candidates returned by LLM.'
        except urllib.error.HTTPError as exc:
            # Mask any potential API key exposure in error logs
            logger.warning('Gemini API HTTPError %s', exc.code)
            return None, f'LLM API error (HTTP {exc.code})'
        except urllib.error.URLError as exc:
            logger.warning('Gemini API URLError: %s', exc.reason)
            return None, f'LLM network error: {exc.reason}'
        except Exception as exc:
            logger.warning('Gemini API unexpected error: %s', exc)
            return None, f'LLM service error: {exc}'


_default_client = None


def get_llm_client() -> GeminiClient:
    """Get or create singleton GeminiClient."""
    global _default_client
    if _default_client is None:
        _default_client = GeminiClient()
    return _default_client
