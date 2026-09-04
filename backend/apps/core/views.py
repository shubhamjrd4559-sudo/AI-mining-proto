"""
apps.core — Health check and stub API views

GET /api/health/
    Returns service status, database connectivity, and version info.

GET /api/analytics/   (stub)
GET /api/chat/        (stub)
GET /api/excel/       (stub)
GET /api/reports/     (stub)
GET /api/topics/      (stub)
"""

import logging
from datetime import datetime, timezone

from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


@api_view(['GET'])
def health_check(request):
    """
    GET /api/health/

    Returns service health status including database connectivity.
    This is the primary Phase 1 verification endpoint.
    """
    db_status = 'connected'
    db_error = None

    try:
        # Verify database is reachable
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception as exc:
        db_status = 'error'
        db_error = str(exc)
        logger.error('Health check: database error: %s', exc)

    overall_status = 'ok' if db_status == 'connected' else 'degraded'

    payload = {
        'status': overall_status,
        'service': 'CMPDI AI Backend',
        'version': '1.0.0-phase1',
        'phase': 1,
        'database': db_status,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }

    if db_error:
        payload['database_error'] = db_error

    http_status = status.HTTP_200_OK if overall_status == 'ok' else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(payload, status=http_status)


def _stub_response(endpoint_name: str) -> Response:
    """Return a consistent Phase 1 stub response for unimplemented endpoints."""
    return Response(
        {
            'status': 'not_implemented',
            'endpoint': endpoint_name,
            'phase': 2,
            'message': f'{endpoint_name} will be implemented in Phase 2+.',
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
def analytics_stub(request):
    """GET /api/analytics/ — Phase 2+ stub"""
    return _stub_response('analytics')


@api_view(['GET', 'POST'])
def chat_stub(request):
    """GET /api/chat/ — Phase 4 stub"""
    return _stub_response('chat')


@api_view(['GET'])
def excel_stub(request):
    """GET /api/excel/ — Phase 4 stub"""
    return _stub_response('excel')


@api_view(['GET'])
def reports_stub(request):
    """GET /api/reports/ — Phase 4 stub"""
    return _stub_response('reports')


@api_view(['GET'])
def topics_stub(request):
    """GET /api/topics/ — Phase 4 stub"""
    return _stub_response('topics')
