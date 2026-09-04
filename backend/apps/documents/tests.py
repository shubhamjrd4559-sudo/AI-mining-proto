"""
apps.documents — Comprehensive Tests for Phase 2 Document Ingestion & Storage
"""

import io
import os
import shutil
import tempfile
import hashlib
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from apps.storage.service import get_storage_service, reset_storage_service
from apps.audit.models import AuditEvent, AuditEventType
from .models import Document, ProcessingJob, DocumentStatus, JobStatus

User = get_user_model()


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

        self.user = User.objects.create_user(username='testminer', password='password123')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        self.settings_override.disable()
        reset_storage_service()
        if os.path.exists(self.temp_media):
            shutil.rmtree(self.temp_media, ignore_errors=True)

    def _upload_file(self, filename: str, content: bytes, content_type: str = 'application/octet-stream', client=None):
        test_client = client or self.client
        file_obj = SimpleUploadedFile(filename, content, content_type=content_type)
        return test_client.post(
            reverse('document-collection'),
            {'file': file_obj},
            format='multipart'
        )

    # 1. Finding 1: Authentication / Authorization Enforcement
    def test_unauthenticated_requests_blocked(self):
        anon_client = APIClient()
        # Upload
        res_up = self._upload_file('test.pdf', b'%PDF test', client=anon_client)
        self.assertIn(res_up.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # List
        res_list = anon_client.get(reverse('document-collection'))
        self.assertIn(res_list.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # Create a document first as authenticated
        res_auth = self._upload_file('valid.pdf', b'%PDF-1.4 valid content', 'application/pdf')
        self.assertEqual(res_auth.status_code, status.HTTP_201_CREATED)
        doc_id = res_auth.json()['document']['id']

        # Detail
        res_det = anon_client.get(reverse('document-detail', kwargs={'pk': doc_id}))
        self.assertIn(res_det.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # Status
        res_st = anon_client.get(reverse('document-status', kwargs={'pk': doc_id}))
        self.assertIn(res_st.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # Download
        res_dl = anon_client.get(reverse('document-download', kwargs={'pk': doc_id}))
        self.assertIn(res_dl.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # Archive
        res_ar = anon_client.post(reverse('document-archive', kwargs={'pk': doc_id}))
        self.assertIn(res_ar.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # Retry
        res_rt = anon_client.post(reverse('document-retry', kwargs={'pk': doc_id}))
        self.assertIn(res_rt.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # Delete
        res_del = anon_client.delete(reverse('document-detail', kwargs={'pk': doc_id}))
        self.assertIn(res_del.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    # 2. Finding 2: MIME Type & Magic Byte Validation
    def test_spoofed_pdf_magic_bytes_rejected(self):
        content = b'THIS IS PLAIN TEXT AND NOT A VALID PDF HEADER'
        res = self._upload_file('spoofed.pdf', content, 'application/pdf')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not a valid PDF', str(res.json()))

    def test_spoofed_png_magic_bytes_rejected(self):
        content = b'NOT_A_PNG_FILE'
        res = self._upload_file('spoofed.png', content, 'image/png')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not a valid PNG', str(res.json()))

    def test_spoofed_jpg_magic_bytes_rejected(self):
        content = b'NOT_A_JPG_FILE'
        res = self._upload_file('spoofed.jpg', content, 'image/jpeg')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not a valid JPEG', str(res.json()))

    def test_spoofed_docx_magic_bytes_rejected(self):
        content = b'NOT_A_ZIP_HEADER'
        res = self._upload_file('spoofed.docx', content, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not a valid OpenXML', str(res.json()))

    def test_spoofed_xlsx_magic_bytes_rejected(self):
        content = b'NOT_A_ZIP_HEADER'
        res = self._upload_file('spoofed.xlsx', content, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not a valid OpenXML', str(res.json()))

    def test_binary_in_csv_or_txt_rejected(self):
        binary_content = b'\x00\x01\x02\xff\xfe\x00 binary payload'
        res_csv = self._upload_file('binary.csv', binary_content, 'text/csv')
        self.assertEqual(res_csv.status_code, status.HTTP_400_BAD_REQUEST)

        res_txt = self._upload_file('binary.txt', binary_content, 'text/plain')
        self.assertEqual(res_txt.status_code, status.HTTP_400_BAD_REQUEST)

    # 3. Valid Uploads for all supported types
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

    def test_upload_scanned_pdf(self):
        content = b'%PDF-1.5 \x00\x01\x02\x03\xfe\xff scanned geological raster payload'
        res = self._upload_file('borehole_scanned.pdf', content, 'application/pdf')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res.json()['document']['id'])
        self.assertEqual(doc.original_filename, 'borehole_scanned.pdf')

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

    def test_upload_csv(self):
        content = b'mine,subsidiary,production_mt\nJharia,BCCL,4.2\n'
        res = self._upload_file('mines.csv', content, 'text/csv')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res.json()['document']['id'])
        self.assertEqual(doc.file_extension, '.csv')

    def test_upload_txt(self):
        content = b'Exploration field notes: North Karanpura block 4.'
        res = self._upload_file('field_notes.txt', content, 'text/plain')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res.json()['document']['id'])
        self.assertEqual(doc.file_extension, '.txt')

    def test_upload_png(self):
        content = b'\x89PNG\r\n\x1a\n mock png data'
        res = self._upload_file('seam_cross_section.png', content, 'image/png')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res.json()['document']['id'])
        self.assertEqual(doc.file_extension, '.png')

    def test_upload_jpg(self):
        content = b'\xff\xd8\xff\xe0 mock jpeg data'
        res = self._upload_file('opencast_mine_aerial.jpg', content, 'image/jpeg')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res.json()['document']['id'])
        self.assertEqual(doc.file_extension, '.jpg')

    # 4. Finding 8: Information Disclosure Protection in Serializers
    def test_storage_key_not_exposed_in_api(self):
        content = b'%PDF-1.4 secret structure test'
        res = self._upload_file('secret.pdf', content, 'application/pdf')
        data = res.json()
        self.assertNotIn('storage_key', data['document'])
        self.assertNotIn('stored_filename', data['document'])

        doc_id = data['document']['id']
        res_det = self.client.get(reverse('document-detail', kwargs={'pk': doc_id}))
        self.assertNotIn('storage_key', res_det.json())
        self.assertNotIn('stored_filename', res_det.json())

    # 5. Finding 5: Transaction Atomicity & Storage Cleanup on Failure
    def test_storage_cleaned_up_if_database_transaction_fails(self):
        content = b'%PDF-1.4 Atomic rollback test'
        storage = get_storage_service()

        with patch('apps.documents.views.ProcessingJob.objects.create', side_effect=RuntimeError("DB Job Failure")):
            res = self._upload_file('atomic_test.pdf', content, 'application/pdf')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('Database failure during document registration', str(res.json()))

        # Document count should still be 0
        self.assertEqual(Document.objects.filter(original_filename='atomic_test.pdf').count(), 0)
        # Storage files should be empty
        self.assertEqual(len(storage.list()), 0)

    # 6. Finding 6: Batch Limits Enforcement
    def test_batch_file_count_limit(self):
        files = [
            SimpleUploadedFile(f'doc_{i}.pdf', b'%PDF-1.4 test', content_type='application/pdf')
            for i in range(11) # Exceeds 10 file limit
        ]
        res = self.client.post(
            reverse('document-collection'),
            {'files': files},
            format='multipart'
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('limit exceeded', str(res.json()).lower())

    def test_batch_total_size_limit(self):
        # Override MAX_UPLOAD_SIZE to allow large single files but trigger MAX_BATCH_TOTAL_SIZE
        with override_settings(MAX_UPLOAD_SIZE=200 * 1024 * 1024, MAX_BATCH_TOTAL_SIZE=10 * 1024 * 1024):
            files = [
                SimpleUploadedFile('doc1.pdf', b'%PDF-1.4 ' + b'0' * (6 * 1024 * 1024), content_type='application/pdf'),
                SimpleUploadedFile('doc2.pdf', b'%PDF-1.4 ' + b'0' * (6 * 1024 * 1024), content_type='application/pdf'),
            ] # Total 12MB > 10MB batch limit
            res = self.client.post(
                reverse('document-collection'),
                {'files': files},
                format='multipart'
            )
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('Total batch size', str(res.json()))

    # 7. Finding 7: Document Retry State Machine & Duplicate Prevention
    def test_retry_rejected_for_completed_document(self):
        res_up = self._upload_file('done.pdf', b'%PDF-1.4 done content')
        self.assertEqual(res_up.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res_up.json()['document']['id'])
        doc.status = DocumentStatus.COMPLETED
        doc.save()

        res_retry = self.client.post(reverse('document-retry', kwargs={'pk': doc.id}))
        self.assertEqual(res_retry.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot retry document', str(res_retry.json()))

    def test_retry_rejected_when_active_job_exists(self):
        res_up = self._upload_file('busy.pdf', b'%PDF-1.4 busy content')
        self.assertEqual(res_up.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res_up.json()['document']['id'])
        doc.status = DocumentStatus.FAILED
        doc.save()

        # Create active job
        ProcessingJob.objects.create(
            document=doc,
            job_type=ProcessingJob.JobType.TEXT_EXTRACTION,
            status=JobStatus.RUNNING,
        )

        res_retry = self.client.post(reverse('document-retry', kwargs={'pk': doc.id}))
        self.assertEqual(res_retry.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Duplicate retry rejected', str(res_retry.json()))

    # 8. Unsupported Format Rejection
    def test_unsupported_format_rejected(self):
        res = self._upload_file('malicious.exe', b'MZ executable payload', 'application/x-msdownload')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Unsupported file format', str(res.json()))

        res_py = self._upload_file('script.py', b'print("hello")', 'text/x-python')
        self.assertEqual(res_py.status_code, status.HTTP_400_BAD_REQUEST)

    # 9. Oversized File Rejection
    def test_oversized_file_rejected(self):
        large_content = b'%PDF ' + b'0' * (6 * 1024 * 1024) # 6MB > 5MB limit
        res = self._upload_file('oversized.pdf', large_content, 'application/pdf')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('exceeds maximum allowed size', str(res.json()))

    # 10. Empty Upload Rejection
    def test_empty_upload_rejected(self):
        res = self._upload_file('empty.pdf', b'', 'application/pdf')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        res_nofile = self.client.post(reverse('document-collection'), {}, format='multipart')
        self.assertEqual(res_nofile.status_code, status.HTTP_400_BAD_REQUEST)

    # 11. Multiple Files Batch Upload
    def test_multiple_files_upload(self):
        f1 = SimpleUploadedFile('doc1.pdf', b'%PDF-1.4 doc 1', content_type='application/pdf')
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

    # 12. Finding 12: List Documents & Pagination / Filtering
    def test_list_documents_pagination_and_filtering(self):
        self._upload_file('alpha_report.pdf', b'%PDF-1.4 alpha', 'application/pdf')
        self._upload_file('beta_stats.xlsx', b'PK\x03\x04 beta', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        res = self.client.get(reverse('document-collection'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['count'], 2)
        self.assertIn('results', data)
        self.assertEqual(len(data['results']), 2)

        # Search filter
        res_search = self.client.get(reverse('document-collection'), {'search': 'alpha'})
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        self.assertEqual(res_search.json()['count'], 1)
        self.assertEqual(res_search.json()['results'][0]['original_filename'], 'alpha_report.pdf')

    # 13. Document Detail View
    def test_document_detail(self):
        res_up = self._upload_file('detailed_doc.pdf', b'%PDF-1.4 detailed doc content', 'application/pdf')
        doc_id = res_up.json()['document']['id']

        res_detail = self.client.get(reverse('document-detail', kwargs={'pk': doc_id}))
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        data = res_detail.json()
        self.assertEqual(data['id'], doc_id)
        self.assertEqual(data['original_filename'], 'detailed_doc.pdf')
        self.assertIn('jobs', data)
        self.assertGreaterEqual(len(data['jobs']), 1)

    # 14. Document Status Endpoint
    def test_document_status_endpoint(self):
        res_up = self._upload_file('status_check.pdf', b'%PDF-1.4 status content', 'application/pdf')
        doc_id = res_up.json()['document']['id']

        res_status = self.client.get(reverse('document-status', kwargs={'pk': doc_id}))
        self.assertEqual(res_status.status_code, status.HTTP_200_OK)
        data = res_status.json()
        self.assertEqual(data['id'], doc_id)
        self.assertEqual(data['status'], DocumentStatus.UPLOADED)

    # 15. Document Download Endpoint
    def test_document_download(self):
        content = b'%PDF-1.4 Real raw content test for download verification.'
        res_up = self._upload_file('download_test.pdf', content, 'application/pdf')
        doc_id = res_up.json()['document']['id']

        res_dl = self.client.get(reverse('document-download', kwargs={'pk': doc_id}))
        self.assertEqual(res_dl.status_code, status.HTTP_200_OK)
        self.assertEqual(res_dl.content, content)
        self.assertIn('attachment;', res_dl['Content-Disposition'])

    # 16. Retry Endpoint Success
    def test_document_retry_success(self):
        res_up = self._upload_file('retry_test.pdf', b'%PDF-1.4 retry content', 'application/pdf')
        doc = Document.objects.get(id=res_up.json()['document']['id'])
        # Complete existing initial job so there's no active job conflict
        ProcessingJob.objects.filter(document=doc).update(status=JobStatus.FAILED)
        doc.status = DocumentStatus.FAILED
        doc.error_message = 'Simulated OCR pipeline error'
        doc.save()

        res_retry = self.client.post(reverse('document-retry', kwargs={'pk': doc.id}))
        self.assertEqual(res_retry.status_code, status.HTTP_200_OK)
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.QUEUED)
        self.assertEqual(doc.error_message, '')

    # 17. Soft Archive & Hard Delete
    def test_document_archive_and_hard_delete(self):
        res_up = self._upload_file('delete_me.pdf', b'%PDF-1.4 delete me content', 'application/pdf')
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


