"""
apps.audit — Tests
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import AuditEvent, AuditEventType


class AuditEventModelTestCase(TestCase):
    def test_audit_event_creation(self):
        """AuditEvent can be created."""
        event = AuditEvent.objects.create(
            event_type=AuditEventType.DOCUMENT_UPLOADED,
            actor='analyst@cmpdi.co.in',
            resource_type='document',
            resource_id='42',
            description='Document "Annual Report 2025.pdf" uploaded.',
        )
        self.assertEqual(event.event_type, AuditEventType.DOCUMENT_UPLOADED)
        self.assertIsNotNone(event.timestamp)

    def test_audit_event_immutability(self):
        """AuditEvent records cannot be updated after creation."""
        event = AuditEvent.objects.create(
            event_type=AuditEventType.SYSTEM_HEALTH_CHECK,
            description='Health check passed.',
        )
        event.description = 'Modified description'
        with self.assertRaises(ValueError):
            event.save()

    def test_audit_event_str(self):
        """AuditEvent __str__ includes event type."""
        event = AuditEvent.objects.create(
            event_type=AuditEventType.USER_LOGIN,
            actor='admin@cmpdi.co.in',
            description='User logged in.',
        )
        self.assertIn('user.login', str(event))


class AuditAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_audit_stub_returns_200(self):
        """GET /api/audit/ returns 200 with not_implemented in Phase 1."""
        url = reverse('api-audit')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['status'], 'not_implemented')
