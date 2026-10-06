"""
apps.intelligence — Views for RAG Query, History, and Re-indexing.
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.audit.models import AuditEvent, AuditEventType
from .models import AIQueryLog
from .serializers import AIQueryInputSerializer, AIQueryLogSerializer
from .generator.answer_engine import generate_grounded_answer
from .indexing.indexer import reindex_all_documents

logger = logging.getLogger(__name__)


def _get_client_ip(request) -> str:
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def execute_query(request) -> Response:
    """
    Core RAG query business logic — accepts a DRF Request object directly.

    This is a plain function (NOT an @api_view) so it is safe to call from
    any other @api_view without triggering DRF's double-wrapping assertion
    ("The `request` argument must be an instance of django.http.HttpRequest,
    not rest_framework.request.Request").

    Both query_view (at /api/intelligence/query/) and chat_stub (at /api/chat/)
    delegate here instead of calling each other as view functions.
    """
    serializer = AIQueryInputSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    question = serializer.validated_data['query']
    document_id = serializer.validated_data.get('document_id')

    try:
        result = generate_grounded_answer(request.user, question, document_id=document_id)

        # Record in persistent query history
        AIQueryLog.objects.create(
            user=request.user,
            question=question,
            query_type=result['query_type'],
            answer=result['answer'],
            confidence=result['confidence'],
            sources=result['sources'],
            evidence_count=result['evidence_count'],
            source_count=result['source_count'],
        )

        # Record immutable audit event
        try:
            AuditEvent.objects.create(
                event_type=AuditEventType.AI_QUERY_SUBMITTED,
                actor=request.user.username,
                actor_ip=_get_client_ip(request),
                resource_type='ai_query',
                description=f"AI query executed ({result['query_type']}, {result['confidence']}): '{question[:80]}'",
                metadata_json={
                    'query_type': result['query_type'],
                    'confidence': result['confidence'],
                    'source_count': result['source_count'],
                    'evidence_count': result['evidence_count'],
                }
            )
        except Exception as audit_exc:
            logger.warning('Could not write audit log for AI query: %s', audit_exc)

        return Response(result, status=status.HTTP_200_OK)

    except Exception as exc:
        logger.error('Error executing AI query: %s', exc, exc_info=True)
        return Response(
            {'error': 'An internal error occurred while processing your query.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def query_view(request):
    """
    POST /api/intelligence/query/
    Execute grounded RAG query over user's documents and structured datasets.
    """
    if request.method == 'GET':
        return Response({
            'service': 'CMPDI Mining Intelligence AI',
            'status': 'active',
            'endpoint': 'POST with {"message": "..."} to query',
        })
    return execute_query(request)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def query_history_view(request):
    """
    GET /api/intelligence/history/
    Retrieve query history for the authenticated user.
    """
    logs = AIQueryLog.objects.filter(user=request.user).order_by('-created_at')[:50]
    serializer = AIQueryLogSerializer(logs, many=True)
    return Response({'results': serializer.data, 'count': len(serializer.data)}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reindex_view(request):
    """
    POST /api/intelligence/reindex/
    Trigger re-indexing of all processed documents belonging to the user.
    """
    try:
        indexed_docs, total_chunks = reindex_all_documents(user=request.user, force=True)
        return Response({
            'status': 'success',
            'indexed_documents': indexed_docs,
            'created_chunks': total_chunks,
        }, status=status.HTTP_200_OK)
    except Exception as exc:
        logger.error('Reindexing failed: %s', exc, exc_info=True)
        return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
