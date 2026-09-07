"""
apps.reports.services.engine — Report Engine (Phase 7 Orchestrator)

Coordinates report creation, lifecycle state transitions, generation execution,
editing, verification, approval, export, and audit trail logging.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from django.utils import timezone
from django.db import transaction

from apps.reports.models import Report, ReportStatus, ReportType
from apps.reports.services.registry import get_generator_for_type
from apps.datasets.models import StructuredDataset
from apps.documents.models import Document
from apps.audit.models import AuditEvent, AuditEventType

logger = logging.getLogger(__name__)


def log_report_audit_event(report: Report, user, action: str, details: Optional[Dict[str, Any]] = None):
    """Log an immutable audit event for a report action."""
    meta = {
        'action': action,
        'report_id': report.id,
        'report_title': report.title,
        'report_type': report.report_type,
        'status': report.status,
        'organization': report.organization,
        'date_range': report.date_range,
    }
    if details:
        meta.update(details)

    try:
        AuditEvent.objects.create(
            event_type=AuditEventType.AI_REPORT_GENERATED,
            actor=getattr(user, 'username', 'system'),
            actor_ip='127.0.0.1',
            resource_type='report',
            resource_id=str(report.id),
            description=f"Report #{report.id} '{report.title}' action: {action}",
            metadata_json=meta,
        )
    except Exception as e:
        logger.warning(f"Could not write report audit event: {e}")


class ReportEngine:
    """Central engine managing the complete Phase 7 Report Lifecycle."""

    @staticmethod
    def create_and_generate(
        user,
        title: Optional[str] = None,
        report_type: str = ReportType.PRODUCTION,
        organization: str = "CMPDI (HQ)",
        date_range: str = "All Available",
        filters: Optional[Dict[str, Any]] = None,
        source_dataset_ids: Optional[List[int]] = None,
        source_document_ids: Optional[List[int]] = None,
    ) -> Report:
        """
        Create a report and execute generation pipeline using real verified project data.
        """
        filters = filters or {}
        auto_title = title or f"{report_type} — {organization}"
        if date_range and date_range not in ("All Available", "All"):
            auto_title += f" ({date_range})"

        with transaction.atomic():
            report = Report.objects.create(
                title=auto_title,
                report_type=report_type,
                organization=organization,
                date_range=date_range,
                filters_json=filters,
                status=ReportStatus.GENERATING,
                created_by=user,
            )

            # Associate only owner-scoped datasets
            if source_dataset_ids:
                datasets = list(StructuredDataset.objects.filter(
                    id__in=source_dataset_ids,
                    source_document__uploaded_by=user
                ))
                report.source_datasets.set(datasets)
            else:
                datasets = list(StructuredDataset.objects.filter(
                    source_document__uploaded_by=user
                ))
                report.source_datasets.set(datasets)

            # Associate only owner-scoped documents
            if source_document_ids:
                docs = list(Document.objects.filter(
                    id__in=source_document_ids,
                    uploaded_by=user
                ))
                report.source_documents.set(docs)
            else:
                docs = list(Document.objects.filter(uploaded_by=user))
                report.source_documents.set(docs)

        # Execute generation
        try:
            generator_cls = get_generator_for_type(report.report_type)
            generator = generator_cls(
                user=user,
                organization=report.organization,
                date_range=report.date_range,
                filters=report.filters_json,
                datasets=list(report.source_datasets.all()),
                documents=list(report.source_documents.all()),
            )

            content, provenance = generator.generate()

            report.content_json = content
            report.provenance_json = provenance
            report.status = ReportStatus.GENERATED
            report.save(update_fields=['content_json', 'provenance_json', 'status', 'updated_at'])

            log_report_audit_event(report, user, 'report.generated', {
                'provenance_count': len(provenance),
                'kpi_count': len(content.get('kpis', [])),
                'table_count': len(content.get('tables', [])),
            })
            return report

        except Exception as exc:
            logger.exception(f"Report generation failed for report #{report.id}: {exc}")
            report.status = ReportStatus.FAILED
            report.error_message = str(exc)
            report.save(update_fields=['status', 'error_message', 'updated_at'])
            log_report_audit_event(report, user, 'report.failed', {'error': str(exc)})
            raise

    @staticmethod
    def edit_narrative(report: Report, user, narrative_updates: Dict[str, Any]) -> Report:
        """
        Safely update narrative sections of a report without modifying underlying source datasets.
        """
        if report.created_by != user:
            raise PermissionError("Only the report creator or designated authority can edit this report.")

        content = dict(report.content_json or {})
        for section in ('title', 'executive_summary', 'analysis', 'conclusions', 'notes'):
            if section in narrative_updates and narrative_updates[section] is not None:
                content[section] = str(narrative_updates[section]).strip()

        report.content_json = content
        report.revision_count += 1
        report.status = ReportStatus.UNDER_REVIEW
        report.save(update_fields=['content_json', 'revision_count', 'status', 'updated_at'])

        log_report_audit_event(report, user, 'report.edited', {
            'revision': report.revision_count,
            'edited_sections': list(narrative_updates.keys()),
        })
        return report

    @staticmethod
    def verify(report: Report, user) -> Report:
        """Mark report as verified."""
        if report.created_by != user:
            raise PermissionError("Unauthorized to verify this report.")
        if report.status in (ReportStatus.FAILED, ReportStatus.GENERATING):
            raise ValueError(f"Cannot verify a report in '{report.status}' status.")

        report.status = ReportStatus.VERIFIED
        report.verified_by = user
        report.verified_at = timezone.now()
        report.save(update_fields=['status', 'verified_by', 'verified_at', 'updated_at'])

        log_report_audit_event(report, user, 'report.verified', {
            'verified_at': report.verified_at.isoformat(),
        })
        return report

    @staticmethod
    def approve(report: Report, user, notes: str = "") -> Report:
        """Mark report as approved by user/authority."""
        if report.created_by != user:
            raise PermissionError("Unauthorized to approve this report.")
        if report.status in (ReportStatus.FAILED, ReportStatus.GENERATING):
            raise ValueError(f"Cannot approve a report in '{report.status}' status.")

        report.status = ReportStatus.APPROVED
        report.approved_by = user
        report.approved_at = timezone.now()
        report.approval_notes = notes.strip()
        report.save(update_fields=['status', 'approved_by', 'approved_at', 'approval_notes', 'updated_at'])

        log_report_audit_event(report, user, 'report.approved', {
            'approved_at': report.approved_at.isoformat(),
            'notes': report.approval_notes,
        })
        return report

    @staticmethod
    def export(report: Report, user, export_format: str = 'pdf') -> Tuple[bytes, str, str]:
        """
        Generate real file export for PDF, DOCX, or XLSX.
        Returns (bytes, content_type, filename).
        """
        if report.created_by != user:
            raise PermissionError("Unauthorized to export this report.")

        fmt = (export_format or 'pdf').lower().strip()
        safe_title = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in report.title)[:40]
        timestamp = timezone.now().strftime("%Y%m%d_%H%M")

        if fmt == 'pdf':
            from apps.reports.services.exporters.pdf_exporter import generate_pdf_report
            data = generate_pdf_report(report)
            content_type = 'application/pdf'
            filename = f"{safe_title}_{timestamp}.pdf"
        elif fmt in ('docx', 'doc'):
            from apps.reports.services.exporters.docx_exporter import generate_docx_report
            data = generate_docx_report(report)
            content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            filename = f"{safe_title}_{timestamp}.docx"
        elif fmt in ('xlsx', 'excel', 'xls'):
            from apps.reports.services.exporters.xlsx_exporter import generate_xlsx_report
            data = generate_xlsx_report(report)
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = f"{safe_title}_{timestamp}.xlsx"
        else:
            raise ValueError(f"Unsupported export format '{export_format}'. Supported formats: pdf, docx, xlsx.")

        report.export_format = fmt.upper()
        if report.status in (ReportStatus.GENERATED, ReportStatus.VERIFIED, ReportStatus.APPROVED):
            report.status = ReportStatus.EXPORTED
        report.save(update_fields=['export_format', 'status', 'updated_at'])

        log_report_audit_event(report, user, 'report.exported', {
            'format': fmt.upper(),
            'filename': filename,
            'file_size_bytes': len(data),
        })

        return data, content_type, filename
