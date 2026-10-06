"""
apps.core — Tests

Verifies:
  1. GET /api/health/ returns 200
  2. Health response contains required fields
  3. Database is connected
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status


class HealthCheckTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_returns_200(self):
        """Health endpoint must return HTTP 200."""
        url = reverse('api-health')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health_response_structure(self):
        """Health response must contain required fields."""
        url = reverse('api-health')
        response = self.client.get(url)
        data = response.json()

        self.assertIn('status', data)
        self.assertIn('service', data)
        self.assertIn('version', data)
        self.assertIn('database', data)
        self.assertIn('timestamp', data)
        self.assertIn('phase', data)

    def test_health_status_ok(self):
        """Health status must be 'ok' when database is connected."""
        url = reverse('api-health')
        response = self.client.get(url)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['database'], 'connected')

    def test_health_service_name(self):
        """Service name must identify this application."""
        url = reverse('api-health')
        response = self.client.get(url)
        data = response.json()
        self.assertEqual(data['service'], 'CMPDI AI Backend')

    def test_health_phase(self):
        """Phase must reflect current implementation phase in the health response."""
        url = reverse('api-health')
        response = self.client.get(url)
        data = response.json()
        self.assertEqual(data['phase'], 2)

    def test_stub_endpoints_return_200(self):
        """All stub endpoints must return 200 with not_implemented status."""
        stubs = [
            reverse('api-analytics'),
            reverse('api-chat'),
            reverse('api-excel'),
            reverse('api-reports'),
            reverse('api-topics'),
        ]
        for url in stubs:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                data = response.json()
                self.assertEqual(data['status'], 'not_implemented')
                self.assertEqual(data['phase'], 2)

    def test_current_user_unauthenticated(self):
        """Unauthenticated call to /api/auth/me/ returns authenticated: False."""
        url = reverse('api-auth-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertFalse(data['authenticated'])
        self.assertIsNone(data['username'])

    def test_current_user_authenticated(self):
        """Authenticated call to /api/auth/me/ returns user details and role."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(username='admin', password='testpassword123', is_staff=True)
        self.client.force_authenticate(user=user)
        url = reverse('api-auth-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['authenticated'])
        self.assertEqual(data['username'], 'admin')
        self.assertEqual(data['role'], 'Administrator · CMPDI')
