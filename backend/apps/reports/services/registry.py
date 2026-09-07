"""
apps.reports.services.registry — Report Generator Registry

Maps report type strings to generator classes.
Enables pluggable addition of new report types without modifying the core system.
"""

from typing import Type
from apps.reports.models import ReportType
from apps.reports.services.base_generator import BaseReportGenerator
from apps.reports.services.generators.production import ProductionReportGenerator
from apps.reports.services.generators.geological import GeologicalExplorationReportGenerator
from apps.reports.services.generators.mining_performance import MiningPerformanceReportGenerator
from apps.reports.services.generators.exploration import ExplorationReportGenerator
from apps.reports.services.generators.coal_seam import CoalSeamAnalysisReportGenerator
from apps.reports.services.generators.parliamentary import ParliamentaryQuestionResponseGenerator
from apps.reports.services.generators.administrative import AdministrativeQueryReportGenerator
from apps.reports.services.generators.custom import CustomReportGenerator

GENERATOR_REGISTRY = {
    ReportType.PRODUCTION: ProductionReportGenerator,
    ReportType.GEOLOGICAL_EXPLORATION: GeologicalExplorationReportGenerator,
    ReportType.MINING_PERFORMANCE: MiningPerformanceReportGenerator,
    ReportType.EXPLORATION: ExplorationReportGenerator,
    ReportType.COAL_SEAM: CoalSeamAnalysisReportGenerator,
    ReportType.PARLIAMENTARY_QUESTION: ParliamentaryQuestionResponseGenerator,
    ReportType.ADMINISTRATIVE_QUERY: AdministrativeQueryReportGenerator,
    ReportType.CUSTOM: CustomReportGenerator,
    # Also support friendly string variations
    'Production Report': ProductionReportGenerator,
    'Geological Report': GeologicalExplorationReportGenerator,
    'Geological & Exploration Report': GeologicalExplorationReportGenerator,
    'Mining Report': MiningPerformanceReportGenerator,
    'Mining Performance Report': MiningPerformanceReportGenerator,
    'Exploration Report': ExplorationReportGenerator,
    'Coal Seam Analysis': CoalSeamAnalysisReportGenerator,
    'Parliamentary Question Response': ParliamentaryQuestionResponseGenerator,
    'Administrative Query': AdministrativeQueryReportGenerator,
    'Custom Report': CustomReportGenerator,
}


def get_generator_for_type(report_type: str) -> Type[BaseReportGenerator]:
    """
    Look up generator class for a given report type.
    Falls back to CustomReportGenerator if unknown type.
    """
    clean_type = (report_type or '').strip()
    generator_cls = GENERATOR_REGISTRY.get(clean_type)
    if not generator_cls:
        # Check case-insensitive match
        for k, v in GENERATOR_REGISTRY.items():
            if k.lower() == clean_type.lower():
                return v
        return CustomReportGenerator
    return generator_cls
