"""
apps.phase8.views_map — Mining Map API views

GET /api/phase8/map/mines/    — paginated mine list with filters
GET /api/phase8/map/filters/  — available filter options
GET /api/phase8/map/stats/    — aggregate statistics
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import MineLocation
from .serializers import MineLocationSerializer, MineLocationListSerializer
from .services.map_service import (
    get_mine_queryset,
    get_filter_options,
    get_map_stats,
)

logger = logging.getLogger(__name__)


class MinePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def mines_list_view(request):

    """
    GET /api/phase8/map/mines/

    Returns mine locations for map rendering. Supports filtering and pagination.

    Query params:
      subsidiary   — CIL subsidiary (CCL, BCCL, SECL, NCL, MCL, ECL, WCL, SCCL)
      state        — state name
      district     — district name
      coalfield    — coalfield name
      mine_type    — OC | UG | Mixed
      search       — free-text search in mine name / coalfield / district
      all          — if "true", skip pagination (returns up to 200 for map markers)
      page_size    — override default page size (max 200)
    """
    subsidiary = request.query_params.get("subsidiary")
    state = request.query_params.get("state")
    district = request.query_params.get("district")
    coalfield = request.query_params.get("coalfield")
    mine_type = request.query_params.get("mine_type")
    search = request.query_params.get("search")
    return_all = request.query_params.get("all", "false").lower() == "true"

    qs = get_mine_queryset(
        subsidiary=subsidiary,
        state=state,
        district=district,
        coalfield=coalfield,
        mine_type=mine_type,
        search=search,
    )

    # For map marker rendering, support returning all results without pagination
    if return_all:
        qs = qs[:200]  # hard cap for safety
        serializer = MineLocationListSerializer(qs, many=True)
        return Response({
            "count": len(serializer.data),
            "results": serializer.data,
            "data_source": "mining_map_phase8.csv (audited project dataset)",
            "year": "2024-25",
            "provenance": "Compiled from audited project dataset mining_map_phase8.csv; coordinates are transcribed as provided in source data, not independently field-surveyed.",
            "note": "Star Rating is NOT available in this dataset.",
        })

    paginator = MinePagination()
    page = paginator.paginate_queryset(qs, request)
    if page is not None:
        serializer = MineLocationSerializer(page, many=True)
        response = paginator.get_paginated_response(serializer.data)
        response.data["data_source"] = "mining_map_phase8.csv (audited project dataset)"
        response.data["year"] = "2024-25"
        response.data["provenance"] = "Compiled from audited project dataset mining_map_phase8.csv; coordinates are transcribed as provided in source data, not independently field-surveyed."
        response.data["note"] = "Star Rating is NOT available in this dataset."
        return response

    serializer = MineLocationSerializer(qs, many=True)
    return Response({
        "count": qs.count(),
        "results": serializer.data,
        "data_source": "mining_map_phase8.csv (audited project dataset)",
        "year": "2024-25",
        "provenance": "Compiled from audited project dataset mining_map_phase8.csv; coordinates are transcribed as provided in source data, not independently field-surveyed.",
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def map_filters_view(request):
    """
    GET /api/phase8/map/filters/

    Returns all available filter option values derived from actual seeded data.
    """
    return Response(get_filter_options())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def map_stats_view(request):
    """
    GET /api/phase8/map/stats/

    Returns aggregate statistics over the full or filtered mine dataset.

    Query params: same as mines_list_view (subsidiary, state, mine_type, etc.)
    """
    subsidiary = request.query_params.get("subsidiary")
    state = request.query_params.get("state")
    district = request.query_params.get("district")
    coalfield = request.query_params.get("coalfield")
    mine_type = request.query_params.get("mine_type")
    search = request.query_params.get("search")

    qs = get_mine_queryset(
        subsidiary=subsidiary,
        state=state,
        district=district,
        coalfield=coalfield,
        mine_type=mine_type,
        search=search,
    )
    return Response(get_map_stats(qs))

