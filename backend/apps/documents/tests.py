"""
apps.documents — Comprehensive Tests for Phase 2 Document Ingestion & Storage
Phase 2 Final Fix Pass: adds ownership, MIME structure, and audit atomicity tests.
"""

import io
import os
import shutil
import tempfile
import hashlib
import zipfile
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_docx() -> bytes:
    """Create a minimal but structurally valid DOCX file in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types/>')
        zf.writestr('word/document.xml', '<?xml version="1.0"?><w:document/>')
    return buf.getvalue()


def _make_valid_xlsx() -> bytes:
    """Create a minimal but structurally valid XLSX file in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types/>')
        zf.writestr('xl/workbook.xml', '<?xml version="1.0"?><workbook/>')
    return buf.getvalue()


def _make_bare_zip() -> bytes:
    """Create a valid ZIP that is NOT an Office document (no Content_Types.xml)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('README.txt', 'This is a bare zip, not an Office doc.')
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# API Tests
# ---------------------------------------------------------------------------

class DocumentUploadAndAPITestCase(TestCase):
    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.temp_media,
            MAX_UPLOAD_SIZE=5 * 1024 * 1024,
        )
        self.settings_override.enable()
        reset_storage_service()

        self.user = User.objects.create_user(username='testminer', password='password123')
        self.other_user = User.objects.create_user(username='otheruser', password='pass456')

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.other_client = APIClient()
        self.other_client.force_authenticate(user=self.other_user)

    def tearDown(self):
        self.settings_override.disable()
        reset_storage_service()
        if os.path.exists(self.temp_media):
            shutil.rmtree(self.temp_media, ignore_errors=True)

    def _upload_file(self, filename: str, content: bytes,
                     content_type: str = 'application/octet-stream', client=None):
        test_client = client or self.client
        file_obj = SimpleUploadedFile(filename, content, content_type=content_type)
        return test_client.post(
            reverse('document-collection'),
            {'file': file_obj},
            format='multipart'
        )

    # ------------------------------------------------------------------
    # Authentication Enforcement
    # ------------------------------------------------------------------

    def test_unauthenticated_requests_blocked(self):
        """All document endpoints require authentication."""
        anon_client = APIClient()

        res_up = self._upload_file('test.pdf', b'%PDF test', client=anon_client)
        self.assertIn(res_up.status_code,
                      [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        res_list = anon_client.get(reverse('document-collection'))
        self.assertIn(res_list.status_code,
                      [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # Upload a real doc first to get a valid doc ID
        res_auth = self._upload_file('valid.pdf', b'%PDF-1.4 content', 'application/pdf')
        self.assertEqual(res_auth.status_code, status.HTTP_201_CREATED)
        doc_id = res_auth.json()['document']['id']

        for url_name, kwargs, method in [
            ('document-detail', {'pk': doc_id}, 'get'),
            ('document-status', {'pk': doc_id}, 'get'),
            ('document-download', {'pk': doc_id}, 'get'),
            ('document-archive', {'pk': doc_id}, 'post'),
            ('document-retry', {'pk': doc_id}, 'post'),
            ('document-detail', {'pk': doc_id}, 'delete'),
        ]:
            url = reverse(url_name, kwargs=kwargs)
            res = getattr(anon_client, method)(url)
            self.assertIn(res.status_code,
                          [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
                          msg=f"Expected auth required for {method.upper()} {url_name}")

    # ------------------------------------------------------------------
    # Document Authorization (Ownership)
    # ------------------------------------------------------------------

    def test_list_scoped_to_owner(self):
        """Document list returns only the requesting user's documents."""
        # user uploads a doc
        self._upload_file('userA_report.pdf', b'%PDF-1.4 userA', 'application/pdf')
        # other_user uploads a doc
        self._upload_file('userB_report.pdf', b'%PDF-1.4 userB', 'application/pdf',
                          client=self.other_client)

        res_user = self.client.get(reverse('document-collection'))
        self.assertEqual(res_user.status_code, status.HTTP_200_OK)
        self.assertEqual(res_user.json()['count'], 1)
        self.assertEqual(res_user.json()['results'][0]['original_filename'], 'userA_report.pdf')

        res_other = self.other_client.get(reverse('document-collection'))
        self.assertEqual(res_other.status_code, status.HTTP_200_OK)
        self.assertEqual(res_other.json()['count'], 1)
        self.assertEqual(res_other.json()['results'][0]['original_filename'], 'userB_report.pdf')

    def test_non_owner_cannot_view_detail(self):
        """Another authenticated user cannot view a document they do not own."""
        res_up = self._upload_file('secret.pdf', b'%PDF-1.4 secret', 'application/pdf')
        doc_id = res_up.json()['document']['id']

        res = self.other_client.get(reverse('document-detail', kwargs={'pk': doc_id}))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_owner_cannot_download(self):
        """Another authenticated user cannot download a document they do not own."""
        res_up = self._upload_file('private.pdf', b'%PDF-1.4 private', 'application/pdf')
        doc_id = res_up.json()['document']['id']

        res = self.other_client.get(reverse('document-download', kwargs={'pk': doc_id}))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_owner_cannot_archive(self):
        """Another authenticated user cannot archive a document they do not own."""
        res_up = self._upload_file('owned.pdf', b'%PDF-1.4 owned', 'application/pdf')
        doc_id = res_up.json()['document']['id']

        res = self.other_client.post(reverse('document-archive', kwargs={'pk': doc_id}))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_owner_cannot_delete(self):
        """Another authenticated user cannot delete a document they do not own."""
        res_up = self._upload_file('mine.pdf', b'%PDF-1.4 mine', 'application/pdf')
        doc_id = res_up.json()['document']['id']

        res = self.other_client.delete(reverse('document-detail', kwargs={'pk': doc_id}))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_owner_cannot_check_status(self):
        """Another authenticated user cannot poll status of a document they do not own."""
        res_up = self._upload_file('poll_me.pdf', b'%PDF-1.4 poll', 'application/pdf')
        doc_id = res_up.json()['document']['id']

        res = self.other_client.get(reverse('document-status', kwargs={'pk': doc_id}))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_access_own_document(self):
        """Owner can access their own document detail and status endpoints."""
        res_up = self._upload_file('myown.pdf', b'%PDF-1.4 my own', 'application/pdf')
        doc_id = res_up.json()['document']['id']

        res_det = self.client.get(reverse('document-detail', kwargs={'pk': doc_id}))
        self.assertEqual(res_det.status_code, status.HTTP_200_OK)

        res_st = self.client.get(reverse('document-status', kwargs={'pk': doc_id}))
        self.assertEqual(res_st.status_code, status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # MIME / Magic Byte Validation (Finding 3)
    # ------------------------------------------------------------------

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
        res = self._upload_file('spoofed.docx', content,
                                'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not a valid OpenXML', str(res.json()))

    def test_spoofed_xlsx_magic_bytes_rejected(self):
        content = b'NOT_A_ZIP_HEADER'
        res = self._upload_file('spoofed.xlsx', content,
                                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not a valid OpenXML', str(res.json()))

    def test_arbitrary_zip_as_docx_rejected(self):
        """A bare ZIP without OpenXML structure must be rejected as DOCX."""
        content = _make_bare_zip()
        res = self._upload_file('notadoc.docx', content,
                                'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Content_Types', str(res.json()))

    def test_arbitrary_zip_as_xlsx_rejected(self):
        """A bare ZIP without OpenXML structure must be rejected as XLSX."""
        content = _make_bare_zip()
        res = self._upload_file('notasheet.xlsx', content,
                                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Content_Types', str(res.json()))

    def test_valid_docx_structure_accepted(self):
        """A structurally valid DOCX (correct OpenXML internal layout) is accepted."""
        content = _make_valid_docx()
        res = self._upload_file('valid_structure.docx', content,
                                'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_valid_xlsx_structure_accepted(self):
        """A structurally valid XLSX (correct OpenXML internal layout) is accepted."""
        content = _make_valid_xlsx()
        res = self._upload_file('valid_structure.xlsx', content,
                                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_binary_in_csv_or_txt_rejected(self):
        binary_content = b'\x00\x01\x02\xff\xfe\x00 binary payload'
        res_csv = self._upload_file('binary.csv', binary_content, 'text/csv')
        self.assertEqual(res_csv.status_code, status.HTTP_400_BAD_REQUEST)
        res_txt = self._upload_file('binary.txt', binary_content, 'text/plain')
        self.assertEqual(res_txt.status_code, status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------
    # Valid Uploads for all supported types
    # ------------------------------------------------------------------

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
        self.assertEqual(doc.uploaded_by, self.user)

        # Verify storage existence
        storage = get_storage_service()
        self.assertTrue(storage.exists(doc.storage_key))
        self.assertEqual(storage.open(doc.storage_key), content)

        # Verify audit event was created atomically with the document
        audit = AuditEvent.objects.filter(
            event_type=AuditEventType.DOCUMENT_UPLOADED,
            resource_id=str(doc.id)
        ).first()
        self.assertIsNotNone(audit, "Audit event must be created for every upload")

    def test_upload_docx_valid_structure(self):
        content = _make_valid_docx()
        res = self._upload_file(
            'production_plan.docx', content,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res.json()['document']['id'])
        self.assertEqual(doc.file_extension, '.docx')

    def test_upload_xlsx_valid_structure(self):
        content = _make_valid_xlsx()
        res = self._upload_file(
            'coal_production_q1.xlsx', content,
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc = Document.objects.get(id=res.json()['document']['id'])
        self.assertEqual(doc.file_extension, '.xlsx')

    def test_upload_csv(self):
        content = b'mine,subsidiary,production_mt\nJharia,BCCL,4.2\n'
        res = self._upload_file('mines.csv', content, 'text/csv')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_upload_txt(self):
        content = b'Exploration field notes: North Karanpura block 4.'
        res = self._upload_file('field_notes.txt', content, 'text/plain')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_upload_png(self):
        content = b'\x89PNG\r\n\x1a\n mock png data'
        res = self._upload_file('seam_cross_section.png', content, 'image/png')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_upload_jpg(self):
        content = b'\xff\xd8\xff\xe0 mock jpeg data'
        res = self._upload_file('opencast_mine_aerial.jpg', content, 'image/jpeg')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    # ------------------------------------------------------------------
    # Audit Atomicity (Finding 4)
    # ------------------------------------------------------------------

    def test_storage_cleaned_up_if_database_transaction_fails(self):
        """If DB transaction fails, storage file is cleaned up and no Document is created."""
        content = b'%PDF-1.4 Atomic rollback test'
        storage = get_storage_service()

        with patch('apps.documents.views.ProcessingJob.objects.create',
                   side_effect=RuntimeError("DB Job Failure")):
            res = self._upload_file('atomic_test.pdf', content, 'application/pdf')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('Database failure during document registration', str(res.json()))

        self.assertEqual(Document.objects.filter(original_filename='atomic_test.pdf').count(), 0)
        self.assertEqual(len(storage.list()), 0)

    def test_audit_event_created_atomically_with_document(self):
        """Every successful upload must have a corresponding AuditEvent."""
        content = b'%PDF-1.4 Audit atomicity test'
        res = self._upload_file('audit_check.pdf', content, 'application/pdf')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc_id = res.json()['document']['id']

        audit_count = AuditEvent.objects.filter(
            event_type=AuditEventType.DOCUMENT_UPLOADED,
            resource_id=str(doc_id),
        ).count()
        self.assertEqual(audit_count, 1, "Exactly one audit event must exist per upload")

    def test_no_document_without_audit_event(self):
        """If audit event creation fails, the document record must also be rolled back."""
        content = b'%PDF-1.4 No orphan document test'

        with patch('apps.documents.views.log_audit', side_effect=RuntimeError("audit failure")):
            res = self._upload_file('orphan_check.pdf', content, 'application/pdf')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(Document.objects.filter(original_filename='orphan_check.pdf').count(), 0)

    # ------------------------------------------------------------------
    # Information Disclosure (Finding 8)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Batch Limits
    # ------------------------------------------------------------------

    def test_batch_file_count_limit(self):
        files = [
            SimpleUploadedFile(f'doc_{i}.pdf', b'%PDF-1.4 test',
                               content_type='application/pdf')
            for i in range(11)
        ]
        res = self.client.post(
            reverse('document-collection'),
            {'files': files},
            format='multipart'
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('limit exceeded', str(res.json()).lower())

    def test_batch_total_size_limit(self):
        with override_settings(MAX_UPLOAD_SIZE=200 * 1024 * 1024,
                               MAX_BATCH_TOTAL_SIZE=10 * 1024 * 1024):
            files = [
                SimpleUploadedFile('doc1.pdf', b'%PDF-1.4 ' + b'0' * (6 * 1024 * 1024),
                                   content_type='application/pdf'),
                SimpleUploadedFile('doc2.pdf', b'%PDF-1.4 ' + b'0' * (6 * 1024 * 1024),
                                   content_type='application/pdf'),
            ]
            res = self.client.post(
                reverse('document-collection'),
                {'files': files},
                format='multipart'
            )
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn('Total batch size', str(res.json()))

    # ------------------------------------------------------------------
    # Retry State Machine
    # ------------------------------------------------------------------

    def test_retry_rejected_for_completed_document(self):
        res_up = self._upload_file('done.pdf', b'%PDF-1.4 done content')
        doc = Document.objects.get(id=res_up.json()['document']['id'])
        doc.status = DocumentStatus.COMPLETED
        doc.save()

        res_retry = self.client.post(reverse('document-retry', kwargs={'pk': doc.id}))
        self.assertEqual(res_retry.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot retry document', str(res_retry.json()))

    def test_retry_rejected_when_active_job_exists(self):
        res_up = self._upload_file('busy.pdf', b'%PDF-1.4 busy content')
        doc = Document.objects.get(id=res_up.json()['document']['id'])
        doc.status = DocumentStatus.FAILED
        doc.save()

        ProcessingJob.objects.create(
            document=doc,
            job_type=ProcessingJob.JobType.TEXT_EXTRACTION,
            status=JobStatus.RUNNING,
        )

        res_retry = self.client.post(reverse('document-retry', kwargs={'pk': doc.id}))
        self.assertEqual(res_retry.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Duplicate retry rejected', str(res_retry.json()))

    # ------------------------------------------------------------------
    # Unsupported Formats & Size
    # ------------------------------------------------------------------

    def test_unsupported_format_rejected(self):
        res = self._upload_file('malicious.exe', b'MZ executable payload',
                                'application/x-msdownload')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Unsupported file format', str(res.json()))

    def test_oversized_file_rejected(self):
        large_content = b'%PDF ' + b'0' * (6 * 1024 * 1024)
        res = self._upload_file('oversized.pdf', large_content, 'application/pdf')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('exceeds maximum allowed size', str(res.json()))

    def test_empty_upload_rejected(self):
        res = self._upload_file('empty.pdf', b'', 'application/pdf')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        res_nofile = self.client.post(
            reverse('document-collection'), {}, format='multipart'
        )
        self.assertEqual(res_nofile.status_code, status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------
    # List / Detail / Download / Archive / Delete
    # ------------------------------------------------------------------

    def test_list_documents_pagination_and_filtering(self):
        self._upload_file('alpha_report.pdf', b'%PDF-1.4 alpha', 'application/pdf')
        self._upload_file('beta_stats.csv', b'mine,value\nA,1\n', 'text/csv')

        res = self.client.get(reverse('document-collection'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['count'], 2)
        self.assertIn('results', data)

        res_search = self.client.get(reverse('document-collection'), {'search': 'alpha'})
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        self.assertEqual(res_search.json()['count'], 1)
        self.assertEqual(res_search.json()['results'][0]['original_filename'], 'alpha_report.pdf')

    def test_document_detail(self):
        res_up = self._upload_file('detailed_doc.pdf', b'%PDF-1.4 detailed doc', 'application/pdf')
        doc_id = res_up.json()['document']['id']

        res_detail = self.client.get(reverse('document-detail', kwargs={'pk': doc_id}))
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        data = res_detail.json()
        self.assertEqual(data['id'], doc_id)
        self.assertIn('jobs', data)
        self.assertGreaterEqual(len(data['jobs']), 1)

    def test_document_status_endpoint(self):
        res_up = self._upload_file('status_check.pdf', b'%PDF-1.4 status', 'application/pdf')
        doc_id = res_up.json()['document']['id']

        res_st = self.client.get(reverse('document-status', kwargs={'pk': doc_id}))
        self.assertEqual(res_st.status_code, status.HTTP_200_OK)
        self.assertEqual(res_st.json()['status'], DocumentStatus.UPLOADED)

    def test_document_download(self):
        content = b'%PDF-1.4 Real raw content for download test.'
        res_up = self._upload_file('download_test.pdf', content, 'application/pdf')
        doc_id = res_up.json()['document']['id']

        res_dl = self.client.get(reverse('document-download', kwargs={'pk': doc_id}))
        self.assertEqual(res_dl.status_code, status.HTTP_200_OK)
        self.assertEqual(res_dl.content, content)
        self.assertIn('attachment;', res_dl['Content-Disposition'])

    def test_document_retry_success(self):
        res_up = self._upload_file('retry_test.pdf', b'%PDF-1.4 retry content', 'application/pdf')
        doc = Document.objects.get(id=res_up.json()['document']['id'])
        ProcessingJob.objects.filter(document=doc).update(status=JobStatus.FAILED)
        doc.status = DocumentStatus.FAILED
        doc.error_message = 'Simulated OCR error'
        doc.save()

        res_retry = self.client.post(reverse('document-retry', kwargs={'pk': doc.id}))
        self.assertEqual(res_retry.status_code, status.HTTP_200_OK)
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.QUEUED)
        self.assertEqual(doc.error_message, '')

    def test_document_archive_and_hard_delete(self):
        res_up = self._upload_file('delete_me.pdf', b'%PDF-1.4 delete me', 'application/pdf')
        doc_id = res_up.json()['document']['id']
        doc = Document.objects.get(id=doc_id)
        storage_key = doc.storage_key

        res_arch = self.client.post(reverse('document-archive', kwargs={'pk': doc_id}))
        self.assertEqual(res_arch.status_code, status.HTTP_200_OK)
        doc.refresh_from_db()
        self.assertTrue(doc.is_archived)

        res_list = self.client.get(reverse('document-collection'))
        self.assertEqual(res_list.json()['count'], 0)

        res_hard = self.client.delete(
            f"{reverse('document-detail', kwargs={'pk': doc_id})}?hard=true"
        )
        self.assertEqual(res_hard.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Document.objects.filter(id=doc_id).exists())

        storage = get_storage_service()
        self.assertFalse(storage.exists(storage_key))

    def test_multiple_files_upload_ownership(self):
        """Each file in a batch upload is owned by the requesting user."""
        f1 = SimpleUploadedFile('doc1.pdf', b'%PDF-1.4 doc 1',
                                content_type='application/pdf')
        f2 = SimpleUploadedFile('doc2.csv', b'mine,value\nA,1\n',
                                content_type='text/csv')

        res = self.client.post(
            reverse('document-collection'),
            {'files': [f1, f2]},
            format='multipart'
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.json()['uploaded_count'], 2)

        for doc in Document.objects.all():
            self.assertEqual(doc.uploaded_by, self.user)
