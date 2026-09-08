"""
apps.phase8.views_geo3d — 3D Geological View API views

GET /api/phase8/geo3d/gsi-reports/         — GSI exploration catalogue
GET /api/phase8/geo3d/gsi-filters/         — available filter options
GET /api/phase8/geo3d/gsi-summary/         — aggregate GSI summary
GET /api/phase8/geo3d/ocbis-blocks/        — OCBIS coal block records
GET /api/phase8/geo3d/ocbis-summary/       — aggregate OCBIS summary
GET /api/phase8/geo3d/reference-strata/    — SIMULATED stratigraphic reference model
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .services.geo3d_service import (
    get_gsi_reports,
    get_gsi_filter_options,
    get_gsi_summary,
    get_ocbis_blocks,
    get_ocbis_summary,
    get_reference_stratigraphy,
)

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def gsi_reports_view(request):

    """
    GET /api/phase8/geo3d/gsi-reports/

    Returns filtered GSI exploration report catalogue entries.

    Query params:
      state   — state filter (partial match)
      region  — GSI regional office code (ER, WR, SR, NR, CR, NER, etc.)
      theme   — thematic filter (partial match)
      search  — free-text search
      limit   — results per page (default 50, max 200)
      offset  — pagination offset
    """
    state = request.query_params.get("state")
    region = request.query_params.get("region")
    theme = request.query_params.get("theme")
    search = request.query_params.get("search")

    try:
        limit = min(int(request.query_params.get("limit", 50)), 200)
        offset = max(int(request.query_params.get("offset", 0)), 0)
    except (ValueError, TypeError):
        limit, offset = 50, 0

    data = get_gsi_reports(
        state=state, region=region, theme=theme,
        search=search, limit=limit, offset=offset,
    )
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def gsi_filters_view(request):
    """GET /api/phase8/geo3d/gsi-filters/ — filter options for GSI reports."""
    return Response(get_gsi_filter_options())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def gsi_summary_view(request):
    """GET /api/phase8/geo3d/gsi-summary/ — aggregate GSI statistics."""
    return Response(get_gsi_summary())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ocbis_blocks_view(request):
    """
    GET /api/phase8/geo3d/ocbis-blocks/

    Returns filtered OCBIS coal block allocation records.

    Query params:
      coalfield   — coalfield name (partial match)
      subsidiary  — subsidiary or state (partial match)
      search      — free-text search
      limit       — results per page (default 50, max 200)
      offset      — pagination offset
    """
    coalfield = request.query_params.get("coalfield")
    subsidiary = request.query_params.get("subsidiary")
    search = request.query_params.get("search")

    try:
        limit = min(int(request.query_params.get("limit", 50)), 200)
        offset = max(int(request.query_params.get("offset", 0)), 0)
    except (ValueError, TypeError):
        limit, offset = 50, 0

    data = get_ocbis_blocks(
        coalfield=coalfield, subsidiary=subsidiary,
        search=search, limit=limit, offset=offset,
    )
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ocbis_summary_view(request):
    """GET /api/phase8/geo3d/ocbis-summary/ — aggregate OCBIS statistics."""
    return Response(get_ocbis_summary())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def reference_strata_view(request):
    """
    GET /api/phase8/geo3d/reference-strata/

    Returns the SIMULATED reference stratigraphic model for 3D visualisation.

    ALWAYS includes is_simulated=true and a full disclaimer in the response.
    This data MUST NOT be presented to users as real borehole measurements.
    """
    return Response(get_reference_stratigraphy())

