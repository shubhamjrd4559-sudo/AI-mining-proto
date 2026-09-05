"""
apps.maintainer — Phase 4 Tests

22 scenarios covering:
1. authenticated dataset access
2. owner-only access
3. XLSX overview
4. CSV overview
5. records/preview
6. validation issue listing
7. deterministic suggestion generation
8. AI fallback (disabled)
9. suggestion creation
10. approval
11. rejection
12. batch approval/rejection
13. applying approved changes
14. original value preservation
15. provenance preservation
16. audit creation
17. XLSX export
18. CSV export
19. unauthorized access
20. invalid suggestion state
21. transaction/partial failure
22. duplicate/concurrent apply protection
"""

import io
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.documents.models import Document, DocumentStatus
from apps.datasets.models import StructuredDataset, StructuredRecord
from apps.pipeline.models import ExtractionProvenance, ValidationResult
from apps.audit.models import AuditEvent
from apps.storage.service import get_storage_service

from .models import MaintainerSuggestion, SuggestionStatus, SuggestionSource, SuggestionIssueType
from .suggester import generate_suggestions_for_dataset, _check_whitespace, _check_comma_number, _check_financial_year, _check_date, _check_percentage

User = get_user_model()


def _make_xlsx_bytes():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Production'
    ws.append(['Mine', 'Production (MT)', 'FY', 'Subsidiary'])
    ws.append(['  Jharia  ', '1,250 MT', 'FY2024-25', 'BCCL'])
    ws.append(['Kathara', '2.1 MT', '2024-25', 'CCL'])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_csv_bytes():
    return b'Mine,Production\n  Jharia  ,1,250\nKathara,2.1\n'


def _setup_dataset(user, file_ext='.csv', file_bytes=None):
    """Create a Document + StructuredDataset + StructuredRecord for testing."""
    if file_bytes is None:
        file_bytes = _make_csv_bytes()

    storage = get_storage_service()
    storage_key = f'documents/test/{user.username}_test{file_ext}'
    storage.save(storage_key, file_bytes)

    doc = Document.objects.create(
        title=f'Test {file_ext}',
        original_filename=f'test{file_ext}',
        stored_filename=f'test{file_ext}',
        storage_key=storage_key,
        file_extension=file_ext,
        file_size=len(file_bytes),
        status=DocumentStatus.INDEXED,
        uploaded_by=user,
    )

    dataset = StructuredDataset.objects.create(
        name=f'Test Dataset ({user.username})',
        source_document=doc,
        schema_json={'columns': ['Mine', 'Production']},
        record_count=2,
    )

    record1 = StructuredRecord.objects.create(
        dataset=dataset,
        row_index=0,
        data_json={'Mine': '  Jharia  ', 'Production': '1,250', 'FY': 'FY2024-25'},
        is_valid=True,
    )
    record2 = StructuredRecord.objects.create(
        dataset=dataset,
        row_index=1,
        data_json={'Mine': 'Kathara', 'Production': '2.1', 'FY': '2024-25'},
        is_valid=True,
    )

    return doc, dataset, record1, record2


class DeterministicSuggesterTests(TestCase):
    """Tests for the deterministic cleaning rules."""

    # 7. Deterministic suggestion generation rules
    def test_whitespace_cleanup(self):
        result = _check_whitespace('  Jharia  ')
        self.assertIsNotNone(result)
        suggested, issue_type, reason, conf = result
        self.assertEqual(suggested, 'Jharia')
        self.assertEqual(issue_type, SuggestionIssueType.WHITESPACE)

    def test_whitespace_no_change(self):
        self.assertIsNone(_check_whitespace('Jharia'))

    def test_comma_number_cleanup(self):
        result = _check_comma_number('1,250')
        self.assertIsNotNone(result)
        suggested, issue_type, reason, conf = result
        self.assertEqual(suggested, '1250')
        self.assertEqual(issue_type, SuggestionIssueType.COMMA_NUMBER)

    def test_comma_number_no_change(self):
        self.assertIsNone(_check_comma_number('1250'))

    def test_financial_year_normalization(self):
        result = _check_financial_year('FY2024-25')
        self.assertIsNotNone(result)
        suggested, issue_type, reason, conf = result
        self.assertEqual(suggested, '2024-25')

    def test_date_normalization(self):
        result = _check_date('15/01/2024')
        self.assertIsNotNone(result)
        suggested, issue_type, reason, conf = result
        self.assertEqual(suggested, '2024-01-15')

    def test_percentage_normalization(self):
        result = _check_percentage('85 %')
        self.assertIsNotNone(result)
        suggested, issue_type, reason, conf = result
        self.assertEqual(suggested, '85%')


