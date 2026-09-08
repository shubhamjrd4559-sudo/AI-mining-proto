"""
apps.phase8.services.map_service — Mining Map query & filter service

Provides filtered, paginated access to the MineLocation dataset
derived from the audited mining_map_phase8.csv (107 mines, 2024-25 data).

IMPORTANT: Star Rating data does NOT exist in the audited dataset.
This service does NOT return, estimate, or fabricate star ratings.
"""

import logging
from typing import Dict, Any, List, Optional

from django.db.models import QuerySet, Count, Avg, Sum, Min, Max, Q

from ..models import MineLocation

logger = logging.getLogger(__name__)


def get_mine_queryset(
    subsidiary: Optional[str] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    coalfield: Optional[str] = None,
    mine_type: Optional[str] = None,
    search: Optional[str] = None,
) -> QuerySet:
    """
    Build a filtered MineLocation queryset.

    All filter values are case-insensitive. Unknown filter values silently
    return an empty queryset rather than raising exceptions.
    """
    qs = MineLocation.objects.all()

    if subsidiary:
        qs = qs.filter(subsidiary__iexact=subsidiary)
    if state:
        qs = qs.filter(state__iexact=state)
    if district:
        qs = qs.filter(district__iexact=district)
    if coalfield:
        qs = qs.filter(coalfield__iexact=coalfield)
    if mine_type:
        qs = qs.filter(mine_type__iexact=mine_type)
    if search:
        qs = qs.filter(
            Q(mine_name__icontains=search) |
            Q(coalfield__icontains=search) |
            Q(district__icontains=search) |
            Q(state__icontains=search) |
            Q(subsidiary__icontains=search)
        )

    return qs


def get_filter_options() -> Dict[str, Any]:
    """
    Return all available filter option values for the Mining Map UI.
    Derived directly from the actual database — always accurate.
    """
    qs = MineLocation.objects.all()

    subsidiaries = sorted(
        set(qs.exclude(subsidiary="").values_list("subsidiary", flat=True))
    )
    states = sorted(
        set(qs.exclude(state="").values_list("state", flat=True))
    )
    coalfields = sorted(
        set(qs.exclude(coalfield="").values_list("coalfield", flat=True))
    )
    mine_types = sorted(
        set(qs.exclude(mine_type="").values_list("mine_type", flat=True))
    )
    districts = sorted(
        set(qs.exclude(district="").values_list("district", flat=True))
    )

    # Human-readable mine type labels
    type_labels = {
        "OC": "Open-cast",
        "UG": "Underground",
        "Mixed": "Mixed (OC+UG)",
    }

    return {
        "subsidiaries": subsidiaries,
        "states": states,
        "districts": districts,
        "coalfields": coalfields,
        "mine_types": [
            {"value": t, "label": type_labels.get(t, t)}
            for t in mine_types
        ],
        "data_source": "mining_map_phase8.csv (audited 2026-09-08)",
        "year": "2024-25",
        "note": "Star Rating is NOT available in the audited dataset.",
    }


def get_map_stats(qs: Optional[QuerySet] = None) -> Dict[str, Any]:
    """
    Return aggregate statistics for the current filter (or all mines).
    """
    if qs is None:
        qs = MineLocation.objects.all()

    total = qs.count()
    if total == 0:
        return {
            "total_mines": 0,
            "subsidiaries": 0,
            "states": 0,
            "coalfields": 0,
            "total_production_mt": 0,
            "avg_production_mt": 0,
            "by_type": {},
            "by_subsidiary": {},
            "data_source": "mining_map_phase8.csv",
        }

    # Aggregates
    agg = qs.aggregate(
        total_prod=Sum("production_mt"),
        avg_prod=Avg("production_mt"),
    )

    by_type = dict(
        qs.values("mine_type").annotate(count=Count("id")).values_list("mine_type", "count")
    )
    by_sub = dict(
        qs.values("subsidiary").annotate(
            count=Count("id"),
            prod=Sum("production_mt"),
        ).values_list("subsidiary", "count")
    )
    sub_prod = dict(
        qs.values("subsidiary").annotate(prod=Sum("production_mt")).values_list("subsidiary", "prod")
    )

    return {
        "total_mines": total,
        "subsidiaries": qs.values("subsidiary").distinct().count(),
        "states": qs.values("state").distinct().count(),
        "coalfields": qs.values("coalfield").distinct().count(),
        "total_production_mt": round(agg["total_prod"] or 0, 2),
        "avg_production_mt": round(agg["avg_prod"] or 0, 3),
        "by_type": by_type,
        "by_subsidiary": {
            sub: {
                "count": by_sub.get(sub, 0),
                "production_mt": round(sub_prod.get(sub, 0) or 0, 2),
            }
            for sub in sorted(by_sub.keys())
        },
        "data_source": "mining_map_phase8.csv (audited project dataset)",
        "year": "2024-25",
        "provenance": "Compiled from audited project dataset mining_map_phase8.csv; coordinates are transcribed as provided in source data, not independently field-surveyed.",
    }

