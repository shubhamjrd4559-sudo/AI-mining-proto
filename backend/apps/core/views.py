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

from django.conf import settings
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    GET /api/health/

    Returns service health status including database connectivity.
    Includes debug flag so the frontend can show dev credential hints
    when the backend is running in DEBUG mode.
    """
    db_status = 'connected'
    db_error = None

    try:
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
        'version': '2.0.0-phase2',
        'phase': 2,
        'database': db_status,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        # Expose debug flag so frontend can display dev credential hints
        'debug': bool(getattr(settings, 'DEBUG', False)),
    }

    if db_error:
        payload['database_error'] = db_error

    http_status = status.HTTP_200_OK if overall_status == 'ok' else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(payload, status=http_status)


@api_view(['GET'])
@permission_classes([AllowAny])
def current_user(request):
    """
    GET /api/auth/me/
    Returns the currently authenticated user's details, role, and permissions.
    """
    if request.user and request.user.is_authenticated:
        is_admin = request.user.is_superuser or request.user.is_staff or request.user.username.lower() == 'admin'
        role = "Administrator · CMPDI" if is_admin else "Contributor · CMPDI"
        return Response({
            "authenticated": True,
            "username": request.user.username,
            "email": request.user.email or f"{request.user.username.lower()}@cmpdi.local",
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "is_staff": request.user.is_staff,
            "is_superuser": request.user.is_superuser,
            "role": role,
        }, status=status.HTTP_200_OK)
    return Response({
        "authenticated": False,
        "username": None,
        "email": None,
        "is_staff": False,
        "is_superuser": False,
        "role": None,
    }, status=status.HTTP_200_OK)


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
@permission_classes([AllowAny])
def analytics_stub(request):
    """GET /api/analytics/ — Phase 2+ stub"""
    return _stub_response('analytics')


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def chat_stub(request):
    """
    GET /api/chat/  — Phase 1 stub compatibility
    POST /api/chat/ — Phase 5 authenticated RAG Mining Intelligence Query

    IMPORTANT: We call execute_query() directly rather than query_view(request).
    Calling another @api_view as a function causes DRF to re-wrap the already-wrapped
    DRF Request, raising:
      AssertionError: The `request` argument must be an instance of
      django.http.HttpRequest, not rest_framework.request.Request.
    execute_query() is a plain function that accepts a DRF Request safely.
    """
    if request.method == 'POST':
        if not request.user or not request.user.is_authenticated:
            return Response(
                {'detail': 'Authentication credentials were not provided.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        from apps.intelligence.views import execute_query
        return execute_query(request)
    return _stub_response('chat')


@api_view(['GET'])
@permission_classes([AllowAny])
def excel_stub(request):
    """GET /api/excel/ — Phase 4 stub"""
    return _stub_response('excel')


@api_view(['GET'])
@permission_classes([AllowAny])
def reports_stub(request):
    """GET /api/reports/ — Phase 4 stub"""
    return _stub_response('reports')


@api_view(['GET'])
@permission_classes([AllowAny])
def topics_stub(request):
    """GET /api/topics/ — Phase 4 stub"""
    return _stub_response('topics')

