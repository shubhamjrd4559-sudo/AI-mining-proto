"""
apps.datasets — Tests
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import StructuredDataset, StructuredRecord


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