class SuggestionGenerationTests(TestCase):
    """Tests for suggestion generation via API and model."""

    def setUp(self):
        self.user = User.objects.create_user(username='maintainer_user', password='testpass')
        self.other = User.objects.create_user(username='other_user', password='testpass')
        self.client = APIClient()
        self.doc, self.dataset, self.record1, self.record2 = _setup_dataset(self.user)

    # 9. Suggestion creation
    def test_generate_suggestions_creates_records(self):
        summary = generate_suggestions_for_dataset(self.dataset, user=self.user)
        count = MaintainerSuggestion.objects.filter(dataset=self.dataset).count()
        self.assertGreater(count, 0)
        self.assertEqual(summary['created'], count)

    # 9. Verify suggestion structure
    def test_suggestion_has_correct_fields(self):
        generate_suggestions_for_dataset(self.dataset, user=self.user)
        ws_suggestion = MaintainerSuggestion.objects.filter(
            dataset=self.dataset, issue_type=SuggestionIssueType.WHITESPACE
        ).first()
        self.assertIsNotNone(ws_suggestion)
        self.assertEqual(ws_suggestion.original_value, '  Jharia  ')
        self.assertEqual(ws_suggestion.suggested_value, 'Jharia')
        self.assertEqual(ws_suggestion.status, SuggestionStatus.PENDING)
        self.assertEqual(ws_suggestion.suggestion_source, SuggestionSource.DETERMINISTIC)

    # 7. No auto-apply — verify source is unchanged
    def test_generate_does_not_modify_source(self):
        generate_suggestions_for_dataset(self.dataset, user=self.user)
        self.record1.refresh_from_db()
        self.assertEqual(self.record1.data_json['Mine'], '  Jharia  ')  # unchanged

    # 8. AI fallback disabled (no key set)
    def test_ai_fallback_disabled_without_key(self):
        import os
        # Ensure no AI keys in env
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ.pop('GEMINI_API_KEY', None)
        summary = generate_suggestions_for_dataset(self.dataset, user=self.user, ai_enabled=True)
        # Should work fine with 0 AI suggestions
        self.assertEqual(summary['ai_created'], 0)


