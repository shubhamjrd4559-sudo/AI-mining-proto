"""
apps.documents — Views (Phase 1 stub)

GET /api/documents/ — returns not_implemented stub.
Full CRUD implemented in Phase 2.
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


@api_view(['GET'])
def document_list_stub(request):
    """
    GET /api/documents/
    Phase 1 stub — returns not_implemented.
    Phase 2: Real list + POST upload.
    """
    return Response(
        {
            'status': 'not_implemented',
            'endpoint': 'documents',
            'phase': 2,
            'message': 'Document upload and listing will be implemented in Phase 2.',
        },
        status=status.HTTP_200_OK,
    )
