"""
apps.documents — Tests
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import Document, ProcessingJob, DocumentStatus, JobStatus


class DocumentModelTestCase(TestCase):
    def test_document_creation(self):
        """Document can be created with required fields."""
        doc = Document.objects.create(
            title='Test Geological Report',
            original_filename='geo_report_2026.pdf',
            file_size=1024 * 1024,
            mime_type='application/pdf',
            status=DocumentStatus.UPLOADED,
        )
        self.assertEqual(doc.status, DocumentStatus.UPLOADED)
        self.assertEqual(doc.title, 'Test Geological Report')
        self.assertIsNotNone(doc.created_at)

    def test_document_status_choices(self):
        """All 8 document status choices are valid."""
        for status_val, _ in DocumentStatus.choices:
            doc = Document.objects.create(
                title=f'Doc {status_val}',
                status=status_val,
            )
            self.assertEqual(doc.status, status_val)

    def test_processing_job_creation(self):
        """ProcessingJob can be created linked to a Document."""
        doc = Document.objects.create(title='Test Doc')
        job = ProcessingJob.objects.create(
            document=doc,
            job_type=ProcessingJob.JobType.OCR,
            status=JobStatus.PENDING,
        )
        self.assertEqual(job.document, doc)
        self.assertEqual(job.status, JobStatus.PENDING)

    def test_document_str(self):
        """Document __str__ includes title and status."""
        doc = Document.objects.create(
            title='Annual Report',
            status=DocumentStatus.COMPLETED,
        )
        self.assertIn('Annual Report', str(doc))
        self.assertIn('completed', str(doc))


class DocumentAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_documents_stub_returns_200(self):
        """GET /api/documents/ returns 200 with not_implemented in Phase 1."""
        url = reverse('api-documents')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['status'], 'not_implemented')
        self.assertEqual(response.json()['phase'], 2)
