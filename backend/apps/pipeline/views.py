from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from apps.documents.models import Document
from .models import ExtractionResult, ValidationResult
from .serializers import ExtractionResultSerializer, ValidationResultSerializer


def _require_owner(doc, request):
    if doc.uploaded_by and doc.uploaded_by != request.user:
        return True  # forbidden
    return False


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def extraction_detail(request, pk):
    """GET /api/documents/<pk>/extraction/"""
    doc = get_object_or_404(Document, pk=pk, is_archived=False)
    if _require_owner(doc, request):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    try:
        ex_result = doc.extraction_result
    except ExtractionResult.DoesNotExist:
        return Response({'detail': 'Extraction not yet run for this document.'},
                        status=status.HTTP_404_NOT_FOUND)
    
    validation_qs = ValidationResult.objects.filter(document=doc)
    
    data = ExtractionResultSerializer(ex_result, context={'request': request}).data
    data['validation_findings'] = ValidationResultSerializer(
        validation_qs[:50], many=True  # cap at 50 findings in detail view
    ).data
    data['has_provenance'] = ex_result.document.extraction_provenance.exists() if hasattr(ex_result.document, 'extraction_provenance') else False
    data['tables_count'] = len(ex_result.extracted_tables)
    
    return Response(data)
