"""
apps.audit — Tests (Phase 9)
"""

from datetime import datetime, timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from django.contrib.auth import get_user_model
from .models import AuditEvent, AuditEventType

User = get_user_model()


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

        # Create users
        self.user1 = User.objects.create_user(
            username='analyst1',
            email='analyst1@cmpdi.co.in',
            password='password123',
        )
        self.user2 = User.objects.create_user(
            username='analyst2',
            email='analyst2@cmpdi.co.in',
            password='password123',
        )
        self.admin = User.objects.create_superuser(
            username='admin_boss',
            email='admin@cmpdi.co.in',
            password='password123',
        )

        # Seed audit events for user1
        self.event_u1_upload = AuditEvent.objects.create(
            event_type=AuditEventType.DOCUMENT_UPLOADED,
            actor='analyst1',
            actor_ip='192.168.1.10',
            resource_type='document',
            resource_id='101',
            description='Uploaded quarterly coal production report.pdf',
            metadata_json={'file_size': 1024, 'pages': 5},
        )
        self.event_u1_ai = AuditEvent.objects.create(
            event_type=AuditEventType.AI_QUERY_SUBMITTED,
            actor='analyst1',
            actor_ip='192.168.1.10',
            resource_type='ai_query',
            resource_id='ai-501',
            description='Query: Gevra mine opencast reserves 2024',
            metadata_json={'confidence': 0.94},
        )

        # Seed audit events for user2
        self.event_u2_report = AuditEvent.objects.create(
            event_type=AuditEventType.AI_REPORT_GENERATED,
            actor='analyst2',
            actor_ip='192.168.1.20',
            resource_type='report',
            resource_id='rep-202',
            description='Generated SECL exploration analysis report',
            metadata_json={'format': 'pdf'},
        )
        self.event_u2_delete = AuditEvent.objects.create(
            event_type=AuditEventType.DOCUMENT_DELETED,
            actor='analyst2',
            actor_ip='192.168.1.20',
            resource_type='document',
            resource_id='102',
            description='Archived obsolete geological survey document',
            metadata_json={'archived': True},
        )

    def test_unauthenticated_request_returns_401(self):
        """Unauthenticated requests to /api/audit/ must receive HTTP 401."""
        url = reverse('api-audit')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_scoped_to_own_events(self):
        """Regular users only receive their own audit records."""
        self.client.force_authenticate(user=self.user1)
        url = reverse('api-audit')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data['count'], 2)
        actors = {item['actor'] for item in data['results']}
        self.assertEqual(actors, {'analyst1'})

    def test_regular_user_cannot_view_others_via_actor_param(self):
        """Regular users passing ?actor=other_user remain restricted to their own logs."""
        self.client.force_authenticate(user=self.user1)
        url = reverse('api-audit') + '?actor=analyst2'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data['count'], 2)
        actors = {item['actor'] for item in data['results']}
        self.assertEqual(actors, {'analyst1'})

    def test_admin_can_view_all_audit_records(self):
        """Admin/manager can view records across all users in the enterprise audit trail."""
        self.client.force_authenticate(user=self.admin)
        url = reverse('api-audit')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertGreaterEqual(data['count'], 4)
        actors = {item['actor'] for item in data['results']}
        self.assertTrue({'analyst1', 'analyst2'}.issubset(actors))

    def test_admin_can_filter_by_actor(self):
        """Admin can filter records by specific actor."""
        self.client.force_authenticate(user=self.admin)
        url = reverse('api-audit') + '?actor=analyst2'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data['count'], 2)
        actors = {item['actor'] for item in data['results']}
        self.assertEqual(actors, {'analyst2'})

    def test_filter_by_event_type(self):
        """Filter audit records by event_type."""
        self.client.force_authenticate(user=self.admin)
        url = reverse('api-audit') + f'?event_type={AuditEventType.DOCUMENT_UPLOADED}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['event_type'], AuditEventType.DOCUMENT_UPLOADED)
        self.assertEqual(data['results'][0]['event_type_display'], 'Document Uploaded')

    def test_filter_by_resource_type(self):
        """Filter audit records by resource_type."""
        self.client.force_authenticate(user=self.admin)
        url = reverse('api-audit') + '?resource_type=report'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['resource_type'], 'report')

    def test_filter_by_search_keyword(self):
        """Search filter matches description, resource_id, or actor."""
        self.client.force_authenticate(user=self.admin)
        url = reverse('api-audit') + '?search=Gevra'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertIn('Gevra', data['results'][0]['description'])

    def test_filter_by_date_range(self):
        """Date filters return events matching timestamp range."""
        self.client.force_authenticate(user=self.admin)
        today_str = timezone.now().strftime('%Y-%m-%d')
        url = reverse('api-audit') + f'?date_from={today_str}&date_to={today_str}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertGreaterEqual(data['count'], 4)

    def test_reverse_chronological_ordering(self):
        """Results are sorted by -timestamp (newest first)."""
        self.client.force_authenticate(user=self.admin)
        url = reverse('api-audit')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.json()['results']
        timestamps = [item['timestamp'] for item in results]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_pagination(self):
        """Pagination returns count, total_pages, page_size, and results subset."""
        self.client.force_authenticate(user=self.admin)
        url = reverse('api-audit') + '?page=1&page_size=2'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(data['page_size'], 2)
        self.assertEqual(data['current_page'], 1)
        self.assertGreaterEqual(data['total_pages'], 2)
        self.assertIsNotNone(data['next'])

    def test_audit_detail_owner_success(self):
        """Owner can view their own audit event detail."""
        self.client.force_authenticate(user=self.user1)
        url = reverse('api-audit-detail', args=[self.event_u1_upload.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['id'], self.event_u1_upload.id)
        self.assertEqual(response.json()['actor'], 'analyst1')

    def test_audit_detail_forbidden_for_non_owner(self):
        """Regular user receives 403 when trying to access another user's audit event."""
        self.client.force_authenticate(user=self.user1)
        url = reverse('api-audit-detail', args=[self.event_u2_report.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_audit_detail_admin_can_access_any(self):
        """Admin can view any audit event detail."""
        self.client.force_authenticate(user=self.admin)
        url = reverse('api-audit-detail', args=[self.event_u2_report.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['id'], self.event_u2_report.id)

    def test_audit_detail_not_found(self):
        """Non-existent audit event ID returns 404."""
        self.client.force_authenticate(user=self.admin)
        url = reverse('api-audit-detail', args=[999999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
