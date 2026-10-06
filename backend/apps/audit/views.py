"""
apps.audit — Views (Phase 9)
Provides authenticated, role-scoped access to immutable AuditEvent records.
"""

from datetime import datetime
import logging

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import status

from django.contrib.auth import get_user_model
from .models import AuditEvent, AuditEventType
from .serializers import AuditEventSerializer

User = get_user_model()

logger = logging.getLogger(__name__)


def _is_admin_or_manager(user) -> bool:
    """Check if user has administrative or managerial auditing privileges."""
    if not user or not user.is_authenticated:
        return False
    role = getattr(user, 'role', '')
    return bool(
        user.is_staff
        or user.is_superuser
        or role in ['admin', 'manager']
    )


class AuditPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_list(request):
    """
    GET /api/audit/
    Lists AuditEvent records with user/role scoping, filtering, reverse
    chronological ordering, and pagination.
    """
    if _is_admin_or_manager(request.user):
        queryset = AuditEvent.objects.all()
        actor = request.query_params.get('actor')
        if actor and actor.strip() and actor.strip().lower() != 'all':
            queryset = queryset.filter(actor__iexact=actor.strip())
    else:
        # Regular users are restricted strictly to their own audit records
        queryset = AuditEvent.objects.filter(actor=request.user.username)

    # Filter: event_type
    event_type = request.query_params.get('event_type')
    if event_type and event_type.strip() and event_type.strip().lower() != 'all':
        queryset = queryset.filter(event_type=event_type.strip())

    # Filter: resource_type
    resource_type = request.query_params.get('resource_type')
    if resource_type and resource_type.strip() and resource_type.strip().lower() != 'all':
        queryset = queryset.filter(resource_type=resource_type.strip())

    # Filter: date_from (YYYY-MM-DD)
    date_from = request.query_params.get('date_from')
    if date_from and date_from.strip():
        try:
            d_from = datetime.strptime(date_from.strip(), '%Y-%m-%d').date()
            queryset = queryset.filter(timestamp__date__gte=d_from)
        except ValueError:
            pass

    # Filter: date_to (YYYY-MM-DD)
    date_to = request.query_params.get('date_to')
    if date_to and date_to.strip():
        try:
            d_to = datetime.strptime(date_to.strip(), '%Y-%m-%d').date()
            queryset = queryset.filter(timestamp__date__lte=d_to)
        except ValueError:
            pass

    # Filter: search across description, resource_id, and actor
    search = request.query_params.get('search')
    if search and search.strip():
        term = search.strip()
        queryset = queryset.filter(
            Q(description__icontains=term) |
            Q(resource_id__icontains=term) |
            Q(actor__icontains=term)
        )

    # Reverse chronological ordering
    queryset = queryset.order_by('-timestamp')

    paginator = AuditPagination()
    page = paginator.paginate_queryset(queryset, request)
    serializer = AuditEventSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_detail(request, pk: int):
    """
    GET /api/audit/<pk>/
    Retrieve single audit event with role/ownership enforcement.
    """
    try:
        event = AuditEvent.objects.get(pk=pk)
    except AuditEvent.DoesNotExist:
        return Response({'error': 'Audit event not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not _is_admin_or_manager(request.user) and event.actor != request.user.username:
        return Response(
            {'error': 'You do not have permission to view this audit record.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = AuditEventSerializer(event)
    return Response(serializer.data, status=status.HTTP_200_OK)
