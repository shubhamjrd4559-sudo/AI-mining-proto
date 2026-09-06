"""
apps.analytics.tests — Comprehensive Automated Test Suite (Phase 6)

Covers:
  1. Authenticated Data Explorer access
  2. Owner-only dataset access
  3. Cross-user access blocked (403)
  4. Dynamic column discovery (schema endpoint)
  5. Dataset selection
  6. XLSX sheet selection / filtering
  7. Global text search
  8. Field-specific filtering
  9. Safe sorting (asc/desc)
  10. Server-side pagination & metadata
  11. Record detail with normalized & original values
  12. Provenance retrieval
  13. SUM aggregation
  14. AVG aggregation
  15. MIN aggregation
  16. MAX aggregation
  17. COUNT aggregation
  18. Grouped analytics by dimension
  19. Financial-year filtering & chronological sorting
  20. Monthly / reporting-period filtering
  21. Time-series trend analytics
  22. Target vs achievement calculations
  23. Data-quality filtering (exclusion of ERROR records)
  24. Invalid field handling (safe rejection)
  25. Empty result handling
  26. Analytics API endpoints (kpi, trends, breakdown, query, drilldown)
  27. Data Explorer API endpoints (list, schema, records, detail)
  28. P2 CSV export of filtered records
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.documents.models import Document, DocumentStatus
from apps.datasets.models import StructuredDataset, StructuredRecord
from apps.pipeline.models import ExtractionProvenance, ValidationResult
from apps.maintainer.models import MaintainerSuggestion, SuggestionStatus
from apps.analytics.query_engine import AnalyticsQueryEngine, parse_financial_year, parse_numeric

User = get_user_model()


class AnalyticsAndExplorerTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Users
        self.owner = User.objects.create_user(username='owner', password='password123')
        self.other_user = User.objects.create_user(username='other_user', password='password123')

        # Document
        self.doc = Document.objects.create(
            title='CMPDI_Annual_Production_2025.xlsx',
            uploaded_by=self.owner,
            original_filename='CMPDI_Annual_Production_2025.xlsx',
            file_extension='.xlsx',
            status=DocumentStatus.COMPLETED,
        )

        # Dataset
        schema = {
            'columns': ['subsidiary', 'mine', 'financial_year', 'reporting_period', 'grade', 'production', 'target', 'dispatch'],
            'column_map': {
                'subsidiary': {'concept': 'subsidiary', 'confidence': 1.0},
                'mine': {'concept': 'mine', 'confidence': 1.0},
                'financial_year': {'concept': 'financial_year', 'confidence': 1.0},
                'reporting_period': {'concept': 'reporting_period', 'confidence': 1.0},
                'grade': {'concept': 'grade', 'confidence': 1.0},
                'production': {'concept': 'production', 'confidence': 1.0},
                'target': {'concept': 'target', 'confidence': 1.0},
                'dispatch': {'concept': 'dispatch', 'confidence': 1.0},
            }
        }
        self.dataset = StructuredDataset.objects.create(
            name='CMPDI Production FY21-FY25',
            description='Test mining dataset',
            source_document=self.doc,
            schema_json=schema,
        )

        # Sample Records
        self.records_data = [
            {'subsidiary': 'BCCL', 'mine': 'Jharia OC', 'financial_year': '2023-24', 'reporting_period': 'Q1', 'grade': 'G6', 'production': 40.0, 'target': 45.0, 'dispatch': 38.0},
            {'subsidiary': 'BCCL', 'mine': 'Moonidih UG', 'financial_year': '2023-24', 'reporting_period': 'Q2', 'grade': 'G8', 'production': 20.0, 'target': 25.0, 'dispatch': 19.0},
            {'subsidiary': 'ECL', 'mine': 'Raniganj OC', 'financial_year': '2023-24', 'reporting_period': 'Q1', 'grade': 'G6', 'production': 35.0, 'target': 30.0, 'dispatch': 34.0},
            {'subsidiary': 'BCCL', 'mine': 'Jharia OC', 'financial_year': '2024-25', 'reporting_period': 'Q1', 'grade': 'G6', 'production': 50.0, 'target': 48.0, 'dispatch': 49.0},
            {'subsidiary': 'SECL', 'mine': 'Gevra OC', 'financial_year': '2024-25', 'reporting_period': 'Q1', 'grade': 'G10', 'production': 60.0, 'target': 55.0, 'dispatch': 58.0},
            # Warning record
            {'subsidiary': 'ECL', 'mine': 'Sonepur UG', 'financial_year': '2024-25', 'reporting_period': 'Q2', 'grade': 'G10', 'production': 5.0, 'target': 10.0, 'dispatch': 4.5},
            # Error record (to test error exclusion)
            {'subsidiary': 'SECL', 'mine': 'Corrupted Mine', 'financial_year': '2024-25', 'reporting_period': 'Q2', 'grade': 'G10', 'production': -10.0, 'target': -5.0, 'dispatch': 0.0},
        ]

        self.records = []
        for i, row in enumerate(self.records_data):
            is_err = (i == len(self.records_data) - 1)
            rec = StructuredRecord.objects.create(
                dataset=self.dataset,
                row_index=i + 1,
                data_json=row,
                is_valid=not is_err,
                validation_errors=[{'issue_type': 'invalid_numeric', 'severity': 'ERROR'}] if is_err else [],
            )
            self.records.append(rec)

            sheet_name = 'Sheet_A' if i < 4 else 'Sheet_B'
            ExtractionProvenance.objects.create(
                record=rec,
                document=self.doc,
                sheet_name=sheet_name,
                page_number=1,
                section_heading='Table 1',
                table_reference='tab_1',
                row_index=i + 2,
                extraction_method='xlsx',
                confidence=0.95,
                source_reference=f'doc:{self.doc.id}:sheet:{sheet_name}:row:{i + 2}',
            )

        # Create validation results
        ValidationResult.objects.create(
            document=self.doc,
            record=self.records[5],
            field_name='production',
            issue_type='suspicious_value',
            severity='WARNING',
            original_value='5.0',
            suggested_value='5.0',
            explanation='Production exceptionally low.',
        )
        ValidationResult.objects.create(
            document=self.doc,
            record=self.records[6],
            field_name='production',
            issue_type='invalid_numeric',
            severity='ERROR',
            original_value='-10.0',
            suggested_value='0.0',
            explanation='Negative production is invalid.',
        )

        self.dataset.record_count = len(self.records)
        self.dataset.save()

    # 1. Authenticated access & 2. Owner-only dataset access
    def test_unauthenticated_access_denied(self):
        """Data Explorer and Analytics endpoints must reject unauthenticated requests (401)."""
        urls = [
            reverse('api-datasets-list'),
            reverse('api-dataset-schema', args=[self.dataset.id]),
            reverse('api-dataset-records', args=[self.dataset.id]),
            reverse('analytics-kpi') + f'?dataset_id={self.dataset.id}',
            reverse('analytics-trends') + f'?dataset_id={self.dataset.id}',
            reverse('analytics-breakdown') + f'?dataset_id={self.dataset.id}',
            reverse('analytics-query') + f'?dataset_id={self.dataset.id}',
        ]
        for url in urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED, f"Failed on {url}")

    # 3. Cross-user access blocked
    def test_cross_user_access_blocked(self):
        """A user cannot access another user's dataset (403 Forbidden)."""
        self.client.force_authenticate(user=self.other_user)
        urls = [
            reverse('api-dataset-schema', args=[self.dataset.id]),
            reverse('api-dataset-records', args=[self.dataset.id]),
            reverse('api-dataset-record-detail', args=[self.dataset.id, self.records[0].id]),
            reverse('analytics-kpi') + f'?dataset_id={self.dataset.id}',
            reverse('analytics-trends') + f'?dataset_id={self.dataset.id}',
            reverse('analytics-breakdown') + f'?dataset_id={self.dataset.id}',
            reverse('analytics-query') + f'?dataset_id={self.dataset.id}',
        ]
        for url in urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN, f"Failed on {url}")

    # 4. Dynamic column discovery
    def test_dynamic_column_discovery(self):
        """Schema endpoint discovers columns, types, and filter values."""
        self.client.force_authenticate(user=self.owner)
        url = reverse('api-dataset-schema', args=[self.dataset.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        col_names = [c['name'] for c in data['columns']]
        self.assertIn('subsidiary', col_names)
        self.assertIn('production', col_names)
        self.assertIn('financial_year', col_names)
        self.assertIn('BCCL', data['filters']['subsidiary'])
        self.assertIn('Sheet_A', data['sheets'])

    # 5. Dataset selection
    def test_dataset_list(self):
        """Dataset list endpoint returns owner datasets."""
        self.client.force_authenticate(user=self.owner)
        res = self.client.get(reverse('api-datasets-list'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(len(data['datasets']), 1)
        self.assertEqual(data['datasets'][0]['id'], self.dataset.id)

    # 6. XLSX sheet selection
    def test_sheet_filtering(self):
        """Filtering by sheet returns only records from that sheet."""
        self.client.force_authenticate(user=self.owner)
        url = reverse('api-dataset-records', args=[self.dataset.id]) + '?sheet=Sheet_A'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['total_records'], 4)

    # 7. Search
    def test_search_filtering(self):
        """Global search query matches text inside data_json."""
        self.client.force_authenticate(user=self.owner)
        url = reverse('api-dataset-records', args=[self.dataset.id]) + '?search=Moonidih'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['total_records'], 1)
        self.assertEqual(data['rows'][0]['data']['mine'], 'Moonidih UG')

    # 8. Field-specific filtering
    def test_field_specific_filtering(self):
        """Dynamic filter by subsidiary returns only matching rows."""
        self.client.force_authenticate(user=self.owner)
        url = reverse('api-dataset-records', args=[self.dataset.id]) + '?subsidiary=BCCL'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['total_records'], 3)
        for r in data['rows']:
            self.assertEqual(r['data']['subsidiary'], 'BCCL')

    # 9. Sorting
    def test_safe_sorting(self):
        """Sorting by production desc orders rows properly."""
        self.client.force_authenticate(user=self.owner)
        url = reverse('api-dataset-records', args=[self.dataset.id]) + '?sort_by=production&sort_dir=desc'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        rows = res.json()['rows']
        prods = [r['data']['production'] for r in rows if r['data']['production'] is not None]
        self.assertEqual(prods, sorted(prods, reverse=True))

    # 10. Pagination
    def test_pagination(self):
        """Pagination returns bounded pages and total_pages metadata."""
        self.client.force_authenticate(user=self.owner)
        url = reverse('api-dataset-records', args=[self.dataset.id]) + '?page=1&page_size=3'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(len(data['rows']), 3)
        self.assertEqual(data['page'], 1)
        self.assertEqual(data['page_size'], 3)
        self.assertEqual(data['total_records'], 7)
        self.assertEqual(data['total_pages'], 3)

    # 11. Record detail & 12. Provenance retrieval
    def test_record_detail_and_provenance(self):
        """Detail endpoint returns normalized fields, validation warnings, and extraction provenance."""
        self.client.force_authenticate(user=self.owner)
        rec = self.records[5]  # record with warning
        url = reverse('api-dataset-record-detail', args=[self.dataset.id, rec.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['record_id'], rec.id)
        self.assertTrue(len(data['fields']) > 0)
        self.assertTrue(len(data['provenance']) > 0)
        self.assertEqual(data['provenance'][0]['sheet_name'], 'Sheet_B')
        self.assertEqual(len(data['validation_findings']), 1)
        self.assertEqual(data['validation_findings'][0]['severity'], 'WARNING')

    # 13. SUM, 14. AVG, 15. MIN, 16. MAX, 17. COUNT
    def test_core_aggregations(self):
        """Query engine calculates SUM, AVG, MIN, MAX, COUNT accurately excluding errors."""
        engine = AnalyticsQueryEngine(self.dataset)

        sum_res = engine.execute_query(aggregation='sum', metric='production', exclude_errors=True)
        # Valid productions: 40 + 20 + 35 + 50 + 60 + 5 = 210.0
        self.assertEqual(sum_res['result'], 210.0)

        avg_res = engine.execute_query(aggregation='avg', metric='production', exclude_errors=True)
        self.assertEqual(avg_res['result'], round(210.0 / 6, 2))

        min_res = engine.execute_query(aggregation='min', metric='production', exclude_errors=True)
        self.assertEqual(min_res['result'], 5.0)

        max_res = engine.execute_query(aggregation='max', metric='production', exclude_errors=True)
        self.assertEqual(max_res['result'], 60.0)

        count_res = engine.execute_query(aggregation='count', metric='production', exclude_errors=True)
        self.assertEqual(count_res['result'], 6.0)

    # 18. Grouped analytics
    def test_grouped_analytics(self):
        """Grouped query aggregates metric per group."""
        engine = AnalyticsQueryEngine(self.dataset)
        res = engine.execute_query(aggregation='sum', metric='production', group_by='subsidiary')
        grp_map = {item['group']: item['value'] for item in res['series']}
        # BCCL: 40 + 20 + 50 = 110.0
        self.assertEqual(grp_map['BCCL'], 110.0)
        # ECL: 35 + 5 = 40.0
        self.assertEqual(grp_map['ECL'], 40.0)
        # SECL: 60.0 (error row with -10 excluded)
        self.assertEqual(grp_map['SECL'], 60.0)

    # 19. Financial-year filtering & 20. Reporting-period filtering
    def test_financial_year_and_reporting_period_filters(self):
        """Filtering by FY and reporting period selects exact records."""
        engine = AnalyticsQueryEngine(self.dataset)

        fy_filtered = engine.filter_records(filters={'financial_year': '2023-24'})
        self.assertEqual(len(fy_filtered), 3)

        rp_filtered = engine.filter_records(filters={'reporting_period': 'Q2'})
        # Q2 has Moonidih (2023-24) and Sonepur (2024-25) and Corrupted Mine (error excluded)
        self.assertEqual(len(rp_filtered), 2)

    # 21. Trend analytics & 22. Target vs achievement
    def test_trend_analytics_and_achievement(self):
        """Trends API sorts FY chronologically and computes achievement %."""
        self.client.force_authenticate(user=self.owner)
        url = reverse('analytics-trends') + f'?dataset_id={self.dataset.id}&metric=production&time_field=financial_year'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        series = data['series']
        self.assertEqual(len(series), 2)
        # Chronological FY: 2023-24 before 2024-25
        self.assertEqual(series[0]['period'], '2023-24')
        self.assertEqual(series[1]['period'], '2024-25')
        self.assertTrue('achievement_pct' in series[0])
        # YoY growth from FY23-24 to FY24-25
        self.assertTrue('growth_pct' in series[1])

    # 23. Data-quality filtering
    def test_data_quality_exclusion_and_kpis(self):
        """KPIs calculate data quality summary and exclude ERROR records."""
        self.client.force_authenticate(user=self.owner)
        url = reverse('analytics-kpi') + f'?dataset_id={self.dataset.id}'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        kpis = data['kpis']
        self.assertEqual(kpis['total_production'], 210.0)  # -10 excluded
        self.assertEqual(kpis['quality']['error_count'], 1)
        self.assertEqual(kpis['quality']['warning_count'], 1)
        self.assertEqual(kpis['mine_count'], 5)  # Jharia, Moonidih, Raniganj, Gevra, Sonepur (5 valid mines)

    # 24. Invalid field handling
    def test_invalid_field_handled_safely(self):
        """Query with non-existent field returns 400 without unhandled 500 or SQL injection."""
        self.client.force_authenticate(user=self.owner)
        url = reverse('analytics-breakdown') + f'?dataset_id={self.dataset.id}&group_by=malicious_col%27;DROP+TABLE'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not present in dataset schema', res.json()['error'])

    # 25. Empty result handling
    def test_empty_result_handling(self):
        """Query matching zero rows returns clean empty structure without crash."""
        self.client.force_authenticate(user=self.owner)
        url = reverse('analytics-breakdown') + f'?dataset_id={self.dataset.id}&group_by=subsidiary&subsidiary=NON_EXISTENT'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()['series'], [])

    # 26. Analytics API breakdown & drilldown
    def test_drilldown_endpoint(self):
        """Drilldown returns full record and provenance for specified IDs."""
        self.client.force_authenticate(user=self.owner)
        rec_ids = f"{self.records[0].id},{self.records[1].id}"
        url = reverse('analytics-drilldown') + f'?dataset_id={self.dataset.id}&record_ids={rec_ids}'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['total_count'], 2)
        self.assertEqual(data['records'][0]['record_id'], self.records[0].id)
        self.assertTrue(len(data['records'][0]['provenance']) > 0)

    # 27. P2 CSV export verification
    def test_csv_export(self):
        """Filtered CSV export streams valid CSV text."""
        self.client.force_authenticate(user=self.owner)
        url = reverse('api-dataset-export-csv', args=[self.dataset.id]) + '?subsidiary=BCCL'
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'text/csv; charset=utf-8')
        content = res.content.decode('utf-8')
        self.assertIn('subsidiary', content)
        self.assertIn('BCCL', content)
        self.assertNotIn('SECL', content)
