"""
apps.reports.views — Report API Views (Phase 7)

All endpoints strictly enforce:
  - TokenAuthentication / SessionAuthentication (IsAuthenticated)
  - Strict owner-scoping (created_by == request.user)
  - Complete lifecycle state transitions: GENERATE → REVIEW → EDIT → VERIFY → APPROVE → EXPORT
"""

import logging
from typing import Optional, Tuple
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.reports.models import Report, ReportType, ReportStatus
from apps.reports.serializers import (
    ReportListSerializer,
    ReportDetailSerializer,
    ReportGenerateRequestSerializer,
    ReportEditSerializer,
    ReportApproveSerializer,
)
from apps.reports.services.engine import ReportEngine
from apps.datasets.models import StructuredDataset
from apps.documents.models import Document

logger = logging.getLogger(__name__)


def _get_owned_report(report_id: int, user) -> Tuple[Optional[Report], Optional[Response]]:
    """Verify report exists and belongs to the requesting user."""
    try:
        report = Report.objects.get(pk=report_id)
    except (Report.DoesNotExist, ValueError):
        return None, Response({'error': 'Report not found.'}, status=status.HTTP_404_NOT_FOUND)

    if report.created_by != user:
        return None, Response(
            {'error': 'You do not have permission to access this report.'},
            status=status.HTTP_403_FORBIDDEN
        )
    return report, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def report_options(request):
    """
    Get available report types, user's structured datasets, uploaded documents,
    subsidiaries, and date periods for configuring a report.
    """
    datasets = StructuredDataset.objects.filter(
        source_document__uploaded_by=request.user
    ).values('id', 'name', 'record_count')

    documents = Document.objects.filter(
        uploaded_by=request.user
    ).values('id', 'title', 'status', 'created_at')

    # Available report types with metadata
    types = [
        {'key': ReportType.PRODUCTION, 'label': 'Production Report', 'icon': '📊', 'description': 'Subsidiary and national raw coal production, targets and dispatch summaries.'},
        {'key': ReportType.GEOLOGICAL_EXPLORATION, 'label': 'Geological & Exploration Report', 'icon': '⛏', 'description': 'Exploration status, borehole evaluation, and coal grade distribution.'},
        {'key': ReportType.MINING_PERFORMANCE, 'label': 'Mining Performance Report', 'icon': '🏭', 'description': 'Mine-level target vs actual operational performance and evacuation efficiency.'},
        {'key': ReportType.EXPLORATION, 'label': 'Exploration Report', 'icon': '🧭', 'description': 'Exploration blocks, drilling status, and stratigraphic survey findings.'},
        {'key': ReportType.COAL_SEAM, 'label': 'Coal Seam Analysis', 'icon': '🔬', 'description': 'Proximate quality, seam thickness, coal type, and GCV grade matrix.'},
        {'key': ReportType.PARLIAMENTARY_QUESTION, 'label': 'Parliamentary Question Response', 'icon': '🏛', 'description': 'Official point-by-point reply for Ministry of Coal parliamentary queries.'},
        {'key': ReportType.ADMINISTRATIVE_QUERY, 'label': 'Administrative Query', 'icon': '📁', 'description': 'Internal governance, operational compliance, and ledger audit verification.'},
        {'key': ReportType.CUSTOM, 'label': 'Custom Report', 'icon': '⚙', 'description': 'Multi-dimensional report synthesizing custom parameters across datasets and documents.'},
    ]

    subsidiaries = ['CMPDI (HQ)', 'SECL', 'MCL', 'NCL', 'CCL', 'WCL', 'ECL', 'BCCL']
    ranges = ['All Available', 'FY 2021-22', 'FY 2022-23', 'FY 2023-24', 'FY 2024-25', 'FY 2025-26']

    return Response({
        'report_types': types,
        'datasets': list(datasets),
        'documents': list(documents),
        'subsidiaries': subsidiaries,
        'date_ranges': ranges,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def report_list(request):
    """List all reports created by the requesting user."""
    qs = Report.objects.filter(created_by=request.user).select_related('created_by', 'verified_by', 'approved_by')

    r_type = request.query_params.get('report_type')
    if r_type:
        qs = qs.filter(report_type=r_type)

    r_status = request.query_params.get('status')
    if r_status:
        qs = qs.filter(status=r_status)

    serializer = ReportListSerializer(qs, many=True)
    return Response({'reports': serializer.data, 'count': qs.count()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def report_generate(request):
    """Create and generate an official report from real verified project data."""
    serializer = ReportGenerateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    try:
        report = ReportEngine.create_and_generate(
            user=request.user,
            title=data.get('title'),
            report_type=data.get('report_type', ReportType.PRODUCTION),
            organization=data.get('organization', 'CMPDI (HQ)'),
            date_range=data.get('date_range', 'All Available'),
            filters=data.get('filters', {}),
            source_dataset_ids=data.get('source_dataset_ids', []),
            source_document_ids=data.get('source_document_ids', []),
        )
        return Response(ReportDetailSerializer(report).data, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.exception("Failed to generate report")
        return Response({'error': f"Report generation failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def report_detail(request, report_id):
    """Retrieve or delete an existing report."""
    report, error_response = _get_owned_report(report_id, request.user)
    if error_response:
        return error_response

    if request.method == 'DELETE':
        report.delete()
        return Response({'message': 'Report deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)

    return Response(ReportDetailSerializer(report).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def report_edit(request, report_id):
    """
    Safely edit narrative sections of a report.
    Source datasets are NEVER modified.
    """
    report, error_response = _get_owned_report(report_id, request.user)
    if error_response:
        return error_response

    serializer = ReportEditSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        updated = ReportEngine.edit_narrative(report, request.user, serializer.validated_data)
        return Response(ReportDetailSerializer(updated).data)
    except PermissionError as pe:
        return Response({'error': str(pe)}, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def report_verify(request, report_id):
    """Mark report as verified by user/authority."""
    report, error_response = _get_owned_report(report_id, request.user)
    if error_response:
        return error_response

    try:
        updated = ReportEngine.verify(report, request.user)
        return Response(ReportDetailSerializer(updated).data)
    except ValueError as ve:
        return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
    except PermissionError as pe:
        return Response({'error': str(pe)}, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def report_approve(request, report_id):
    """Mark report as approved with optional sign-off remarks."""
    report, error_response = _get_owned_report(report_id, request.user)
    if error_response:
        return error_response

    serializer = ReportApproveSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    notes = serializer.validated_data.get('notes', '')
    try:
        updated = ReportEngine.approve(report, request.user, notes=notes)
        return Response(ReportDetailSerializer(updated).data)
    except ValueError as ve:
        return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
    except PermissionError as pe:
        return Response({'error': str(pe)}, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def report_export(request, report_id, export_format):
    """
    Download a real publication-grade PDF, DOCX, or XLSX file.
    """
    report, error_response = _get_owned_report(report_id, request.user)
    if error_response:
        return error_response

    try:
        file_bytes, content_type, filename = ReportEngine.export(report, request.user, export_format)
        response = HttpResponse(file_bytes, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(file_bytes)
        return response
    except ValueError as ve:
        return Response({'error': str(ve)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Export failed")
        return Response({'error': f"Export failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
