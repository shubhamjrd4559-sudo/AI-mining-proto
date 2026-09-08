"""
apps.phase8.services.geo3d_service — 3D Geological View service

Provides real data from:
  - GSI Reports catalogue (1,075 exploration reports)
  - OCBIS coal block allocation records (2,386 blocks)

CRITICAL DISCLAIMER:
  The actual individual borehole intercept data (depth, lithology, seam thickness,
  GCV, ash, moisture) is NOT available in the audited dataset.
  Any 3D visualisation of subsurface structure is a SIMULATED REFERENCE MODEL
  and MUST be clearly labelled as such in the UI and API responses.
"""

import logging
from typing import Dict, Any, List, Optional

from django.db.models import QuerySet, Count, Q

from ..models import GSIReport, OcbisBlock

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Reference stratigraphic model for the 3D viewer
#
# This is a SIMULATED geological column representing TYPICAL Gondwana coalfield
# stratigraphy found across CIL coalfields.  Values are based on published
# generic Gondwana lithostratigraphy in GSI / CMPDI technical literature
# (Gondwana coal seam depth ranges, approximate thicknesses, typical lithologies).
#
# THIS IS NOT ACTUAL BOREHOLE DATA FOR ANY SPECIFIC LOCATION.
# ─────────────────────────────────────────────────────────────────────────────
SIMULATED_STRATA_DISCLAIMER = (
    "SIMULATED GEOLOGICAL REFERENCE MODEL — NOT ACTUAL BOREHOLE MEASUREMENTS. "
    "This model illustrates typical Gondwana coalfield stratigraphy for demonstration "
    "purposes only. No real borehole intercept data (depth, lithology, seam, GCV, ash, "
    "moisture) is available in the audited dataset. Do not use for engineering decisions."
)

REFERENCE_STRATIGRAPHY = [
    {
        "layer_no": 1,
        "name": "Overburden / Alluvium",
        "strata_type": "Quaternary",
        "depth_from_m": 0,
        "depth_to_m": 30,
        "lithology": "Soil, laterite, alluvium",
        "colour": "#C4A25A",
        "is_coal": False,
    },
    {
        "layer_no": 2,
        "name": "Barren Measures",
        "strata_type": "Gondwana / Permian",
        "depth_from_m": 30,
        "depth_to_m": 120,
        "lithology": "Sandstone, shale, carbonaceous shale",
        "colour": "#8B7355",
        "is_coal": False,
    },
    {
        "layer_no": 3,
        "name": "Coal Seam — Upper",
        "strata_type": "Gondwana / Permian",
        "depth_from_m": 120,
        "depth_to_m": 140,
        "lithology": "Coal, banded coal",
        "colour": "#1C1C1C",
        "is_coal": True,
        "typical_thickness_m": "5–20 m (varies by coalfield)",
    },
    {
        "layer_no": 4,
        "name": "Inter-burden / Shale",
        "strata_type": "Gondwana / Permian",
        "depth_from_m": 140,
        "depth_to_m": 200,
        "lithology": "Fine sandstone, shale, mudstone",
        "colour": "#6B7C93",
        "is_coal": False,
    },
    {
        "layer_no": 5,
        "name": "Coal Seam — Lower",
        "strata_type": "Gondwana / Permian",
        "depth_from_m": 200,
        "depth_to_m": 220,
        "lithology": "Coal, banded coal, carbonaceous shale partings",
        "colour": "#2A2A2A",
        "is_coal": True,
        "typical_thickness_m": "8–30 m (varies by coalfield)",
    },
    {
        "layer_no": 6,
        "name": "Floor Measures",
        "strata_type": "Gondwana / Permian",
        "depth_from_m": 220,
        "depth_to_m": 350,
        "lithology": "Massive sandstone, conglomerate, quartzite",
        "colour": "#A0926E",
        "is_coal": False,
    },
    {
        "layer_no": 7,
        "name": "Basement / Precambrian",
        "strata_type": "Precambrian",
        "depth_from_m": 350,
        "depth_to_m": 500,
        "lithology": "Granite, gneiss, schist",
        "colour": "#7A6B54",
        "is_coal": False,
    },
]


