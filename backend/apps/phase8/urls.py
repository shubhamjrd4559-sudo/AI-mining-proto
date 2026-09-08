"""
apps.phase8.urls — Phase 8 URL configuration

Mounted at /api/phase8/ by backend/config/urls.py

Topics & Word Cloud:
  GET /api/phase8/topics/wordcloud/
  GET /api/phase8/topics/topics/
  GET /api/phase8/topics/documents/

Mining Map:
  GET /api/phase8/map/mines/
  GET /api/phase8/map/filters/
  GET /api/phase8/map/stats/

3D Geological View:
  GET /api/phase8/geo3d/gsi-reports/
  GET /api/phase8/geo3d/gsi-filters/
  GET /api/phase8/geo3d/gsi-summary/
  GET /api/phase8/geo3d/ocbis-blocks/
  GET /api/phase8/geo3d/ocbis-summary/
  GET /api/phase8/geo3d/reference-strata/
"""

from django.urls import path

from .views_topics import word_cloud_view, topics_view, topic_documents_view
from .views_map import mines_list_view, map_filters_view, map_stats_view
from .views_geo3d import (
    gsi_reports_view,
    gsi_filters_view,
    gsi_summary_view,
    ocbis_blocks_view,
    ocbis_summary_view,
    reference_strata_view,
)

urlpatterns = [
    # Topics & Word Cloud
    path("topics/wordcloud/", word_cloud_view, name="phase8-wordcloud"),
    path("topics/topics/", topics_view, name="phase8-topics"),
    path("topics/documents/", topic_documents_view, name="phase8-topic-documents"),

    # Mining Map
    path("map/mines/", mines_list_view, name="phase8-mines-list"),
    path("map/filters/", map_filters_view, name="phase8-map-filters"),
    path("map/stats/", map_stats_view, name="phase8-map-stats"),

    # 3D Geological View
    path("geo3d/gsi-reports/", gsi_reports_view, name="phase8-gsi-reports"),
    path("geo3d/gsi-filters/", gsi_filters_view, name="phase8-gsi-filters"),
    path("geo3d/gsi-summary/", gsi_summary_view, name="phase8-gsi-summary"),
    path("geo3d/ocbis-blocks/", ocbis_blocks_view, name="phase8-ocbis-blocks"),
    path("geo3d/ocbis-summary/", ocbis_summary_view, name="phase8-ocbis-summary"),
    path("geo3d/reference-strata/", reference_strata_view, name="phase8-reference-strata"),
]
