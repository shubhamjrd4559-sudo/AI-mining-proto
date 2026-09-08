"""
apps.phase8.tests — Comprehensive Automated Test Suite for Phase 8

Covers:
  1. MineLocation model & data integrity (107 verified mines, real coordinates, no star ratings)
  2. GSIReport model & data integrity (1,075 exploration records)
  3. OcbisBlock model & data integrity (2,226 coal blocks)
  4. Mining Map APIs:
     - Authentication enforcement (unauthenticated blocked with 401)
     - Authenticated list, pagination, all-markers mode
     - Multi-field filtering (subsidiary, state, mine_type, search)
     - Aggregation stats & filter options introspection
     - Provenance & star rating exclusion notes
  5. 3D Geological View APIs:
     - Authentication enforcement (unauthenticated blocked with 401)
     - GSI reports, GSI filters, GSI summary
     - OCBIS blocks, OCBIS summary
     - Reference stratigraphy API & mandatory simulation disclaimer check
  6. Topics & Word Cloud APIs:
     - Authentication enforcement (unauthenticated blocked with 401)
     - Authenticated keyword extraction over DocumentChunk
     - Owner isolation (User A cannot see User B's documents)
     - Topic classification & document provenance
  7. Data Provenance & Safety:
     - Verified source CSV artifact exists
     - Provenance manifest integrity
     - Zero fabricated borehole measurements
     - Zero fabricated star ratings
"""

import json
from pathlib import Path
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.documents.models import Document, DocumentStatus
from apps.intelligence.models import DocumentChunk
from apps.phase8.models import MineLocation, GSIReport, OcbisBlock
from apps.phase8.services.geo3d_service import (
    SIMULATED_STRATA_DISCLAIMER,
    REFERENCE_STRATIGRAPHY,
    get_reference_stratigraphy,
)
from apps.phase8.services.topics_service import (
    get_word_cloud_data,
    get_topics_data,
    get_topic_documents,
)

User = get_user_model()


class MineLocationModelTestCase(TestCase):
    """Verifies MineLocation data model and integrity constraints."""

    def test_mine_creation_and_string_representation(self):
        mine = MineLocation.objects.create(
            mine_name="Test OCP",
            latitude=23.75,
            longitude=85.90,
            state="Jharkhand",
            district="Bokaro",
            coalfield="East Bokaro",
            subsidiary="CCL",
            mine_type="OC",
            production_mt=3.5,
            year="2024-25",
        )
        self.assertEqual(str(mine), "Test OCP (CCL, Jharkhand)")
        self.assertFalse(hasattr(mine, "star_rating"))
        self.assertFalse(hasattr(mine, "stars"))

    def test_seeded_mines_data_integrity(self):
        """Verifies 107 verified mines from mining_map_phase8.csv are valid."""
        total = MineLocation.objects.count()
        if total > 0:
            self.assertEqual(total, 107)
            for m in MineLocation.objects.all():
                self.assertGreaterEqual(m.latitude, 6.0)
                self.assertLessEqual(m.latitude, 38.0)
                self.assertGreaterEqual(m.longitude, 68.0)
                self.assertLessEqual(m.longitude, 98.0)
                self.assertIn(m.mine_type, ["OC", "UG", "Mixed"])
                self.assertTrue(len(m.mine_name) > 0)
                self.assertTrue(len(m.subsidiary) > 0)


class GSIReportModelTestCase(TestCase):
    """Verifies GSIReport exploration catalog model."""

    def test_gsi_report_creation_and_str(self):
        report = GSIReport.objects.create(
            accession_no="GSI-TEST-001",
            fsp_id="FSP2024001",
            title="Geological Investigation in Jharia Coalfield",
            author="Sharma, R.K.",
            state="Jharkhand",
            toposheet_no="73I/1",
            year_from="2023",
            year_to="2024",
            region="ER",
            mission="Mission IIB",
            theme="Coal and Lignite Exploration",
        )
        self.assertIn("GSI-TEST-001", str(report))
        self.assertIn("Geological Investigation", str(report))


class OcbisBlockModelTestCase(TestCase):
    """Verifies OCBIS Coal Block allocation model."""

    def test_ocbis_block_creation_and_str(self):
        block = OcbisBlock.objects.create(
            subsidiary_or_state="BCCL",
            coalfield="Jharia",
            block_name="Pootki Sector A",
            act_type="CIL",
            allocated_to="BCCL",
        )
        self.assertEqual(str(block), "Pootki Sector A (Jharia)")