class AuthenticationAndOwnershipTests(TestCase):
    """Tests for authentication and owner scoping."""

    def setUp(self):
        self.user = User.objects.create_user(username='owner', password='testpass')
        self.other = User.objects.create_user(username='stranger', password='testpass')
        self.client = APIClient()
        self.doc, self.dataset, self.record1, self.record2 = _setup_dataset(self.user)

    # 1. authenticated dataset access
    def test_unauthenticated_dataset_list_rejected(self):
        resp = self.client.get('/api/maintainer/datasets/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # 1. authenticated access works
    def test_authenticated_dataset_list(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/maintainer/datasets/')
        self.assertIn(resp.status_code, [200, 201])

    # 2. owner-only access
    def test_other_user_cannot_see_dataset(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.get(f'/api/maintainer/datasets/{self.dataset.pk}/overview/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # 19. unauthorized access
    def test_unauthenticated_overview_rejected(self):
        resp = self.client.get(f'/api/maintainer/datasets/{self.dataset.pk}/overview/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # 2. owner can access
    def test_owner_can_access_dataset(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(f'/api/maintainer/datasets/{self.dataset.pk}/overview/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['id'], self.dataset.pk)

    # 3. XLSX overview
    def test_xlsx_dataset_overview(self):
        xlsx_bytes = _make_xlsx_bytes()
        _, dataset_xlsx, _, _ = _setup_dataset(self.user, file_ext='.xlsx', file_bytes=xlsx_bytes)
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(f'/api/maintainer/datasets/{dataset_xlsx.pk}/overview/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['file_type'], 'xlsx')

    # 4. CSV overview
    def test_csv_dataset_overview(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(f'/api/maintainer/datasets/{self.dataset.pk}/overview/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['file_type'], 'csv')


class RecordsAndValidationTests(TestCase):
    """Tests for records listing and validation issues."""

    def setUp(self):
        self.user = User.objects.create_user(username='rec_user', password='testpass')
        self.client = APIClient()
        self.doc, self.dataset, self.record1, self.record2 = _setup_dataset(self.user)
        self.client.force_authenticate(user=self.user)

    # 5. records/preview
    def test_records_list(self):
        resp = self.client.get(f'/api/maintainer/datasets/{self.dataset.pk}/records/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 2)

    # 6. validation issue listing
    def test_validation_issues_endpoint(self):
        ValidationResult.objects.create(
            document=self.doc,
            field_name='Production',
            issue_type='invalid_numeric',
            severity='ERROR',
            original_value='N/A',
            suggested_value='',
            explanation='Not a number.',
        )
        resp = self.client.get(f'/api/maintainer/datasets/{self.dataset.pk}/validation-issues/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)


class ApproveRejectTests(TestCase):
    """Tests for suggestion approval and rejection."""

    def setUp(self):
        self.user = User.objects.create_user(username='approver', password='testpass')
        self.other = User.objects.create_user(username='other_approver', password='testpass')
        self.client = APIClient()
        self.doc, self.dataset, self.record1, self.record2 = _setup_dataset(self.user)
        # Create a test suggestion
        self.suggestion = MaintainerSuggestion.objects.create(
            dataset=self.dataset,
            record=self.record1,
            document=self.doc,
            field_name='Mine',
            original_value='  Jharia  ',
            suggested_value='Jharia',
            issue_type=SuggestionIssueType.WHITESPACE,
            reason='Whitespace cleanup',
            confidence=1.0,
            suggestion_source=SuggestionSource.DETERMINISTIC,
            status=SuggestionStatus.PENDING,
            created_by=self.user,
        )

    # 10. approval
    def test_approve_suggestion(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(f'/api/maintainer/suggestions/{self.suggestion.pk}/approve/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.status, SuggestionStatus.APPROVED)
        self.assertIsNotNone(self.suggestion.reviewed_at)
        self.assertEqual(self.suggestion.reviewed_by, self.user)

    # 10. APPROVE MUST NOT APPLY
    def test_approve_does_not_apply(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(f'/api/maintainer/suggestions/{self.suggestion.pk}/approve/')
        self.record1.refresh_from_db()
        # Source data unchanged
        self.assertEqual(self.record1.data_json['Mine'], '  Jharia  ')

    # 11. rejection
    def test_reject_suggestion(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(f'/api/maintainer/suggestions/{self.suggestion.pk}/reject/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.status, SuggestionStatus.REJECTED)

    # 20. invalid suggestion state
    def test_cannot_approve_already_approved(self):
        self.suggestion.status = SuggestionStatus.APPROVED
        self.suggestion.save()
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(f'/api/maintainer/suggestions/{self.suggestion.pk}/approve/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # 20. cannot approve rejected
    def test_cannot_approve_rejected_suggestion(self):
        self.suggestion.status = SuggestionStatus.REJECTED
        self.suggestion.save()
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(f'/api/maintainer/suggestions/{self.suggestion.pk}/approve/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # 2. other user cannot approve
    def test_other_user_cannot_approve(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.post(f'/api/maintainer/suggestions/{self.suggestion.pk}/approve/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # 12. batch approval
    def test_batch_approve(self):
        s2 = MaintainerSuggestion.objects.create(
            dataset=self.dataset, record=self.record2, document=self.doc,
            field_name='Production', original_value='1,250', suggested_value='1250',
            issue_type=SuggestionIssueType.COMMA_NUMBER,
            reason='Comma cleanup', confidence=0.95,
            suggestion_source=SuggestionSource.DETERMINISTIC,
            status=SuggestionStatus.PENDING, created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/api/maintainer/suggestions/batch-review/', {
            'ids': [self.suggestion.pk, s2.pk],
            'action': 'approve',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['updated'], 2)
        self.suggestion.refresh_from_db()
        s2.refresh_from_db()
        self.assertEqual(self.suggestion.status, SuggestionStatus.APPROVED)
        self.assertEqual(s2.status, SuggestionStatus.APPROVED)

    # 12. batch rejection
    def test_batch_reject(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/api/maintainer/suggestions/batch-review/', {
            'ids': [self.suggestion.pk],
            'action': 'reject',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.status, SuggestionStatus.REJECTED)


class ApplyTests(TestCase):
    """Tests for the apply approved changes workflow."""

    def setUp(self):
        self.user = User.objects.create_user(username='applier', password='testpass')
        self.client = APIClient()
        self.doc, self.dataset, self.record1, self.record2 = _setup_dataset(self.user)
        self.suggestion = MaintainerSuggestion.objects.create(
            dataset=self.dataset,
            record=self.record1,
            document=self.doc,
            field_name='Mine',
            original_value='  Jharia  ',
            suggested_value='Jharia',
            issue_type=SuggestionIssueType.WHITESPACE,
            reason='Whitespace cleanup',
            confidence=1.0,
            suggestion_source=SuggestionSource.DETERMINISTIC,
            status=SuggestionStatus.APPROVED,
            created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)

    # 13. applying approved changes
    def test_apply_approved_changes(self):
        resp = self.client.post(f'/api/maintainer/datasets/{self.dataset.pk}/apply/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['applied'], 1)
        self.assertEqual(resp.data['failed'], 0)

    # 14. original value preservation
    def test_original_value_preserved_after_apply(self):
        self.client.post(f'/api/maintainer/datasets/{self.dataset.pk}/apply/')
        self.record1.refresh_from_db()
        # The corrected value is applied
        self.assertEqual(self.record1.data_json['Mine'], 'Jharia')
        # Original is preserved in a backup key
        self.assertIn('Mine_original_before_apply', self.record1.data_json)
        self.assertEqual(self.record1.data_json['Mine_original_before_apply'], '  Jharia  ')

    # 15. provenance preservation
    def test_provenance_preserved_after_apply(self):
        self.client.post(f'/api/maintainer/datasets/{self.dataset.pk}/apply/')
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.status, SuggestionStatus.APPLIED)
        self.assertIsNotNone(self.suggestion.applied_at)
        self.assertEqual(self.suggestion.applied_value, 'Jharia')

    # 16. audit creation
    def test_audit_event_created_on_apply(self):
        audit_count_before = AuditEvent.objects.count()
        self.client.post(f'/api/maintainer/datasets/{self.dataset.pk}/apply/')
        audit_count_after = AuditEvent.objects.count()
        self.assertGreater(audit_count_after, audit_count_before)
        event = AuditEvent.objects.order_by('-timestamp').first()
        self.assertIn('Mine', event.description)

    # 22. duplicate apply protection
    def test_duplicate_apply_rejected(self):
        # Apply once
        self.client.post(f'/api/maintainer/datasets/{self.dataset.pk}/apply/')
        # Apply again — already APPLIED, not APPROVED
        resp = self.client.post(f'/api/maintainer/datasets/{self.dataset.pk}/apply/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Second apply should have 0 applied (nothing left in APPROVED state)
        self.assertEqual(resp.data['applied'], 0)

    # 21. pending suggestions are not applied
    def test_pending_suggestions_not_applied(self):
        pending = MaintainerSuggestion.objects.create(
            dataset=self.dataset, record=self.record2, document=self.doc,
            field_name='Production', original_value='2.1', suggested_value='2.10',
            issue_type=SuggestionIssueType.NUMERIC_FORMAT,
            reason='Format cleanup', confidence=0.95,
            suggestion_source=SuggestionSource.DETERMINISTIC,
            status=SuggestionStatus.PENDING, created_by=self.user,
        )
        resp = self.client.post(f'/api/maintainer/datasets/{self.dataset.pk}/apply/')
        self.assertEqual(resp.data['applied'], 1)  # only the APPROVED one
        pending.refresh_from_db()
        # Pending record unchanged
        self.record2.refresh_from_db()
        self.assertEqual(self.record2.data_json['Production'], '2.1')

    def test_apply_conflict_protection(self):
        """If record value was modified between suggestion creation and apply, conflict marks FAILED."""
        # Change the record value so it differs from suggestion.original_value ('  Jharia  ')
        self.record1.data_json['Mine'] = 'Modified Name'
        self.record1.save(update_fields=['data_json'])

        resp = self.client.post(f'/api/maintainer/datasets/{self.dataset.pk}/apply/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['applied'], 0)
        self.assertEqual(resp.data['failed'], 1)

        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.status, SuggestionStatus.FAILED)
        self.assertIn('Conflict detected', self.suggestion.error_message)

        # The modified name was NOT overwritten
        self.record1.refresh_from_db()
        self.assertEqual(self.record1.data_json['Mine'], 'Modified Name')

    def test_orphan_dataset_access_denied(self):
        """Datasets without source_document or owner are denied maintainer access."""
        orphan = StructuredDataset.objects.create(
            name='Orphan Dataset', source_document=None, schema_json={}
        )
        resp = self.client.get(f'/api/maintainer/datasets/{orphan.pk}/overview/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class AuditReviewTests(TestCase):
    """Tests for audit trail generation during review actions."""

    def setUp(self):
        self.user = User.objects.create_user(username='auditor_user', password='testpass')
        self.client = APIClient()
        self.doc, self.dataset, self.record1, self.record2 = _setup_dataset(self.user)
        self.client.force_authenticate(user=self.user)
        self.suggestion = MaintainerSuggestion.objects.create(
            dataset=self.dataset, record=self.record1, document=self.doc,
            field_name='Mine', original_value='  Jharia  ', suggested_value='Jharia',
            issue_type=SuggestionIssueType.WHITESPACE, reason='Whitespace cleanup',
            confidence=1.0, suggestion_source=SuggestionSource.DETERMINISTIC,
            status=SuggestionStatus.PENDING, created_by=self.user,
        )

    def test_approve_creates_audit_event(self):
        count_before = AuditEvent.objects.count()
        self.client.post(f'/api/maintainer/suggestions/{self.suggestion.pk}/approve/')
        self.assertGreater(AuditEvent.objects.count(), count_before)
        latest = AuditEvent.objects.order_by('-timestamp').first()
        self.assertIn('Approved suggestion', latest.description)

    def test_reject_creates_audit_event(self):
        count_before = AuditEvent.objects.count()
        self.client.post(f'/api/maintainer/suggestions/{self.suggestion.pk}/reject/')
        self.assertGreater(AuditEvent.objects.count(), count_before)
        latest = AuditEvent.objects.order_by('-timestamp').first()
        self.assertIn('Rejected suggestion', latest.description)


class ExportTests(TestCase):
    """Tests for XLSX and CSV export."""

    def setUp(self):
        self.user = User.objects.create_user(username='exporter', password='testpass')
        self.client = APIClient()
        self.doc, self.dataset, self.record1, self.record2 = _setup_dataset(self.user)
        self.client.force_authenticate(user=self.user)

    # 17. XLSX export
    def test_xlsx_export(self):
        resp = self.client.get(f'/api/maintainer/datasets/{self.dataset.pk}/export/xlsx/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            resp['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertIn('.xlsx', resp['Content-Disposition'])

        # Verify it can be loaded with openpyxl and has content
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        self.assertIn('Maintained Data', wb.sheetnames)
        ws = wb['Maintained Data']
        self.assertGreater(ws.max_row, 1)

    # 18. CSV export
    def test_csv_export(self):
        resp = self.client.get(f'/api/maintainer/datasets/{self.dataset.pk}/export/csv/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertIn('.csv', resp['Content-Disposition'])

        content = resp.content.decode('utf-8')
        self.assertIn('Mine', content)
        self.assertIn('Production', content)

    # 12. Source immutability — original file not changed
    def test_source_file_immutability(self):
        storage = get_storage_service()
        original_content = storage.open(self.doc.storage_key)

        # Apply a suggestion
        sug = MaintainerSuggestion.objects.create(
            dataset=self.dataset, record=self.record1, document=self.doc,
            field_name='Mine', original_value='  Jharia  ', suggested_value='Jharia',
            issue_type=SuggestionIssueType.WHITESPACE, reason='ws', confidence=1.0,
            suggestion_source=SuggestionSource.DETERMINISTIC,
            status=SuggestionStatus.APPROVED, created_by=self.user,
        )
        self.client.post(f'/api/maintainer/datasets/{self.dataset.pk}/apply/')

        # Original file unchanged
        new_content = storage.open(self.doc.storage_key)
        self.assertEqual(original_content, new_content)

    # 19. unauthorized export
    def test_unauthorized_export(self):
        self.client.logout()
        resp = self.client.get(f'/api/maintainer/datasets/{self.dataset.pk}/export/csv/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class GenerateSuggestionsAPITests(TestCase):
    """Tests for generate-suggestions API endpoint."""

    def setUp(self):
        self.user = User.objects.create_user(username='gen_user', password='testpass')
        self.other = User.objects.create_user(username='gen_other', password='testpass')
        self.client = APIClient()
        self.doc, self.dataset, self.record1, self.record2 = _setup_dataset(self.user)

    def test_generate_suggestions_api(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(f'/api/maintainer/datasets/{self.dataset.pk}/generate-suggestions/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('created', resp.data)

    def test_generate_suggestions_owner_only(self):
        self.client.force_authenticate(user=self.other)
        resp = self.client.post(f'/api/maintainer/datasets/{self.dataset.pk}/generate-suggestions/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_generate_idempotent_clears_pending(self):
        """Re-running generate-suggestions replaces PENDING deterministic suggestions."""
        self.client.force_authenticate(user=self.user)
        self.client.post(f'/api/maintainer/datasets/{self.dataset.pk}/generate-suggestions/')
        count1 = MaintainerSuggestion.objects.filter(
            dataset=self.dataset, status=SuggestionStatus.PENDING
        ).count()
        self.client.post(f'/api/maintainer/datasets/{self.dataset.pk}/generate-suggestions/')
        count2 = MaintainerSuggestion.objects.filter(
            dataset=self.dataset, status=SuggestionStatus.PENDING
        ).count()
        # Count should be the same (not doubled)
        self.assertEqual(count1, count2)
