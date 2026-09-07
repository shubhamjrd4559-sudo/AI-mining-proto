"""
apps.reports.services.exporters.pdf_exporter — Publication-Quality PDF Exporter

Uses ReportLab to generate publication-grade official CMPDI / CIL reports.
"""

import io
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
from reportlab.pdfgen import canvas

from apps.reports.models import Report


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and render total page count."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Header rule & text
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(40, 800, 555, 800)
        self.drawString(40, 805, "CMPDI · Coal India Limited — AI Mining Intelligence Command Center")

        # Footer rule & text
        self.line(40, 45, 555, 45)
        self.drawString(40, 32, "Confidential · Official Government / Subsidiary Record")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(555, 32, page_str)
        self.restoreState()


def generate_pdf_report(report: Report) -> bytes:
    """
    Generate official PDF bytes for a given Report instance.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    navy = colors.HexColor("#071A3D")
    royal = colors.HexColor("#0B4DB8")
    charcoal = colors.HexColor("#1E293B")
    muted = colors.HexColor("#64748B")

    title_style = ParagraphStyle(
        'RepTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=navy,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        'RepSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=muted,
        spaceAfter=14,
    )
    section_style = ParagraphStyle(
        'RepSection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=royal,
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        'RepBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=charcoal,
        spaceAfter=8,
    )
    table_cell_style = ParagraphStyle(
        'RepCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=charcoal,
    )
    table_hdr_style = ParagraphStyle(
        'RepHdrCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )

    content = report.content_json or {}
    story = []

    # Title & Metadata
    rep_title = content.get('title') or report.title
    story.append(Paragraph(rep_title, title_style))

    meta_text = (
        f"<b>Report Type:</b> {report.report_type} &nbsp;|&nbsp; "
        f"<b>Organization:</b> {report.organization} &nbsp;|&nbsp; "
        f"<b>Period:</b> {report.date_range} &nbsp;|&nbsp; "
        f"<b>Status:</b> {report.status} &nbsp;|&nbsp; "
        f"<b>Generated:</b> {content.get('generated_at') or report.created_at.strftime('%Y-%m-%d %H:%M')}"
    )
    story.append(Paragraph(meta_text, subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=12))

    # Executive Summary Box
    exec_summary = content.get('executive_summary', '')
    if exec_summary:
        story.append(Paragraph("Executive Summary", section_style))
        summary_p = Paragraph(f"<i>{exec_summary}</i>", body_style)
        summary_table = Table(
            [[summary_p]],
            colWidths=[515],
        )
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 10))

    # Key Performance Indicators (KPIs)
    kpis = content.get('kpis', [])
    if kpis:
        story.append(Paragraph("Key Performance Indicators (KPIs)", section_style))
        kpi_cells = []
        for k in kpis[:4]:
            val_p = Paragraph(f"<font size=14 color='#0B4DB8'><b>{k.get('value', '—')}</b></font>", body_style)
            lbl_p = Paragraph(f"<b>{k.get('label', '')}</b>", table_cell_style)
            chg_p = Paragraph(f"<font size=7.5 color='#64748B'>{k.get('change', '')}</font>", table_cell_style)
            kpi_cells.append([val_p, lbl_p, chg_p])

        # Arrange in a grid row of cards
        row_data = []
        for cell in kpi_cells:
            inner_tbl = Table(
                [[cell[0]], [cell[1]], [cell[2]]],
                colWidths=[122],
            )
            inner_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EEF2F8")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#DCE5F2")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            row_data.append(inner_tbl)

        kpi_table = Table([row_data], colWidths=[128] * len(row_data))
        kpi_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 12))

    # Tables
    tables = content.get('tables', [])
    for t in tables:
        story.append(Paragraph(t.get('title', 'Data Table'), section_style))
        if t.get('description'):
            story.append(Paragraph(t.get('description'), subtitle_style))

        cols = t.get('columns', [])
        rows = t.get('rows', [])
        if cols and rows:
            tbl_data = []
            hdr_row = [Paragraph(c, table_hdr_style) for c in cols]
            tbl_data.append(hdr_row)
            for r in rows[:20]:
                data_row = [Paragraph(str(c), table_cell_style) for c in r]
                tbl_data.append(data_row)

            # Auto calculate col width
            avail_w = 515
            c_w = avail_w / len(cols)
            rpt_table = Table(tbl_data, colWidths=[c_w] * len(cols))
            rpt_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), navy),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]))
            story.append(rpt_table)
            if t.get('source'):
                story.append(Paragraph(f"<font size=7.5 color='#64748B'><i>Source: {t.get('source')}</i></font>", body_style))
            story.append(Spacer(1, 12))

    # Analysis Section
    analysis = content.get('analysis', '')
    if analysis:
        story.append(Paragraph("Operational & Geological Analysis", section_style))
        for para in analysis.split('\n\n'):
            if para.strip():
                story.append(Paragraph(para.strip(), body_style))
        story.append(Spacer(1, 8))

    # Conclusions Section
    conclusions = content.get('conclusions', '')
    if conclusions:
        story.append(Paragraph("Strategic Conclusions & Action Items", section_style))
        for line in conclusions.split('\n'):
            if line.strip():
                story.append(Paragraph(line.strip(), body_style))
        story.append(Spacer(1, 10))

    # Provenance / Source Traceability Section
    provenance = report.provenance_json or []
    if provenance:
        story.append(Paragraph("Source Traceability & Audit Provenance", section_style))
        prov_rows = [
            [
                Paragraph("Source Type", table_hdr_style),
                Paragraph("Document / Dataset", table_hdr_style),
                Paragraph("Sheet / Page", table_hdr_style),
                Paragraph("Row / Ref", table_hdr_style),
                Paragraph("Extraction Method", table_hdr_style),
            ]
        ]
        for p in provenance[:15]:
            p_type = p.get('source_type', 'dataset').upper()
            name = p.get('name') or p.get('document_title') or 'Verified Dataset'
            pg_sheet = f"p. {p.get('page_number')}" if p.get('page_number') else (p.get('sheet_name') or 'Main')
            row_ref = p.get('source_ref') or f"Row {p.get('row_index', '—')}"
            method = f"{p.get('extractor_type', 'doc')} ({int((p.get('confidence') or 1.0)*100)}%)"

            prov_rows.append([
                Paragraph(p_type, table_cell_style),
                Paragraph(name[:30], table_cell_style),
                Paragraph(str(pg_sheet), table_cell_style),
                Paragraph(str(row_ref), table_cell_style),
                Paragraph(method, table_cell_style),
            ])

        prov_table = Table(prov_rows, colWidths=[65, 160, 90, 100, 100])
        prov_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#334155")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ]))
        story.append(prov_table)
        story.append(Spacer(1, 14))

    # Approval Sign-off Box
    signoff_data = [
        [
            Paragraph(f"<b>Verification Status:</b> {report.status}", table_cell_style),
            Paragraph(f"<b>Verified By:</b> {report.verified_by.username if report.verified_by else 'Pending'}", table_cell_style),
            Paragraph(f"<b>Approved By:</b> {report.approved_by.username if report.approved_by else 'Pending'}", table_cell_style),
        ],
        [
            Paragraph(f"<b>Revision:</b> #{report.revision_count}", table_cell_style),
            Paragraph(f"<b>Verified At:</b> {report.verified_at.strftime('%Y-%m-%d %H:%M') if report.verified_at else '—'}", table_cell_style),
            Paragraph(f"<b>Approved At:</b> {report.approved_at.strftime('%Y-%m-%d %H:%M') if report.approved_at else '—'}", table_cell_style),
        ]
    ]
    if report.approval_notes:
        signoff_data.append([Paragraph(f"<b>Remarks / Authority Notes:</b> {report.approval_notes}", table_cell_style), "", ""])

    signoff_table = Table(signoff_data, colWidths=[170, 170, 175])
    signoff_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ('SPAN', (0, 2), (-1, 2)) if report.approval_notes else ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(KeepTogether([
        Paragraph("Governance & Authority Sign-off", section_style),
        signoff_table
    ]))

    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