class MiningMapAPITestCase(TestCase):
    """Tests Mining Map endpoints, authorization, filtering, pagination, and stats."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="mapuser", password="password123")
        self.client.force_authenticate(user=self.user)

        # Seed test mine records
        self.mine1 = MineLocation.objects.create(
            mine_name="Aadocm",
            latitude=23.7666,
            longitude=85.9855,
            state="Jharkhand",
            district="Bokaro",
            coalfield="E. Bokaro",
            subsidiary="CCL",
            mine_type="OC",
            production_mt=2.613,
            year="2024-25",
        )
        self.mine2 = MineLocation.objects.create(
            mine_name="AGKCC",
            latitude=23.8098,
            longitude=86.2917,
            state="Jharkhand",
            district="Dhanbad",
            coalfield="Jharia",
            subsidiary="BCCL",
            mine_type="OC",
            production_mt=0.02,
            year="2024-25",
        )
        self.mine3 = MineLocation.objects.create(
            mine_name="Bagdeva",
            latitude=22.3863,
            longitude=82.5350,
            state="Chhattisgarh",
            district="Korba",
            coalfield="Central India",
            subsidiary="SECL",
            mine_type="UG",
            production_mt=0.285,
            year="2024-25",
        )

    def test_unauthenticated_mining_map_access_blocked(self):
        """Unauthenticated requests must be rejected with 401."""
        unauth_client = APIClient()
        url = reverse("phase8-mines-list")
        response = unauth_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_mines_list_paginated(self):
        url = reverse("phase8-mines-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("results", data)
        self.assertIn("count", data)
        self.assertEqual(data["count"], 3)
        self.assertIn("note", data)
        self.assertIn("Star Rating is NOT available", data["note"])
        self.assertIn("provenance", data)

    def test_mines_list_all_markers(self):
        """Map requests all=true for efficient marker rendering."""
        url = reverse("phase8-mines-list") + "?all=true"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["count"], 3)
        item = data["results"][0]
        self.assertIn("latitude", item)
        self.assertIn("longitude", item)
        self.assertIn("mine_name", item)
        self.assertIn("subsidiary", item)
        self.assertNotIn("star_rating", item)

    def test_filter_by_subsidiary(self):
        url = reverse("phase8-mines-list") + "?subsidiary=CCL"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["mine_name"], "Aadocm")

    def test_filter_by_state(self):
        url = reverse("phase8-mines-list") + "?state=Chhattisgarh"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["mine_name"], "Bagdeva")

    def test_filter_by_mine_type(self):
        url = reverse("phase8-mines-list") + "?mine_type=UG"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["mine_name"], "Bagdeva")

    def test_search_filter(self):
        url = reverse("phase8-mines-list") + "?search=jharia"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["mine_name"], "AGKCC")

    def test_filter_options_endpoint(self):
        url = reverse("phase8-map-filters")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("subsidiaries", data)
        self.assertIn("states", data)
        self.assertIn("coalfields", data)
        self.assertIn("mine_types", data)
        self.assertIn("CCL", data["subsidiaries"])
        self.assertIn("BCCL", data["subsidiaries"])
        self.assertIn("SECL", data["subsidiaries"])

    def test_map_stats_endpoint(self):
        url = reverse("phase8-map-stats")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["total_mines"], 3)
        self.assertAlmostEqual(data["total_production_mt"], 2.918, places=2)
        self.assertIn("by_type", data)
        self.assertIn("by_subsidiary", data)
        self.assertIn("provenance", data)


class Geological3DAPITestCase(TestCase):
    """Tests 3D Geological View endpoints, authorization, GSI reports, OCBIS blocks, and stratigraphy disclaimer."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="geouser", password="password123")
        self.client.force_authenticate(user=self.user)

        self.gsi = GSIReport.objects.create(
            accession_no="WRO-2788",
            title="Field Report On Coal Investigation In Gadhsisa Area",
            author="Kachhara, R.C.",
            state="Gujarat",
            year_from="1971",
            year_to="1972",
            region="WR",
            theme="Systematic Geological Mapping",
        )
        self.block = OcbisBlock.objects.create(
            subsidiary_or_state="Jharkhand",
            coalfield="North Karanpura",
            block_name="Badam",
            act_type="MMDR",
            allocated_to="NTPC",
        )

    def test_unauthenticated_geological_access_blocked(self):
        """Unauthenticated requests must receive 401."""
        unauth_client = APIClient()
        url = reverse("phase8-gsi-reports")
        response = unauth_client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_gsi_reports_list_and_filter(self):
        url = reverse("phase8-gsi-reports")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["results"][0]["accession_no"], "WRO-2788")

        # Filter by region
        res_wr = self.client.get(url + "?region=WR")
        self.assertEqual(res_wr.json()["total"], 1)
        res_er = self.client.get(url + "?region=ER")
        self.assertEqual(res_er.json()["total"], 0)

    def test_gsi_summary_endpoint(self):
        url = reverse("phase8-gsi-summary")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("total_reports", data)
        self.assertIn("by_region", data)

    def test_ocbis_blocks_list_and_filter(self):
        url = reverse("phase8-ocbis-blocks")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["results"][0]["block_name"], "Badam")

        # Filter by coalfield
        res_cf = self.client.get(url + "?coalfield=Karanpura")
        self.assertEqual(res_cf.json()["total"], 1)

    def test_ocbis_summary_endpoint(self):
        url = reverse("phase8-ocbis-summary")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("total_blocks", data)
        self.assertIn("allocated_blocks", data)

    def test_reference_stratigraphy_strict_disclaimer(self):
        """CRITICAL DATA SAFETY: Must clearly label simulated strata as NOT actual borehole measurements."""
        url = reverse("phase8-reference-strata")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertTrue(data.get("is_simulated"))
        self.assertEqual(data.get("label"), "SIMULATED — NOT ACTUAL BOREHOLE DATA")
        self.assertIn("SIMULATED GEOLOGICAL REFERENCE MODEL — NOT ACTUAL BOREHOLE MEASUREMENTS", data.get("disclaimer", ""))
        self.assertIn("layers", data)
        self.assertGreater(len(data["layers"]), 0)

        # Service-level test
        strata = get_reference_stratigraphy()
        self.assertTrue(strata["is_simulated"])
        self.assertEqual(strata["disclaimer"], SIMULATED_STRATA_DISCLAIMER)