def get_gsi_reports(
    state: Optional[str] = None,
    region: Optional[str] = None,
    theme: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Return filtered GSI exploration report catalogue entries."""
    qs = GSIReport.objects.all()

    if state:
        qs = qs.filter(state__icontains=state)
    if region:
        qs = qs.filter(region__iexact=region)
    if theme:
        qs = qs.filter(theme__icontains=theme)
    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(author__icontains=search) |
            Q(accession_no__icontains=search) |
            Q(state__icontains=search)
        )

    total = qs.count()
    items = list(
        qs[offset: offset + limit].values(
            "id", "accession_no", "title", "author",
            "state", "year_from", "year_to", "region", "theme",
        )
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": items,
        "data_source": "GSI_Reports.csv (Google Drive, audited 2026-09-08)",
    }


def get_gsi_filter_options() -> Dict[str, Any]:
    """Return all available GSI report filter options."""
    regions = sorted(
        set(GSIReport.objects.exclude(region="").values_list("region", flat=True))
    )
    themes = sorted(
        set(GSIReport.objects.exclude(theme__in=["null", ""]).values_list("theme", flat=True))
        - {"null"}
    )[:30]

    return {
        "regions": regions,
        "themes": themes,
        "data_source": "GSI_Reports.csv",
    }


def get_gsi_summary() -> Dict[str, Any]:
    """Return aggregate statistics for the GSI exploration reports."""
    total = GSIReport.objects.count()
    by_region = dict(
        GSIReport.objects.values("region").annotate(count=Count("id")).values_list("region", "count")
    )
    themes_with_coal = GSIReport.objects.filter(
        Q(theme__icontains="coal") | Q(theme__icontains="lignite")
    ).count()

    return {
        "total_reports": total,
        "coal_lignite_reports": themes_with_coal,
        "by_region": by_region,
        "data_source": "GSI_Reports.csv (audited 2026-09-08)",
    }


def get_ocbis_blocks(
    coalfield: Optional[str] = None,
    subsidiary: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Return filtered OCBIS coal block allocation records."""
    qs = OcbisBlock.objects.all()

    if coalfield:
        qs = qs.filter(coalfield__icontains=coalfield)
    if subsidiary:
        qs = qs.filter(subsidiary_or_state__icontains=subsidiary)
    if search:
        qs = qs.filter(
            Q(block_name__icontains=search) |
            Q(coalfield__icontains=search) |
            Q(subsidiary_or_state__icontains=search) |
            Q(allocated_to__icontains=search)
        )

    total = qs.count()
    items = list(
        qs[offset: offset + limit].values(
            "id", "subsidiary_or_state", "coalfield",
            "block_name", "act_type", "allocated_to",
        )
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": items,
        "data_source": "OCBIS.html (Online Coal Block Information System, audited 2026-09-08)",
    }


def get_ocbis_summary() -> Dict[str, Any]:
    """Return aggregate summary for OCBIS blocks."""
    total = OcbisBlock.objects.count()
    unallocated = OcbisBlock.objects.filter(allocated_to__iexact="Unallocated").count()
    by_coalfield = dict(
        OcbisBlock.objects.values("coalfield").annotate(count=Count("id"))
        .order_by("-count")[:15]
        .values_list("coalfield", "count")
    )

    return {
        "total_blocks": total,
        "unallocated_blocks": unallocated,
        "allocated_blocks": total - unallocated,
        "top_coalfields": by_coalfield,
        "data_source": "OCBIS.html (audited 2026-09-08)",
    }


def get_reference_stratigraphy() -> Dict[str, Any]:
    """
    Return the clearly-labelled SIMULATED reference stratigraphic model.

    IMPORTANT: This function returns SIMULATED data and must ALWAYS include
    the disclaimer. Never remove or alter the disclaimer.
    """
    return {
        "disclaimer": SIMULATED_STRATA_DISCLAIMER,
        "is_simulated": True,
        "label": "SIMULATED — NOT ACTUAL BOREHOLE DATA",
        "model_description": (
            "Generic Gondwana coalfield stratigraphy representative of typical "
            "CIL subsidiary coalfields. Based on published Gondwana lithostratigraphic "
            "column from GSI/CMPDI literature. NOT derived from any specific borehole log."
        ),
        "layers": REFERENCE_STRATIGRAPHY,
        "real_data_available": (
            "GSI exploration report catalogue (1,075 records) and OCBIS coal block "
            "data (2,386 blocks) are available via the gsi-reports and ocbis-blocks APIs. "
            "Individual borehole intercept logs are NOT available in the audited dataset."
        ),
    }
