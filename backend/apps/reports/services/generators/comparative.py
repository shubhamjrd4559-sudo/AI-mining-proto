"""
apps.reports.services.generators.comparative — Comparative Intelligence Report Generator
"""

import logging
from typing import Dict, Any, List, Tuple

from apps.reports.services.base_generator import BaseReportGenerator
from apps.reports.services.comparative_builder import ComparativeReportBuilder

logger = logging.getLogger(__name__)


class ComparativeIntelligenceReportGenerator(BaseReportGenerator):
    report_type_name = "Comparative Intelligence Report"

    def generate(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        scoped_datasets = self.get_scoped_datasets()
        scoped_documents = self.get_scoped_documents()

        builder = ComparativeReportBuilder(
            user=self.user,
            organization=self.organization,
            date_range=self.date_range,
            filters=self.filters,
            datasets=scoped_datasets,
            documents=scoped_documents,
        )

        return builder.generate_comparative_report()
