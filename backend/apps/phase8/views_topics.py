"""
apps.phase8.views_topics — Topics & Word Cloud API views

GET /api/phase8/topics/wordcloud/
GET /api/phase8/topics/topics/
GET /api/phase8/topics/documents/
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .services.topics_service import (
    get_word_cloud_data,
    get_topics_data,
    get_topic_documents,
)

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def word_cloud_view(request):

    """
    GET /api/phase8/topics/wordcloud/

    Returns real keyword frequency data from indexed DocumentChunks.

    Query params:
      limit (int, default 60): max number of words to return
    """
    try:
        limit = min(int(request.query_params.get("limit", 60)), 200)
    except (ValueError, TypeError):
        limit = 60

    data = get_word_cloud_data(request.user, limit=limit)
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def topics_view(request):
    """
    GET /api/phase8/topics/topics/

    Returns topic distribution derived from indexed DocumentChunks using
    keyword-signature matching against domain topic categories.
    """
    data = get_topics_data(request.user)
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def topic_documents_view(request):
    """
    GET /api/phase8/topics/documents/

    Returns user's indexed documents with their dominant topic and top keywords.
    """
    data = get_topic_documents(request.user)
    return Response(data)

