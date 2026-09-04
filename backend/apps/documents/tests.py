"""
apps.documents — Comprehensive Tests for Phase 2 Document Ingestion & Storage
"""

import io
import os
import shutil
import tempfile
import hashlib
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from apps.storage.service import get_storage_service, reset_storage_service
from apps.audit.models import AuditEvent, AuditEventType
from .models import Document, ProcessingJob, DocumentStatus, JobStatus


class DocumentModelTestCase(TestCase):
    def test_document_creation(self):
        """Document can be created with required fields and defaults."""
        doc = Document.objects.create(
            title='Test Geological Report',
            original_filename='geo_report_2026.pdf',
            stored_filename='test_geo.pdf',
            storage_key='documents/2026/09/05/test_geo.pdf',
            file_extension='.pdf',
            file_size=1024 * 1024,
            mime_type='application/pdf',
            sha256_hash='a' * 64,
            status=DocumentStatus.UPLOADED,
        )
        self.assertEqual(doc.status, DocumentStatus.UPLOADED)
        self.assertEqual(doc.title, 'Test Geological Report')
        self.assertEqual(doc.file_extension, '.pdf')
        self.assertEqual(doc.file_size_display, '1.0 MB')
        self.assertFalse(doc.is_archived)
        self.assertIsNotNone(doc.created_at)

    def test_document_status_choices(self):
        """All document status choices are valid."""
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
            job_type=ProcessingJob.JobType.TEXT_EXTRACTION,
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


