"""
apps.audit — Views (Phase 1 stub)
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


@api_view(['GET'])
def audit_list_stub(request):
    """GET /api/audit/ — Phase 1 stub"""
    return Response(
        {
            'status': 'not_implemented',
            'endpoint': 'audit',
            'phase': 2,
            'message': 'Audit log API will be implemented in Phase 2.',
        },
        status=status.HTTP_200_OK,
    )
