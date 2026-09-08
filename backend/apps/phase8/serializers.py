"""
apps.phase8.serializers — DRF serializers for Phase 8 models
"""
from rest_framework import serializers
from .models import MineLocation, GSIReport, OcbisBlock


class MineLocationSerializer(serializers.ModelSerializer):
    """Serializer for MineLocation — includes all fields needed by the map frontend."""

    mine_type_display = serializers.SerializerMethodField()

    class Meta:
        model = MineLocation
        fields = [
            "id",
            "mine_name",
            "latitude",
            "longitude",
            "state",
            "district",
            "coalfield",
            "subsidiary",
            "mine_type",
            "mine_type_display",
            "production_mt",
            "year",
        ]

    def get_mine_type_display(self, obj):
        mapping = {
            "OC": "Open-cast",
            "UG": "Underground",
            "Mixed": "Mixed (OC+UG)",
        }
        return mapping.get(obj.mine_type, obj.mine_type or "—")


class MineLocationListSerializer(serializers.ModelSerializer):
    """Compact serializer for map marker rendering (lat/lon + key label fields)."""

    class Meta:
        model = MineLocation
        fields = [
            "id",
            "mine_name",
            "latitude",
            "longitude",
            "subsidiary",
            "mine_type",
            "state",
            "district",
            "coalfield",
            "production_mt",
            "year",
        ]


class GSIReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSIReport
        fields = [
            "id",
            "accession_no",
            "fsp_id",
            "title",
            "author",
            "state",
            "toposheet_no",
            "year_from",
            "year_to",
            "region",
            "mission",
            "theme",
        ]


class OcbisBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = OcbisBlock
        fields = [
            "id",
            "subsidiary_or_state",
            "coalfield",
            "block_name",
            "act_type",
            "allocated_to",
        ]
