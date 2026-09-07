"""
apps.reports.tests.test_reports — Phase 7 Comprehensive Test Suite

Tests:
  - Authentication and owner-scoping (IsAuthenticated, 401/403 protections)
  - Report options endpoint
  - Report generation across all 8 report types from real structured datasets
  - Report content structure: KPIs, tables, trends, narrative, conclusions
  - Provenance integrity (source references, extraction traceability)
  - Safe narrative editing without altering source data (revision count increment)
  - Verification workflow (verified_by, verified_at, state transition)
  - Approval workflow (approved_by, approved_at, notes, state transition)
  - Real file exports: PDF, DOCX, XLSX
  - Failure and error handling (404, invalid format, empty data)
  - Cross-user data isolation
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.reports.models import Report, ReportType, ReportStatus
from apps.documents.models import Document, DocumentStatus
from apps.datasets.models import StructuredDataset, StructuredRecord
from apps.pipeline.models import ExtractionProvenance
from apps.audit.models import AuditEvent

User = get_user_model()


class ReportGeneratorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('analyst_user', 'analyst@cmpdi.local', 'password123')
        self.other_user = User.objects.create_user('other_user', 'other@cmpdi.local', 'password123')

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create sample document and structured dataset for testing
        self.doc = Document.objects.create(
            title='SECL_MCL_Production_FY24.xlsx',
            original_filename='SECL_MCL_Production_FY24.xlsx',
            uploaded_by=self.user,
            status=DocumentStatus.COMPLETED,
        )

        self.dataset = StructuredDataset.objects.create(
            name='SECL & MCL Coal Production FY24',
            source_document=self.doc,
            schema_json={
                'columns': ['subsidiary', 'mine', 'coalfield', 'state', 'financial_year', 'coal_type', 'grade', 'production', 'target', 'dispatch'],
                'extractor_type': 'xlsx',
            },
        )

        # Create structured records with realistic numbers
        self.r1 = StructuredRecord.objects.create(
            dataset=self.dataset,
            row_index=1,
            data_json={
                'subsidiary': 'SECL',
                'mine': 'Gevra OC',
                'coalfield': 'Korba',
                'state': 'Chhattisgarh',
                'financial_year': '2023-24',
                'coal_type': 'Non-Coking',
                'grade': 'G10',
                'production': 52.5,
                'target': 50.0,
                'dispatch': 51.8,
            },
            is_valid=True,
        )

        self.r2 = StructuredRecord.objects.create(
            dataset=self.dataset,
            row_index=2,
            data_json={
                'subsidiary': 'MCL',
                'mine': 'Bhubaneswari OC',
                'coalfield': 'Talcher',
                'state': 'Odisha',
                'financial_year': '2023-24',
                'coal_type': 'Non-Coking',
                'grade': 'G11',
                'production': 31.0,
                'target': 30.0,
                'dispatch': 30.5,
            },
            is_valid=True,
        )

        # Create extraction provenance for traceable audit
        ExtractionProvenance.objects.create(
            record=self.r1,
            document=self.doc,
            extraction_method='xlsx',
            confidence=1.0,
            sheet_name='SECL_Data',
            row_index=1,
            source_reference='Row 1, Sheet: SECL_Data',
        )
        ExtractionProvenance.objects.create(
            record=self.r2,
            document=self.doc,
            extraction_method='xlsx',
            confidence=1.0,
            sheet_name='MCL_Data',
            row_index=2,
            source_reference='Row 2, Sheet: MCL_Data',
        )

    # 1. Authentication & Options
    def test_unauthenticated_access_blocked(self):
        anon_client = APIClient()
        res = anon_client.get('/api/reports/list/')
        self.assertIn(res.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

        res = anon_client.post('/api/reports/generate/', {})
        self.assertIn(res.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_report_options_endpoint(self):
        res = self.client.get('/api/reports/options/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn('report_types', data)
        self.assertEqual(len(data['report_types']), 8)
        self.assertIn('datasets', data)
        self.assertEqual(len(data['datasets']), 1)
        self.assertEqual(data['datasets'][0]['name'], 'SECL & MCL Coal Production FY24')

    # 2. Generation of Production Report
    def test_generate_production_report(self):
        payload = {
            'report_type': ReportType.PRODUCTION,
            'organization': 'CMPDI (HQ)',
            'date_range': 'FY 2023-24',
            'source_dataset_ids': [self.dataset.id],
        }
        res = self.client.post('/api/reports/generate/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.json()

        self.assertEqual(data['status'], ReportStatus.GENERATED)
        self.assertEqual(data['report_type'], ReportType.PRODUCTION)
        content = data['content_json']
        self.assertIn('executive_summary', content)
        self.assertIn('kpis', content)
        self.assertIn('tables', content)

        # Verify exact mathematical calculations from real records (52.5 + 31.0 = 83.5 MT)
        kpis = {k['label']: k['value'] for k in content['kpis']}
        self.assertEqual(kpis['Total Production'], '83.5 MT')
        self.assertEqual(kpis['Total Dispatch'], '82.3 MT')
        self.assertEqual(kpis['Target Achievement'], '104.38%')

        # Verify provenance was captured
        self.assertTrue(len(data['provenance_json']) >= 2)
        prov_sources = [p['name'] for p in data['provenance_json']]
        self.assertIn('SECL & MCL Coal Production FY24', prov_sources)

    # 3. Generation across all 8 report types
    def test_all_eight_report_types_generation(self):
        all_types = [
            ReportType.PRODUCTION,
            ReportType.GEOLOGICAL_EXPLORATION,
            ReportType.MINING_PERFORMANCE,
            ReportType.EXPLORATION,
            ReportType.COAL_SEAM,
            ReportType.PARLIAMENTARY_QUESTION,
            ReportType.ADMINISTRATIVE_QUERY,
            ReportType.CUSTOM,
        ]

        for r_type in all_types:
            payload = {
                'report_type': r_type,
                'organization': 'SECL',
                'date_range': 'FY 2023-24',
            }
            res = self.client.post('/api/reports/generate/', payload, format='json')
            self.assertEqual(res.status_code, status.HTTP_201_CREATED, f"Failed for report type {r_type}")
            d = res.json()
            self.assertEqual(d['status'], ReportStatus.GENERATED)
            self.assertIn('executive_summary', d['content_json'])
            self.assertTrue(len(d['content_json']['kpis']) > 0)

    # 4. Lifecycle: Review -> Edit -> Verify -> Approve
    def test_report_review_edit_verify_approve_workflow(self):
        # 1. Generate
        res = self.client.post('/api/reports/generate/', {
            'report_type': ReportType.PRODUCTION,
            'organization': 'SECL',
        }, format='json')
        rep_id = res.json()['id']

        # 2. Edit narrative (safe edit without altering underlying records)
        orig_r1_prod = StructuredRecord.objects.get(id=self.r1.id).data_json['production']
        edit_res = self.client.patch(f'/api/reports/{rep_id}/edit/', {
            'executive_summary': 'Updated executive review remarks by authorized mining engineer.',
            'analysis': 'Detailed operational analysis updated.',
        }, format='json')
        self.assertEqual(edit_res.status_code, status.HTTP_200_OK)
        edit_data = edit_res.json()
        self.assertEqual(edit_data['status'], ReportStatus.UNDER_REVIEW)
        self.assertEqual(edit_data['revision_count'], 1)
        self.assertEqual(edit_data['content_json']['executive_summary'], 'Updated executive review remarks by authorized mining engineer.')

        # Verify underlying source record remained unchanged!
        refreshed_r1_prod = StructuredRecord.objects.get(id=self.r1.id).data_json['production']
        self.assertEqual(orig_r1_prod, refreshed_r1_prod)

        # 3. Verify
        ver_res = self.client.post(f'/api/reports/{rep_id}/verify/')
        self.assertEqual(ver_res.status_code, status.HTTP_200_OK)
        ver_data = ver_res.json()
        self.assertEqual(ver_data['status'], ReportStatus.VERIFIED)
        self.assertIsNotNone(ver_data['verified_at'])
        self.assertEqual(ver_data['verified_by_name'], self.user.username)

        # 4. Approve
        app_res = self.client.post(f'/api/reports/{rep_id}/approve/', {
            'notes': 'Formally approved for ministry distribution.',
        }, format='json')
        self.assertEqual(app_res.status_code, status.HTTP_200_OK)
        app_data = app_res.json()
        self.assertEqual(app_data['status'], ReportStatus.APPROVED)
        self.assertIsNotNone(app_data['approved_at'])
        self.assertEqual(app_data['approved_by_name'], self.user.username)
        self.assertEqual(app_data['approval_notes'], 'Formally approved for ministry distribution.')

    # 5. Real Exports: PDF, DOCX, XLSX
    def test_export_pdf(self):
        res = self.client.post('/api/reports/generate/', {'report_type': ReportType.PRODUCTION})
        rep_id = res.json()['id']

        export_res = self.client.get(f'/api/reports/{rep_id}/export/pdf/')
        self.assertEqual(export_res.status_code, status.HTTP_200_OK)
        self.assertEqual(export_res['Content-Type'], 'application/pdf')
        self.assertTrue(export_res.content.startswith(b'%PDF'))
        self.assertTrue(len(export_res.content) > 1000)

        # Verify status transitioned to EXPORTED
        rep = Report.objects.get(id=rep_id)
        self.assertEqual(rep.status, ReportStatus.EXPORTED)
        self.assertEqual(rep.export_format, 'PDF')

    def test_export_docx(self):
        res = self.client.post('/api/reports/generate/', {'report_type': ReportType.PARLIAMENTARY_QUESTION})
        rep_id = res.json()['id']

        export_res = self.client.get(f'/api/reports/{rep_id}/export/docx/')
        self.assertEqual(export_res.status_code, status.HTTP_200_OK)
        self.assertIn('wordprocessingml', export_res['Content-Type'])
        self.assertTrue(export_res.content.startswith(b'PK')) # DOCX is a zip archive
        self.assertTrue(len(export_res.content) > 1000)

    def test_export_xlsx(self):
        res = self.client.post('/api/reports/generate/', {'report_type': ReportType.MINING_PERFORMANCE})
        rep_id = res.json()['id']

        export_res = self.client.get(f'/api/reports/{rep_id}/export/xlsx/')
        self.assertEqual(export_res.status_code, status.HTTP_200_OK)
        self.assertIn('spreadsheetml', export_res['Content-Type'])
        self.assertTrue(export_res.content.startswith(b'PK')) # XLSX is a zip archive
        self.assertTrue(len(export_res.content) > 1000)

    # 6. Multi-Tenancy & Cross-User Security Isolation
    def test_cross_user_isolation(self):
        # Generate report as user 1
        res = self.client.post('/api/reports/generate/', {'report_type': ReportType.PRODUCTION})
        rep_id = res.json()['id']

        # Switch to user 2
        other_client = APIClient()
        other_client.force_authenticate(user=self.other_user)

        # Cannot view user 1's report
        res_view = other_client.get(f'/api/reports/{rep_id}/')
        self.assertEqual(res_view.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot edit user 1's report
        res_edit = other_client.patch(f'/api/reports/{rep_id}/edit/', {'executive_summary': 'Hacked'})
        self.assertEqual(res_edit.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot approve user 1's report
        res_app = other_client.post(f'/api/reports/{rep_id}/approve/', {})
        self.assertEqual(res_app.status_code, status.HTTP_403_FORBIDDEN)

        # Cannot export user 1's report
        res_exp = other_client.get(f'/api/reports/{rep_id}/export/pdf/')
        self.assertEqual(res_exp.status_code, status.HTTP_403_FORBIDDEN)

        # User 2 list should not contain user 1's reports
        res_list = other_client.get('/api/reports/list/')
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(res_list.json()['count'], 0)

    # 7. Audit Trail Logging
    def test_audit_event_logged(self):
        res = self.client.post('/api/reports/generate/', {'report_type': ReportType.PRODUCTION})
        rep_id = res.json()['id']

        events = AuditEvent.objects.filter(metadata_json__report_id=rep_id)
        self.assertTrue(events.exists())
        self.assertEqual(events.first().actor, self.user.username)

    # 8. Error Handling & Edge Cases
    def test_invalid_export_format_returns_bad_request(self):
        res = self.client.post('/api/reports/generate/', {'report_type': ReportType.PRODUCTION})
        rep_id = res.json()['id']

        exp_res = self.client.get(f'/api/reports/{rep_id}/export/unsupported_format/')
        self.assertEqual(exp_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', exp_res.json())

    def test_report_not_found_returns_404(self):
        res = self.client.get('/api/reports/999999/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        res_edit = self.client.patch('/api/reports/999999/edit/', {'executive_summary': 'test'})
        self.assertEqual(res_edit.status_code, status.HTTP_404_NOT_FOUND)

    def test_subsidiary_filter_isolates_records(self):
        # Generate report filtered to SECL only
        res = self.client.post('/api/reports/generate/', {
            'report_type': ReportType.PRODUCTION,
            'organization': 'SECL',
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        content = res.json()['content_json']
        kpis = {k['label']: k['value'] for k in content['kpis']}
        # Only SECL record (52.5 MT) should be included, not MCL (31.0 MT)
        self.assertEqual(kpis['Total Production'], '52.5 MT')
        self.assertEqual(kpis['Total Dispatch'], '51.8 MT')

    def test_empty_dataset_fallback(self):
        # Empty dataset with no matching records
        empty_ds = StructuredDataset.objects.create(
            name='Empty Dataset',
            source_document=self.doc,
        )
        res = self.client.post('/api/reports/generate/', {
            'report_type': ReportType.PRODUCTION,
            'organization': 'NonExistentSubsidiary',
            'source_dataset_ids': [empty_ds.id],
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        content = res.json()['content_json']
        self.assertIn('No verified production records were found', content['executive_summary'])

    def test_delete_report(self):
        res = self.client.post('/api/reports/generate/', {'report_type': ReportType.PRODUCTION})
        rep_id = res.json()['id']

        del_res = self.client.delete(f'/api/reports/{rep_id}/')
        self.assertEqual(del_res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Report.objects.filter(id=rep_id).exists())

    def test_empty_dataset_fallback_no_dummy_rows(self):
        empty_doc = Document.objects.create(
            title='Empty.xlsx',
            original_filename='Empty.xlsx',
            uploaded_by=self.user,
            status=DocumentStatus.COMPLETED,
        )
        empty_ds = StructuredDataset.objects.create(
            name='Empty Dataset for Audit',
            source_document=empty_doc,
        )
        types_to_test = [
            ReportType.COAL_SEAM,
            ReportType.EXPLORATION,
            ReportType.PARLIAMENTARY_QUESTION,
            ReportType.ADMINISTRATIVE_QUERY,
            ReportType.CUSTOM,
        ]
        for r_type in types_to_test:
            res = self.client.post('/api/reports/generate/', {
                'report_type': r_type,
                'organization': 'NonExistentUnit',
                'source_dataset_ids': [empty_ds.id],
            }, format='json')
            self.assertEqual(res.status_code, status.HTTP_201_CREATED)
            content = res.json()['content_json']
            self.assertEqual(content['tables'], [], f"Report {r_type} generated fake table rows on empty data!")

    def test_verify_and_approve_rejected_on_failed_report(self):
        rep = Report.objects.create(
            title='Failed Report',
            report_type=ReportType.PRODUCTION,
            status=ReportStatus.FAILED,
            created_by=self.user,
        )
        ver_res = self.client.post(f'/api/reports/{rep.id}/verify/')
        self.assertEqual(ver_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot verify', ver_res.json()['error'])

        app_res = self.client.post(f'/api/reports/{rep.id}/approve/', {'notes': 'Test'})
        self.assertEqual(app_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot approve', app_res.json()['error'])