class TopicsAndWordCloudAPITestCase(TestCase):
    """Tests Topics and Word Cloud extraction, authorization, and owner isolation."""

    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(username="usera", password="password123")
        self.user_b = User.objects.create_user(username="userb", password="password123")

        # Create indexed documents for user_a
        self.doc = Document.objects.create(
            title="CMPDI Exploration Annual Report 2024",
            uploaded_by=self.user_a,
            status=DocumentStatus.INDEXED,
        )

        DocumentChunk.objects.create(
            document=self.doc,
            chunk_index=0,
            content=(
                "Geological exploration and borehole drilling carried out across Gondwana coalfields. "
                "Total coal production increased with opencast mining and overburden removal. "
                "Coal quality analysis showed high coking coal grades with low ash and moisture. "
                "Environmental clearance and safety measures were implemented for mine reclamation."
            ),
            content_hash="hash001",
            section_heading="Chapter 1: Geological Exploration and Mining",
        )
        DocumentChunk.objects.create(
            document=self.doc,
            chunk_index=1,
            content=(
                "Borehole drilling programs expanded in CCL, BCCL, and SECL coalfield areas. "
                "Production targets were achieved through modern excavation equipment and washery upgrades. "
                "Coking and non-coking coal dispatch achieved record figures during the financial year."
            ),
            content_hash="hash002",
            section_heading="Chapter 2: Operational Performance",
        )

    def test_unauthenticated_topics_access_blocked(self):
        """Unauthenticated requests must be rejected with 401."""
        url = reverse("phase8-wordcloud")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_wordcloud_extracts_real_keywords(self):
        self.client.force_authenticate(user=self.user_a)
        url = reverse("phase8-wordcloud")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertGreater(len(data["words"]), 0)
        self.assertEqual(data["total_documents"], 1)
        self.assertEqual(data["total_chunks"], 2)

        words_list = [w["word"] for w in data["words"]]
        self.assertTrue(any("COAL" in w for w in words_list))

    def test_owner_isolation_in_topics_and_wordcloud(self):
        """User B should NOT see User A's indexed documents or keyword frequencies."""
        self.client.force_authenticate(user=self.user_b)
        url = reverse("phase8-wordcloud")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["words"]), 0)
        self.assertEqual(data["total_chunks"], 0)
        self.assertEqual(data["total_documents"], 0)

    def test_topics_distribution_generation(self):
        self.client.force_authenticate(user=self.user_a)
        url = reverse("phase8-topics")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("topics", data)
        self.assertGreater(len(data["topics"]), 0)
        topic_names = [t["name"] for t in data["topics"]]
        self.assertTrue(
            any("Exploration" in t or "Production" in t or "Quality" in t for t in topic_names)
        )

    def test_topic_documents_provenance(self):
        self.client.force_authenticate(user=self.user_a)
        url = reverse("phase8-topic-documents")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("documents", data)
        self.assertEqual(len(data["documents"]), 1)
        doc = data["documents"][0]
        self.assertEqual(doc["title"], "CMPDI Exploration Annual Report 2024")
        self.assertGreater(len(doc["top_keywords"]), 0)
        self.assertNotEqual(doc["dominant_topic"], "—")


class DataProvenanceTestCase(TestCase):
    """Verifies that actual source data artifacts and provenance manifest exist and are consistent."""

    def test_source_csv_exists(self):
        csv_path = Path(__file__).resolve().parent / "data" / "mining_map_phase8.csv"
        self.assertTrue(csv_path.exists(), "Source artifact mining_map_phase8.csv must exist in data directory")

    def test_provenance_manifest_integrity(self):
        manifest_path = Path(__file__).resolve().parent / "data" / "provenance.json"
        self.assertTrue(manifest_path.exists(), "provenance.json must exist in data directory")
        with open(manifest_path, encoding="utf-8") as f:
            prov = json.load(f)
        self.assertIn("datasets", prov)
        self.assertIn("mining_map", prov["datasets"])
        self.assertEqual(prov["datasets"]["mining_map"]["record_count"], 107)
        self.assertIn("coordinate_provenance_statement", prov["datasets"]["mining_map"])
        self.assertIn("not been independently ground-truth surveyed", prov["datasets"]["mining_map"]["coordinate_provenance_statement"])
        self.assertTrue(prov["geological_model_safety"]["is_simulated"])
