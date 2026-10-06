"""
apps.reports.services.exporters.pdf_exporter — Publication-Quality PDF Exporter

Uses ReportLab to generate publication-grade official CMPDI / CIL reports.
Supports both single-document operational reports and advanced comparative intelligence reports
with native vector charts, 16-section structure, and dual-source provenance.
"""

import io
from typing import Dict, Any, List, Optional
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend

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


def _create_chart_drawing(chart_dict: Dict[str, Any], width: float = 515, height: float = 160) -> Optional[Drawing]:
    """
    Build a native ReportLab grouped bar chart drawing with legend.
    """
    categories = chart_dict.get('categories', [])
    past_series = chart_dict.get('past_series', [])
    curr_series = chart_dict.get('curr_series', [])

    if not categories or not past_series or not curr_series:
        return None

    d = Drawing(width, height)

    chart = VerticalBarChart()
    chart.x = 45
    chart.y = 25
    chart.height = height - 55
    chart.width = width - 65
    chart.data = [past_series, curr_series]
    chart.categoryAxis.categoryNames = categories
    chart.categoryAxis.labels.fontSize = 8
    chart.categoryAxis.labels.fontName = 'Helvetica-Bold'
    chart.categoryAxis.labels.fillColor = colors.HexColor('#1E293B')

    # Color palette
    chart.bars[0].fillColor = colors.HexColor('#64748B')  # Past / Reference
    chart.bars[1].fillColor = colors.HexColor('#0B4DB8')  # Current / User Upload

    # Compute max value for value axis
    all_vals = [v for v in past_series + curr_series if v is not None]
    max_val = max(all_vals) if all_vals else 100
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max_val * 1.15
    chart.valueAxis.labels.fontSize = 7.5

    # Add Legend
    legend = Legend()
    legend.x = width - 230
    legend.y = height - 12
    legend.alignment = 'right'
    past_lbl = chart_dict.get('past_label', 'Past Baseline')
    curr_lbl = chart_dict.get('curr_label', 'Current Upload')
    legend.colorNamePairs = [
        (colors.HexColor('#64748B'), past_lbl[:22]),
        (colors.HexColor('#0B4DB8'), curr_lbl[:22]),
    ]
    legend.fontName = 'Helvetica'
    legend.fontSize = 7.5

    d.add(chart)
    d.add(legend)
    return d


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
        fontSize=17,
        leading=21,
        textColor=navy,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        'RepSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=muted,
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        'RepSection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=royal,
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        'RepBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=charcoal,
        spaceAfter=6,
    )
    table_cell_style = ParagraphStyle(
        'RepCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=charcoal,
    )
    table_hdr_style = ParagraphStyle(
        'RepHdrCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=colors.white,
    )
    callout_hdr_style = ParagraphStyle(
        'CalloutHdr',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=navy,
    )

    content = report.content_json or {}
    is_comparative = content.get('is_comparative', False)
    story = []

    # 1. Title & Metadata Header
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
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    # 2. Source Role Callout Table (When Comparative)
    source_roles = content.get('source_roles')
    if is_comparative and source_roles:
        org_r = source_roles.get('org_reference', {})
        curr_r = source_roles.get('current_upload', {})

        role_table_data = [
            [
                Paragraph("<b>HISTORICAL / ORGANIZATION REFERENCE</b>", callout_hdr_style),
                Paragraph("<b>CURRENT USER-UPLOADED REPORT</b>", callout_hdr_style),
            ],
            [
                Paragraph(f"<b>Source:</b> {org_r.get('title', 'N/A')}<br/><b>Period:</b> {org_r.get('period', 'N/A')}<br/><b>Status:</b> Protected Baseline Reference", table_cell_style),
                Paragraph(f"<b>Source:</b> {curr_r.get('title', 'N/A')}<br/><b>Period:</b> {curr_r.get('period', 'N/A')}<br/><b>Status:</b> Newly Ingested Document", table_cell_style),
            ]
        ]
        role_table = Table(role_table_data, colWidths=[255, 260])
        role_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#F1F5F9")),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor("#EFF6FF")),
            ('BACKGROUND', (0, 1), (0, 1), colors.HexColor("#F8FAFC")),
            ('BACKGROUND', (1, 1), (1, 1), colors.HexColor("#F0F7FF")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
            ('LINEAFTER', (0, 0), (0, -1), 1, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(role_table)
        story.append(Spacer(1, 10))

    # 3. Executive Summary Box
    exec_summary = content.get('executive_summary', '')
    if exec_summary:
        story.append(Paragraph("Executive Summary", section_style))
        summary_p = Paragraph(f"<i>{exec_summary}</i>", body_style)
        summary_table = Table([[summary_p]], colWidths=[515])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 10))

    # 4. Top Improvements & Top Declines Box (When Comparative)
    top_imp = content.get('top_improvements')
    top_dec = content.get('top_declines')
    if is_comparative and (top_imp or top_dec):
        imp_p = Paragraph(f"<b>Top Performance Improvements:</b><br/>{top_imp.replace(chr(10), '<br/>')}", table_cell_style)
        dec_p = Paragraph(f"<b>Top Performance Declines:</b><br/>{top_dec.replace(chr(10), '<br/>')}", table_cell_style)

        imp_table = Table([[imp_p, dec_p]], colWidths=[255, 260])
        imp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#F0FDF4")),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor("#FEF2F2")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
            ('LINEAFTER', (0, 0), (0, -1), 1, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(imp_table)
        story.append(Spacer(1, 10))

    # 5. Key Performance Indicators (KPIs)
    kpis = content.get('kpis', [])
    if kpis:
        story.append(Paragraph("Key Performance Indicators (KPIs)", section_style))
        kpi_cells = []
        for k in kpis[:4]:
            val_p = Paragraph(f"<font size=13 color='#0B4DB8'><b>{k.get('value', '—')}</b></font>", body_style)
            lbl_p = Paragraph(f"<b>{k.get('label', '')}</b>", table_cell_style)
            chg_p = Paragraph(f"<font size=7.5 color='#64748B'>{k.get('change', '')}</font>", table_cell_style)
            kpi_cells.append([val_p, lbl_p, chg_p])

        row_data = []
        for cell in kpi_cells:
            inner_tbl = Table([[cell[0]], [cell[1]], [cell[2]]], colWidths=[122])
            inner_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EEF2F8")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#DCE5F2")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            row_data.append(inner_tbl)

        kpi_table = Table([row_data], colWidths=[128] * len(row_data))
        kpi_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 12))

    # 6. Comparative Visual Charts (Native ReportLab)
    chart_data = content.get('chart_data', {})
    if is_comparative and chart_data:
        grouped = chart_data.get('grouped_metrics')
        subs_chart = chart_data.get('subsidiary_metrics')

        if chart_data.get('has_chart'):
            story.append(Paragraph("Visual Comparative Intelligence", section_style))

            if grouped and grouped.get('categories'):
                chart_drawing = _create_chart_drawing(grouped, width=515, height=155)
                if chart_drawing:
                    story.append(Paragraph("<b>Figure 1: Organization Baseline vs Current Performance (Production, Target, Dispatch)</b>", subtitle_style))
                    story.append(chart_drawing)
                    story.append(Spacer(1, 10))

            if subs_chart and subs_chart.get('categories'):
                subs_drawing = _create_chart_drawing(subs_chart, width=515, height=155)
                if subs_drawing:
                    story.append(Paragraph("<b>Figure 2: Subsidiary Output Comparison (Raw Coal Production in MT)</b>", subtitle_style))
                    story.append(subs_drawing)
                    story.append(Spacer(1, 10))
        else:
            story.append(Paragraph("Visual Comparative Charting", section_style))
            no_chart_table = Table([[Paragraph("<i>Insufficient overlapping numerical categories between selected sources to render a comparative bar chart.</i>", body_style)]], colWidths=[515])
            no_chart_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(no_chart_table)
            story.append(Spacer(1, 10))

    # 7. Tables
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
            for r in rows[:25]:
                data_row = [Paragraph(str(c), table_cell_style) for c in r]
                tbl_data.append(data_row)

            avail_w = 515
            c_w = avail_w / len(cols)
            rpt_table = Table(tbl_data, colWidths=[c_w] * len(cols))
            rpt_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), navy),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]))
            story.append(rpt_table)
            if t.get('source'):
                story.append(Paragraph(f"<font size=7.5 color='#64748B'><i>Source: {t.get('source')}</i></font>", body_style))
            story.append(Spacer(1, 10))

    # 8. Comparative Findings Sections (When Comparative)
    if is_comparative:
        what_org = content.get('what_org_says')
        what_curr = content.get('what_current_says')
        what_chg = content.get('what_changed')
        ref_bench = content.get('reference_benchmarks')
        new_info = content.get('newly_available')
        missing_info = content.get('missing_information')
        ai_insights = content.get('ai_insights', [])

        if what_org or what_curr or what_chg:
            story.append(Paragraph("Cross-Report Comparative Findings", section_style))
            if what_org:
                story.append(Paragraph("<b>What the Organization Reference Report Says:</b>", callout_hdr_style))
                story.append(Paragraph(what_org, body_style))
            if what_curr:
                story.append(Paragraph("<b>What the Current Report Says:</b>", callout_hdr_style))
                story.append(Paragraph(what_curr, body_style))
            if what_chg:
                story.append(Paragraph("<b>What Changed (Operational Variances):</b>", callout_hdr_style))
                for line in what_chg.split('\n'):
                    if line.strip():
                        story.append(Paragraph(line.strip(), body_style))
            story.append(Spacer(1, 8))

        if ref_bench:
            story.append(Paragraph("Rules, Benchmarks & Reference Standards", section_style))
            for line in ref_bench.split('\n'):
                if line.strip():
                    story.append(Paragraph(line.strip(), body_style))
            story.append(Spacer(1, 8))

        if new_info:
            story.append(Paragraph("Newly Available Information in Current Report", section_style))
            new_box = Table([[Paragraph(new_info.replace('\n', '<br/>'), body_style)]], colWidths=[515])
            new_box.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#BBF7D0")),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(new_box)
            story.append(Spacer(1, 8))

        if missing_info:
            story.append(Paragraph("Missing / Unavailable Information Disclosure", section_style))
            miss_box = Table([[Paragraph(f"<i>The following metrics were not identified in the selected sources. They are not assumed or interpolated as zero:</i><br/>{missing_info.replace(chr(10), '<br/>')}", body_style)]], colWidths=[515])
            miss_box.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#FFFBEB")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#FDE68A")),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(miss_box)
            story.append(Spacer(1, 8))

        if ai_insights:
            story.append(Paragraph("AI-Generated Operational Insights (Strictly Grounded)", section_style))
            for i, insight in enumerate(ai_insights, 1):
                story.append(Paragraph(f"<b>{i}.</b> {insight}", body_style))
            story.append(Spacer(1, 8))

    # 9. Analysis Section
    analysis = content.get('analysis', '')
    if analysis:
        story.append(Paragraph("Operational Analysis & Synthesis", section_style))
        for para in analysis.split('\n\n'):
            if para.strip():
                story.append(Paragraph(para.strip(), body_style))
        story.append(Spacer(1, 8))

    # 10. Conclusions Section
    conclusions = content.get('conclusions', '')
    if conclusions:
        story.append(Paragraph("Strategic Conclusions & Action Items", section_style))
        for line in conclusions.split('\n'):
            if line.strip():
                story.append(Paragraph(line.strip(), body_style))
        story.append(Spacer(1, 10))

    # 11. Provenance / Source Traceability Section
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
            row_ref = p.get('source_ref') or f"Row {p.get('row_index', '-')}"
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
        story.append(Spacer(1, 12))

    # 12. Approval Sign-off Box
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