class DocumentUploadAndAPITestCase(TestCase):
    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.temp_media,
            MAX_UPLOAD_SIZE=5 * 1024 * 1024, # 5MB limit for testing
        )
        self.settings_override.enable()
        reset_storage_service()
        self.client = APIClient()

    def tearDown(self):
        self.settings_override.disable()
        reset_storage_service()
        if os.path.exists(self.temp_media):
            shutil.rmtree(self.temp_media, ignore_errors=True)

    def _upload_file(self, filename: str, content: bytes, content_type: str = 'application/octet-stream'):
        file_obj = SimpleUploadedFile(filename, content, content_type=content_type)
        return self.client.post(
            reverse('document-collection'),
            {'file': file_obj},
            format='multipart'
        )

    # 1. PDF Upload
    def test_upload_pdf(self):
        content = b'%PDF-1.4 Mock PDF content for mining report.'
        res = self._upload_file('mining_survey.pdf', content, 'application/pdf')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['uploaded_count'], 1)

        doc = Document.objects.get(id=data['document']['id'])
        self.assertEqual(doc.original_filename, 'mining_survey.pdf')
        self.assertEqual(doc.file_extension, '.pdf')
        self.assertEqual(doc.status, DocumentStatus.UPLOADED)
        self.assertEqual(doc.sha256_hash, hashlib.sha256(content).hexdigest())

        # Verify storage existence
        storage = get_storage_service()
        self.assertTrue(storage.exists(doc.storage_key))
        self.assertEqual(storage.open(doc.storage_key), content)

        # Verify audit event
        audit = AuditEvent.objects.filter(event_type=AuditEventType.DOCUMENT_UPLOADED, resource_id=str(doc.id)).first()
        self.assertIsNotNone(audit)

    # 2. Scanned PDF (simulated binary)
    def test_upload_scanned_pdf(self):
        content = b'%PDF-1.5 \x00\x01\x02\x03\xfe\xff scanned geological raster payload'
        res = self._upload_file('borehole_scanned.pdf', content, 'application/pdf')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res.json()['document']['id'])
        self.assertEqual(doc.original_filename, 'borehole_scanned.pdf')

    # 3. DOCX Upload
    def test_upload_docx(self):
        content = b'PK\x03\x04 mock docx xml zip archive data'
        res = self._upload_file(
            'production_plan.docx',
            content,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res.json()['document']['id'])
        self.assertEqual(doc.file_extension, '.docx')

    # 4. XLSX Upload
    def test_upload_xlsx(self):
        content = b'PK\x03\x04 mock xlsx spreadsheet data'
        res = self._upload_file(
            'coal_production_q1.xlsx',
            content,
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res.json()['document']['id'])
        self.assertEqual(doc.file_extension, '.xlsx')

    # 5. CSV Upload
    def test_upload_csv(self):
        content = b'mine,subsidiary,production_mt\nJharia,BCCL,4.2\n'
        res = self._upload_file('mines.csv', content, 'text/csv')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res.json()['document']['id'])
        self.assertEqual(doc.file_extension, '.csv')

    # 6. TXT Upload
    def test_upload_txt(self):
        content = b'Exploration field notes: North Karanpura block 4.'
        res = self._upload_file('field_notes.txt', content, 'text/plain')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res.json()['document']['id'])
        self.assertEqual(doc.file_extension, '.txt')

    # 7. PNG Upload
    def test_upload_png(self):
        content = b'\x89PNG\r\n\x1a\n mock png data'
        res = self._upload_file('seam_cross_section.png', content, 'image/png')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res.json()['document']['id'])
        self.assertEqual(doc.file_extension, '.png')

    # 8. JPG/JPEG Upload
    def test_upload_jpg(self):
        content = b'\xff\xd8\xff\xe0 mock jpeg data'
        res = self._upload_file('opencast_mine_aerial.jpg', content, 'image/jpeg')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res.json()['document']['id'])
        self.assertEqual(doc.file_extension, '.jpg')

    # 9. Unsupported Format Rejection
    def test_unsupported_format_rejected(self):
        res = self._upload_file('malicious.exe', b'MZ executable payload', 'application/x-msdownload')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Unsupported file format', str(res.json()))

        res_py = self._upload_file('script.py', b'print("hello")', 'text/x-python')
        self.assertEqual(res_py.status_code, status.HTTP_400_BAD_REQUEST)

    # 10. Oversized File Rejection
    def test_oversized_file_rejected(self):
        large_content = b'0' * (6 * 1024 * 1024) # 6MB > 5MB limit
        res = self._upload_file('oversized.pdf', large_content, 'application/pdf')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('exceeds maximum allowed size', str(res.json()))

    # 11. Empty Upload Rejection
    def test_empty_upload_rejected(self):
        res = self._upload_file('empty.pdf', b'', 'application/pdf')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # No file sent at all
        res_nofile = self.client.post(reverse('document-collection'), {}, format='multipart')
        self.assertEqual(res_nofile.status_code, status.HTTP_400_BAD_REQUEST)

    # 12. Multiple Files Batch Upload
    def test_multiple_files_upload(self):
        f1 = SimpleUploadedFile('doc1.pdf', b'%PDF doc 1', content_type='application/pdf')
        f2 = SimpleUploadedFile('doc2.xlsx', b'PK\x03\x04 xlsx 2', content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        f3 = SimpleUploadedFile('doc3.txt', b'text notes', content_type='text/plain')

        res = self.client.post(
            reverse('document-collection'),
            {'files': [f1, f2, f3]},
            format='multipart'
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.json()
        self.assertEqual(data['uploaded_count'], 3)
        self.assertEqual(len(data['documents']), 3)
        self.assertEqual(Document.objects.count(), 3)

    # 13. List Documents & Filtering
    def test_list_documents(self):
        # Create test documents
        self._upload_file('alpha_report.pdf', b'%PDF alpha')
        self._upload_file('beta_stats.xlsx', b'PK beta')

        res = self.client.get(reverse('document-collection'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['count'], 2)

        # Search filter
        res_search = self.client.get(reverse('document-collection'), {'search': 'alpha'})
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        self.assertEqual(res_search.json()['count'], 1)

    # 14. Document Detail View
    def test_document_detail(self):
        res_up = self._upload_file('detailed_doc.pdf', b'%PDF detailed doc content')
        doc_id = res_up.json()['document']['id']

        res_detail = self.client.get(reverse('document-detail', kwargs={'pk': doc_id}))
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        data = res_detail.json()
        self.assertEqual(data['id'], doc_id)
        self.assertEqual(data['original_filename'], 'detailed_doc.pdf')
        self.assertIn('jobs', data)
        self.assertGreaterEqual(len(data['jobs']), 1)

    # 15. Document Status Endpoint
    def test_document_status_endpoint(self):
        res_up = self._upload_file('status_check.pdf', b'%PDF status content')
        doc_id = res_up.json()['document']['id']

        res_status = self.client.get(reverse('document-status', kwargs={'pk': doc_id}))
        self.assertEqual(res_status.status_code, status.HTTP_200_OK)
        data = res_status.json()
        self.assertEqual(data['id'], doc_id)
        self.assertEqual(data['status'], DocumentStatus.UPLOADED)

    # 16. Document Download Endpoint
    def test_document_download(self):
        content = b'%PDF-1.4 Real raw content test for download verification.'
        res_up = self._upload_file('download_test.pdf', content, 'application/pdf')
        doc_id = res_up.json()['document']['id']

        res_dl = self.client.get(reverse('document-download', kwargs={'pk': doc_id}))
        self.assertEqual(res_dl.status_code, status.HTTP_200_OK)
        self.assertEqual(res_dl.content, content)
        self.assertIn('attachment;', res_dl['Content-Disposition'])

    # 17. Retry Endpoint
    def test_document_retry(self):
        res_up = self._upload_file('retry_test.pdf', b'%PDF retry content')
        doc = Document.objects.get(id=res_up.json()['document']['id'])
        doc.status = DocumentStatus.FAILED
        doc.error_message = 'Simulated OCR pipeline error'
        doc.save()

        res_retry = self.client.post(reverse('document-retry', kwargs={'pk': doc.id}))
        self.assertEqual(res_retry.status_code, status.HTTP_200_OK)
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.QUEUED)
        self.assertEqual(doc.error_message, '')

    # 18. Soft Archive & Hard Delete
    def test_document_archive_and_hard_delete(self):
        res_up = self._upload_file('delete_me.pdf', b'%PDF delete me content')
        doc_id = res_up.json()['document']['id']
        doc = Document.objects.get(id=doc_id)
        storage_key = doc.storage_key

        # Soft delete / archive via POST /archive/
        res_arch = self.client.post(reverse('document-archive', kwargs={'pk': doc_id}))
        self.assertEqual(res_arch.status_code, status.HTTP_200_OK)
        doc.refresh_from_db()
        self.assertTrue(doc.is_archived)

        # By default, list excludes archived
        res_list = self.client.get(reverse('document-collection'))
        self.assertEqual(res_list.json()['count'], 0)

        # Hard delete
        res_hard = self.client.delete(f"{reverse('document-detail', kwargs={'pk': doc_id})}?hard=true")
        self.assertEqual(res_hard.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Document.objects.filter(id=doc_id).exists())

        # Storage file deleted
        storage = get_storage_service()
        self.assertFalse(storage.exists(storage_key))

