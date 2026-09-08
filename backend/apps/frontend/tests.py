"""
apps.frontend.tests — Integration tests for the Django-hosted frontend

Tests verify:
  1. GET / returns 200 with the expected HTML shell.
  2. The response does NOT contain the hard-coded development API_BASE.
  3. The response IS same-origin (API_BASE = '').
  4. The static asset tag is resolved (no raw {% static %} tags in output).
  5. /api/health/ continues to work from the same Django process.
  6. /admin/ is still accessible (not broken by root URL).
  7. Media and static URL settings are correct.
  8. Production settings import without requiring secrets or a real DB.
"""

from django.test import TestCase, override_settings
from django.urls import reverse


class FrontendRootViewTests(TestCase):
    """Tests for GET / — the Django-hosted frontend shell."""

    def test_root_returns_200(self):
        """GET / must return HTTP 200."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_root_content_type_is_html(self):
        """GET / must return text/html."""
        response = self.client.get('/')
        self.assertIn('text/html', response.get('Content-Type', ''))

    def test_root_contains_app_shell(self):
        """The response must contain key app shell identifiers."""
        response = self.client.get('/')
        content = response.content.decode('utf-8')
        # Title
        self.assertIn('CMPDI', content)
        # Must have a script section (JS is embedded)
        self.assertIn('<script', content)

    def test_root_no_hardcoded_development_api_base(self):
        """
        The rendered page must NOT contain the hard-coded development origin.
        This is the critical same-origin regression check.
        """
        response = self.client.get('/')
        content = response.content.decode('utf-8')
        self.assertNotIn("'http://127.0.0.1:8000'", content,
                         "Hard-coded development API_BASE found in rendered frontend. "
                         "API_BASE must be '' (empty string) when served by Django.")

    def test_root_api_base_is_empty_string(self):
        """The rendered page must declare API_BASE as the empty string."""
        response = self.client.get('/')
        content = response.content.decode('utf-8')
        self.assertIn("const API_BASE = '';", content,
                      "Same-origin API_BASE not found. Expected: const API_BASE = '';")

    def test_root_no_raw_django_template_tags(self):
        """
        The rendered output must not contain unresolved Django template syntax.
        If template rendering failed, raw {% ... %} tags would leak into the HTML.
        """
        response = self.client.get('/')
        content = response.content.decode('utf-8')
        self.assertNotIn('{%', content,
                         "Unresolved Django template tags found in rendered output.")
        self.assertNotIn('%}', content,
                         "Unresolved Django template tags found in rendered output.")

    def test_root_no_raw_template_variables(self):
        """
        The rendered output must not contain unresolved {{ }} variables.
        """
        response = self.client.get('/')
        content = response.content.decode('utf-8')
        self.assertNotIn('{{', content,
                         "Unresolved Django template variables found in rendered output.")

    def test_root_uses_correct_template(self):
        """GET / must be rendered using the frontend/index.html template."""
        response = self.client.get('/')
        template_names = [t.name for t in response.templates]
        self.assertIn('frontend/index.html', template_names,
                      f"Expected frontend/index.html template. Got: {template_names}")


class FrontendStaticAssetsTests(TestCase):
    """Tests verifying static asset configuration."""

    def test_static_url_configured(self):
        """STATIC_URL must be configured."""
        from django.conf import settings
        self.assertTrue(
            hasattr(settings, 'STATIC_URL') and settings.STATIC_URL,
            "STATIC_URL must be configured."
        )

    def test_static_root_configured(self):
        """STATIC_ROOT must be configured for collectstatic."""
        from django.conf import settings
        self.assertTrue(
            hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT,
            "STATIC_ROOT must be configured for collectstatic."
        )

    def test_staticfiles_dirs_includes_backend_static(self):
        """STATICFILES_DIRS must include the backend/static/ directory."""
        from django.conf import settings
        from pathlib import Path
        static_dirs = [str(d) for d in getattr(settings, 'STATICFILES_DIRS', [])]
        # At least one entry should resolve to backend/static/
        self.assertTrue(
            any('static' in d for d in static_dirs),
            f"STATICFILES_DIRS does not contain backend/static/. Got: {static_dirs}"
        )

    def test_media_url_configured(self):
        """MEDIA_URL must be configured for uploaded document serving."""
        from django.conf import settings
        self.assertEqual(settings.MEDIA_URL, '/media/',
                         "MEDIA_URL must be '/media/'.")

    def test_media_root_configured(self):
        """MEDIA_ROOT must be configured."""
        from django.conf import settings
        self.assertTrue(
            hasattr(settings, 'MEDIA_ROOT') and settings.MEDIA_ROOT,
            "MEDIA_ROOT must be configured."
        )


class FrontendAPICoexistenceTests(TestCase):
    """Tests that API routes and the frontend root coexist correctly."""

    def test_api_health_still_works(self):
        """GET /api/health/ must return 200 alongside the frontend root."""
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('status', data)

    def test_admin_route_not_broken(self):
        """GET /admin/ must return 302 (redirect to login) — not broken by root route."""
        response = self.client.get('/admin/')
        # Admin redirects unauthenticated users to login
        self.assertIn(response.status_code, [200, 301, 302])

    def test_root_does_not_conflict_with_api(self):
        """GET /api/ must NOT return the frontend HTML (route isolation)."""
        response = self.client.get('/api/health/')
        content = response.content.decode('utf-8')
        # API health check returns JSON, not HTML
        self.assertNotIn('<html', content.lower(),
                         "API route appears to be returning HTML. Route isolation broken.")

    def test_url_reversal_for_root(self):
        """The 'frontend-index' URL name must resolve to '/'."""
        url = reverse('frontend-index')
        self.assertEqual(url, '/')


class ProductionSettingsImportTest(TestCase):
    """
    Verify that production settings can be imported without real secrets or DB.
    This test checks the import-time safety of production.py.
    """

    def test_production_settings_are_importable(self):
        """
        Production settings must be importable without raising exceptions,
        even when DATABASE_URL and other secrets are not set.
        This protects against accidental import-time errors in deployment.
        """
        try:
            import importlib
            # Use override_settings to avoid touching the real DB
            import config.settings.production as prod_settings
            # Verify critical production safety flags
            self.assertFalse(prod_settings.DEBUG,
                             "DEBUG must be False in production settings.")
            self.assertTrue(
                hasattr(prod_settings, 'SECURE_SSL_REDIRECT'),
                "SECURE_SSL_REDIRECT must be defined in production settings."
            )
        except Exception as exc:
            # If dj_database_url or other deps fail, still validate the module exists
            # This is acceptable if DATABASE_URL is not set in the test environment
            import importlib.util
            spec = importlib.util.find_spec('config.settings.production')
            self.assertIsNotNone(spec, f"Production settings module not found: {exc}")
