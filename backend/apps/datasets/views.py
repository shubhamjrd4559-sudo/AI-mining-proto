"""
apps.datasets — Views (Phase 1 stub)
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


@api_view(['GET'])
def dataset_list_stub(request):
    """GET /api/datasets/ — Phase 1 stub"""
    return Response(
        {
            'status': 'not_implemented',
            'endpoint': 'datasets',
            'phase': 2,
            'message': 'Dataset listing will be implemented in Phase 2.',
        },
        status=status.HTTP_200_OK,
    )
