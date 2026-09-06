"""
apps.datasets — Tests
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.documents.models import Document, DocumentStatus
from .models import StructuredDataset, StructuredRecord
from apps.pipeline.models import ExtractionProvenance

User = get_user_model()


class DatasetModelTestCase(TestCase):
    def test_dataset_creation(self):
        """StructuredDataset can be created."""
        ds = StructuredDataset.objects.create(
            name='Coal Production 2025',
            schema_json={'columns': ['mine', 'production_mt', 'year']},
        )
        self.assertEqual(ds.name, 'Coal Production 2025')
        self.assertEqual(ds.record_count, 0)

    def test_structured_record_creation(self):
        """StructuredRecord can be created linked to a dataset."""
        ds = StructuredDataset.objects.create(name='Test Dataset')
        record = StructuredRecord.objects.create(
            dataset=ds,
            row_index=0,
            data_json={'mine': 'Jharia', 'production_mt': 4.2},
        )
        self.assertEqual(record.dataset, ds)
        self.assertTrue(record.is_valid)


class DatasetAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_datasets_stub_returns_200(self):
        """GET /api/datasets/ returns 200 with not_implemented in Phase 1."""
        url = reverse('api-datasets')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['status'], 'not_implemented')


class DataExplorerAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='explorer_user', password='password123')
        self.other_user = User.objects.create_user(username='other_explorer_user', password='password123')

        self.doc = Document.objects.create(
            title='MCL_Annual_Report.xlsx',
            uploaded_by=self.user,
            original_filename='MCL_Annual_Report.xlsx',
            file_extension='.xlsx',
            status=DocumentStatus.COMPLETED,
        )

        self.dataset = StructuredDataset.objects.create(
            name='MCL Production Records',
            source_document=self.doc,
            schema_json={
                'columns': ['mine', 'subsidiary', 'production', 'financial_year'],
                'column_map': {
                    'mine': {'concept': 'mine'},
                    'subsidiary': {'concept': 'subsidiary'},
                    'production': {'concept': 'production'},
                    'financial_year': {'concept': 'financial_year'},
                }
            },
            record_count=2,
        )

        self.r1 = StructuredRecord.objects.create(
            dataset=self.dataset,
            row_index=1,
            data_json={'mine': 'Kulda', 'subsidiary': 'MCL', 'production': 25.4, 'financial_year': '2024-25'},
        )
        self.r2 = StructuredRecord.objects.create(
            dataset=self.dataset,
            row_index=2,
            data_json={'mine': 'Basundhara', 'subsidiary': 'MCL', 'production': 18.2, 'financial_year': '2024-25'},
        )

        ExtractionProvenance.objects.create(
            record=self.r1,
            document=self.doc,
            sheet_name='Production',
            page_number=1,
            row_index=2,
            source_reference='doc:1:sheet:Production:row:2',
        )

    def test_list_datasets_authenticated(self):
        """Owner can list their datasets via /api/datasets/list/."""
        self.client.force_authenticate(user=self.user)
        res = self.client.get(reverse('api-datasets-list'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.json()['datasets']), 1)

    def test_schema_discovery(self):
        """Owner can get schema discovery via /api/datasets/<id>/schema/."""
        self.client.force_authenticate(user=self.user)
        res = self.client.get(reverse('api-dataset-schema', args=[self.dataset.id]))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn('columns', data)
        self.assertIn('Production', data['sheets'])

    def test_records_pagination_and_detail(self):
        """Owner can paginate records and view record detail."""
        self.client.force_authenticate(user=self.user)
        records_url = reverse('api-dataset-records', args=[self.dataset.id]) + '?page=1&page_size=1'
        res = self.client.get(records_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.json()['rows']), 1)
        self.assertEqual(res.json()['total_records'], 2)

        detail_url = reverse('api-dataset-record-detail', args=[self.dataset.id, self.r1.id])
        res_det = self.client.get(detail_url)
        self.assertEqual(res_det.status_code, status.HTTP_200_OK)
        self.assertEqual(res_det.json()['record_id'], self.r1.id)
        self.assertEqual(len(res_det.json()['provenance']), 1)

    def test_csv_export(self):
        """Owner can export CSV of records."""
        self.client.force_authenticate(user=self.user)
        res = self.client.get(reverse('api-dataset-export-csv', args=[self.dataset.id]))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'text/csv; charset=utf-8')
        content = res.content.decode('utf-8')
        self.assertIn('Kulda', content)
        self.assertIn('Basundhara', content)
