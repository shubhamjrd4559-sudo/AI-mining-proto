"""
apps.reports.services.exporters.xlsx_exporter — Professional Excel (XLSX) Report Exporter

Uses openpyxl to generate publication-grade, structured, readable Excel workbooks from
the existing report content without recalculating or modifying underlying report data.

Sheets:
  1. Summary & KPIs — Title banner, metadata, executive summary, KPI comparison table,
     top improvements/declines, and governance sign-off.
  2. Report Data — Detailed comparison tables (Key metrics, Subsidiary breakdown,
     Financials, Coverage matrix, New discovery, Missing info, and Grounded insights).
  3. Provenance & Audit — Traceability ledger with frozen header and auto-filters.
"""

import io
import re
from typing import Dict, Any, List, Optional, Tuple
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from apps.reports.models import Report


# -------------------------------------------------------------
# Color Palette & Styles
# -------------------------------------------------------------
NAVY_HEX = "071A3D"
ROYAL_HEX = "0B4DB8"
CHARCOAL_HEX = "1E293B"
MUTED_HEX = "64748B"
BORDER_HEX = "E2E8F0"
LIGHT_BG_HEX = "F8FAFC"
CARD_BG_HEX = "EEF2F8"

GREEN_BG_HEX = "E6F4EA"
GREEN_TXT_HEX = "137333"
RED_BG_HEX = "FCE8E6"
RED_TXT_HEX = "C5221F"
BLUE_BG_HEX = "EFF6FF"
BLUE_TXT_HEX = "1D4ED8"
GRAY_BG_HEX = "F1F5F9"
GRAY_TXT_HEX = "64748B"


def _get_status_style(status_text: str) -> Tuple[Optional[PatternFill], Optional[Font]]:
    """Return subtle, professional fill and font colors based on comparative status."""
    s = (status_text or '').strip().lower()
    if any(w in s for w in ('increased', 'improved', 'growth', 'surplus', 'positive', 'expansion')):
        return (
            PatternFill(start_color=GREEN_BG_HEX, end_color=GREEN_BG_HEX, fill_type="solid"),
            Font(name="Calibri", size=9, bold=True, color=GREEN_TXT_HEX),
        )
    elif any(w in s for w in ('decreased', 'declined', 'deficit', 'negative', 'contraction', 'loss')):
        return (
            PatternFill(start_color=RED_BG_HEX, end_color=RED_BG_HEX, fill_type="solid"),
            Font(name="Calibri", size=9, bold=True, color=RED_TXT_HEX),
        )
    elif any(w in s for w in ('newly available', 'active', 'verified', 'reported')):
        return (
            PatternFill(start_color=BLUE_BG_HEX, end_color=BLUE_BG_HEX, fill_type="solid"),
            Font(name="Calibri", size=9, bold=True, color=BLUE_TXT_HEX),
        )
    elif any(w in s for w in ('not available', 'unavailable', 'insufficient', 'pending', 'baseline')):
        return (
            PatternFill(start_color=GRAY_BG_HEX, end_color=GRAY_BG_HEX, fill_type="solid"),
            Font(name="Calibri", size=9, italic=True, color=GRAY_TXT_HEX),
        )
    return None, None


def _apply_box_styling(ws, start_row: int, start_col: int, end_row: int, end_col: int, border: Optional[Border] = None, fill: Optional[PatternFill] = None):
    """Apply borders and fills to all cells in a rectangular block (e.g. merged boxes)."""
    for r in range(start_row, end_row + 1):
        for c in range(start_col, end_col + 1):
            cell = ws.cell(row=r, column=c)
            if border:
                cell.border = border
            if fill:
                cell.fill = fill


def generate_xlsx_report(report: Report) -> bytes:
    """
    Generate professional, publication-grade XLSX workbook bytes from report content.
    Strictly presentation formatting: does not alter or recompute underlying data.
    """
    wb = openpyxl.Workbook()
    content = report.content_json or {}
    is_comparative = content.get('is_comparative', False)

    # Standard styling elements
    navy_fill = PatternFill(start_color=NAVY_HEX, end_color=NAVY_HEX, fill_type="solid")
    royal_fill = PatternFill(start_color=ROYAL_HEX, end_color=ROYAL_HEX, fill_type="solid")
    slate_fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
    light_fill = PatternFill(start_color=LIGHT_BG_HEX, end_color=LIGHT_BG_HEX, fill_type="solid")
    card_fill = PatternFill(start_color=CARD_BG_HEX, end_color=CARD_BG_HEX, fill_type="solid")
    green_hdr_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
    red_hdr_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color=BORDER_HEX),
        right=Side(style='thin', color=BORDER_HEX),
        top=Side(style='thin', color=BORDER_HEX),
        bottom=Side(style='thin', color=BORDER_HEX),
    )
    header_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='medium', color=ROYAL_HEX),
        bottom=Side(style='medium', color=ROYAL_HEX),
    )

    # =============================================================
    # Tab 1: Summary & KPIs
    # =============================================================
    ws_sum = wb.active
    ws_sum.title = "Summary & KPIs"
    ws_sum.views.sheetView[0].showGridLines = True

    # 1. Header Banner
    rep_title = content.get('title') or report.title
    ws_sum.merge_cells("A1:F1")
    t_cell = ws_sum["A1"]
    t_cell.value = rep_title
    t_cell.font = Font(name="Calibri", size=15, bold=True, color=NAVY_HEX)
    t_cell.alignment = Alignment(vertical="center")
    ws_sum.row_dimensions[1].height = 26

    ws_sum["A2"] = "CMPDI · Coal India Limited — AI Mining Intelligence Command Center"
    ws_sum["A2"].font = Font(name="Calibri", size=9.5, italic=True, color=MUTED_HEX)

    # 2. Metadata Grid (Rows 4-5)
    ws_sum["A4"] = "Report Type:"
    ws_sum["B4"] = report.report_type
    ws_sum["C4"] = "Organization:"
    ws_sum["D4"] = report.organization
    ws_sum["E4"] = "Period / Date:"
    ws_sum["F4"] = report.date_range

    ws_sum["A5"] = "Governance Status:"
    ws_sum["B5"] = report.status
    ws_sum["C5"] = "Revision Number:"
    ws_sum["D5"] = f"#{report.revision_count}"
    ws_sum["E5"] = "Generated At:"
    ws_sum["F5"] = content.get('generated_at') or report.created_at.strftime('%Y-%m-%d %H:%M')

    for r in range(4, 6):
        ws_sum.row_dimensions[r].height = 18
        for c in range(1, 7):
            cell = ws_sum.cell(row=r, column=c)
            cell.font = Font(name="Calibri", size=9, bold=(c % 2 != 0), color=NAVY_HEX if c % 2 != 0 else CHARCOAL_HEX)
            cell.border = thin_border
            if c % 2 != 0:
                cell.fill = light_fill
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    cur_row = 7

    # 3. Source Roles Box (When Comparative)
    source_roles = content.get('source_roles')
    if is_comparative and source_roles:
        org_r = source_roles.get('org_reference', {})
        curr_r = source_roles.get('current_upload', {})

        ws_sum.cell(row=cur_row, column=1, value="SOURCE IDENTIFICATION & ROLE SEPARATION").font = Font(name="Calibri", size=11, bold=True, color=ROYAL_HEX)
        cur_row += 1

        ws_sum.merge_cells(start_row=cur_row, start_column=1, end_row=cur_row, end_column=3)
        h_past = ws_sum.cell(row=cur_row, column=1, value="PAST / ORGANIZATION REFERENCE (BASELINE)")
        h_past.font = Font(name="Calibri", size=9.5, bold=True, color="FFFFFF")
        h_past.fill = slate_fill
        h_past.alignment = Alignment(horizontal="center", vertical="center")

        ws_sum.merge_cells(start_row=cur_row, start_column=4, end_row=cur_row, end_column=6)
        h_curr = ws_sum.cell(row=cur_row, column=4, value="CURRENT USER-UPLOADED DATA")
        h_curr.font = Font(name="Calibri", size=9.5, bold=True, color="FFFFFF")
        h_curr.fill = royal_fill
        h_curr.alignment = Alignment(horizontal="center", vertical="center")
        ws_sum.row_dimensions[cur_row].height = 20
        cur_row += 1

        ws_sum.merge_cells(start_row=cur_row, start_column=1, end_row=cur_row + 1, end_column=3)
        p_box = ws_sum.cell(row=cur_row, column=1)
        p_box.value = f"Source: {org_r.get('title', 'N/A')}\nPeriod: {org_r.get('period', 'N/A')}  |  Status: Protected Baseline"
        p_box.font = Font(name="Calibri", size=8.5)
        p_box.alignment = Alignment(wrap_text=True, vertical="center")
        _apply_box_styling(ws_sum, cur_row, 1, cur_row + 1, 3, border=thin_border, fill=light_fill)

        ws_sum.merge_cells(start_row=cur_row, start_column=4, end_row=cur_row + 1, end_column=6)
        c_box = ws_sum.cell(row=cur_row, column=4)
        c_box.value = f"Source: {curr_r.get('title', 'N/A')}\nPeriod: {curr_r.get('period', 'N/A')}  |  Status: Current Period Ingestion"
        c_box.font = Font(name="Calibri", size=8.5)
        c_box.alignment = Alignment(wrap_text=True, vertical="center")
        _apply_box_styling(ws_sum, cur_row, 4, cur_row + 1, 6, border=thin_border, fill=card_fill)

        cur_row += 3

    # 4. Executive Summary Box
    exec_summary = content.get('executive_summary', '')
    if exec_summary:
        ws_sum.cell(row=cur_row, column=1, value="EXECUTIVE SUMMARY").font = Font(name="Calibri", size=11, bold=True, color=ROYAL_HEX)
        cur_row += 1

        ws_sum.merge_cells(start_row=cur_row, start_column=1, end_row=cur_row + 2, end_column=6)
        s_cell = ws_sum.cell(row=cur_row, column=1, value=exec_summary)
        s_cell.font = Font(name="Calibri", size=9, italic=True)
        s_cell.alignment = Alignment(wrap_text=True, vertical="top")
        _apply_box_styling(ws_sum, cur_row, 1, cur_row + 2, 6, border=thin_border, fill=light_fill)
        cur_row += 4

    # 5. KPI Cards Grid (4 Cards side-by-side across cols A:F)
    kpis = content.get('kpis', [])
    if kpis:
        ws_sum.cell(row=cur_row, column=1, value="KEY PERFORMANCE METRICS").font = Font(name="Calibri", size=11, bold=True, color=ROYAL_HEX)
        cur_row += 1

        # Card col pairs: Card 1 (A), Card 2 (B:C), Card 3 (D), Card 4 (E:F)
        card_cols = [
            (1, 1),  # Col A
            (2, 3),  # Cols B:C
            (4, 4),  # Col D
            (5, 6),  # Cols E:F
        ]

        val_row = cur_row
        lbl_row = cur_row + 1
        src_row = cur_row + 2

        ws_sum.row_dimensions[val_row].height = 24
        ws_sum.row_dimensions[lbl_row].height = 18
        ws_sum.row_dimensions[src_row].height = 16

        for idx, k in enumerate(kpis[:4]):
            sc, ec = card_cols[idx]
            val_txt = str(k.get('value', '—'))
            lbl_txt = str(k.get('label', ''))
            chg_txt = str(k.get('change', ''))

            _apply_box_styling(ws_sum, val_row, sc, src_row, ec, border=thin_border, fill=card_fill)

            if sc != ec:
                ws_sum.merge_cells(start_row=val_row, start_column=sc, end_row=val_row, end_column=ec)
                ws_sum.merge_cells(start_row=lbl_row, start_column=sc, end_row=lbl_row, end_column=ec)
                ws_sum.merge_cells(start_row=src_row, start_column=sc, end_row=src_row, end_column=ec)

            vc = ws_sum.cell(row=val_row, column=sc, value=val_txt)
            vc.font = Font(name="Calibri", size=13, bold=True, color=ROYAL_HEX)
            vc.alignment = Alignment(horizontal="center", vertical="center")

            lc = ws_sum.cell(row=lbl_row, column=sc, value=lbl_txt)
            lc.font = Font(name="Calibri", size=8.5, bold=True, color=CHARCOAL_HEX)
            lc.alignment = Alignment(horizontal="center", vertical="center")

            sc_cell = ws_sum.cell(row=src_row, column=sc, value=chg_txt)
            sc_cell.font = Font(name="Calibri", size=8, italic=True, color=MUTED_HEX)
            sc_cell.alignment = Alignment(horizontal="center", vertical="center")

        cur_row += 4

    # 6. Key Performance Comparison Table (from Table 1)
    tables = content.get('tables', [])
    if tables:
        t1 = tables[0]
        t1_cols = t1.get('columns', [])
        t1_rows = t1.get('rows', [])

        if t1_cols and t1_rows:
            ws_sum.cell(row=cur_row, column=1, value="KEY PERFORMANCE COMPARISON").font = Font(name="Calibri", size=11, bold=True, color=ROYAL_HEX)
            cur_row += 1

            ws_sum.row_dimensions[cur_row].height = 22
            for c_idx, col_name in enumerate(t1_cols, start=1):
                c_cell = ws_sum.cell(row=cur_row, column=c_idx, value=col_name)
                c_cell.font = Font(name="Calibri", size=9, bold=True, color="FFFFFF")
                c_cell.fill = navy_fill
                c_cell.alignment = Alignment(horizontal="center", vertical="center")
                c_cell.border = thin_border
            cur_row += 1

            for r_idx, row_vals in enumerate(t1_rows):
                ws_sum.row_dimensions[cur_row].height = 19
                is_even = r_idx % 2 == 0
                for c_idx, val in enumerate(row_vals, start=1):
                    cell = ws_sum.cell(row=cur_row, column=c_idx, value=val)
                    cell.font = Font(name="Calibri", size=8.5)
                    cell.border = thin_border

                    # Check alignment
                    col_header = t1_cols[c_idx - 1].lower() if c_idx - 1 < len(t1_cols) else ''
                    if 'metric' in col_header or c_idx == 1:
                        cell.font = Font(name="Calibri", size=8.5, bold=True, color=CHARCOAL_HEX)
                        cell.alignment = Alignment(horizontal="left", vertical="center")
                    elif 'status' in col_header:
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                        fill, font = _get_status_style(str(val))
                        if fill and font:
                            cell.fill = fill
                            cell.font = font
                    else:
                        cell.alignment = Alignment(horizontal="right", vertical="center")

                    if not cell.fill.fill_type and is_even:
                        cell.fill = light_fill
                cur_row += 1

            cur_row += 1

    # 7. Top Improvements & Top Declines (Parallel Cards)
    top_imp = content.get('top_improvements', '')
    top_dec = content.get('top_declines', '')
    if is_comparative and (top_imp or top_dec):
        ws_sum.cell(row=cur_row, column=1, value="EXECUTIVE CHANGE HIGHLIGHTS").font = Font(name="Calibri", size=11, bold=True, color=ROYAL_HEX)
        cur_row += 1

        ws_sum.merge_cells(start_row=cur_row, start_column=1, end_row=cur_row, end_column=3)
        ih = ws_sum.cell(row=cur_row, column=1, value="TOP PERFORMANCE IMPROVEMENTS")
        ih.font = Font(name="Calibri", size=9, bold=True, color=GREEN_TXT_HEX)
        ih.fill = green_hdr_fill
        ih.alignment = Alignment(horizontal="center", vertical="center")

        ws_sum.merge_cells(start_row=cur_row, start_column=4, end_row=cur_row, end_column=6)
        dh = ws_sum.cell(row=cur_row, column=4, value="TOP PERFORMANCE DECLINES")
        dh.font = Font(name="Calibri", size=9, bold=True, color=RED_TXT_HEX)
        dh.fill = red_hdr_fill
        dh.alignment = Alignment(horizontal="center", vertical="center")
        ws_sum.row_dimensions[cur_row].height = 20
        cur_row += 1

        ws_sum.merge_cells(start_row=cur_row, start_column=1, end_row=cur_row + 2, end_column=3)
        ic = ws_sum.cell(row=cur_row, column=1, value=top_imp.strip())
        ic.font = Font(name="Calibri", size=8.5)
        ic.alignment = Alignment(wrap_text=True, vertical="top")
        _apply_box_styling(ws_sum, cur_row, 1, cur_row + 2, 3, border=thin_border, fill=PatternFill(start_color="F0FDF4", end_color="F0FDF4", fill_type="solid"))

        ws_sum.merge_cells(start_row=cur_row, start_column=4, end_row=cur_row + 2, end_column=6)
        dc = ws_sum.cell(row=cur_row, column=4, value=top_dec.strip())
        dc.font = Font(name="Calibri", size=8.5)
        dc.alignment = Alignment(wrap_text=True, vertical="top")
        _apply_box_styling(ws_sum, cur_row, 4, cur_row + 2, 6, border=thin_border, fill=PatternFill(start_color="FEF2F2", end_color="FEF2F2", fill_type="solid"))

        cur_row += 4

    # 8. Governance / Sign-off Block
    ws_sum.cell(row=cur_row, column=1, value="GOVERNANCE & APPROVAL SIGN-OFF").font = Font(name="Calibri", size=11, bold=True, color=ROYAL_HEX)
    cur_row += 1

    ws_sum.cell(row=cur_row, column=1, value="Verification Status")
    ws_sum.cell(row=cur_row, column=2, value=report.status)
    ws_sum.cell(row=cur_row, column=3, value="Verified By")
    ws_sum.cell(row=cur_row, column=4, value=report.verified_by.username if report.verified_by else "Pending")
    ws_sum.cell(row=cur_row, column=5, value="Approved By")
    ws_sum.cell(row=cur_row, column=6, value=report.approved_by.username if report.approved_by else "Pending")

    ws_sum.cell(row=cur_row + 1, column=1, value="Revision Number")
    ws_sum.cell(row=cur_row + 1, column=2, value=f"#{report.revision_count}")
    ws_sum.cell(row=cur_row + 1, column=3, value="Verified Date")
    ws_sum.cell(row=cur_row + 1, column=4, value=report.verified_at.strftime('%Y-%m-%d %H:%M') if report.verified_at else "—")
    ws_sum.cell(row=cur_row + 1, column=5, value="Approved Date")
    ws_sum.cell(row=cur_row + 1, column=6, value=report.approved_at.strftime('%Y-%m-%d %H:%M') if report.approved_at else "—")

    for r in range(cur_row, cur_row + 2):
        ws_sum.row_dimensions[r].height = 18
        for c in range(1, 7):
            cell = ws_sum.cell(row=r, column=c)
            cell.font = Font(name="Calibri", size=8.5, bold=(c % 2 != 0))
            cell.border = thin_border
            if c % 2 != 0:
                cell.fill = light_fill
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    # =============================================================
    # Tab 2: Report Data
    # =============================================================
    ws_tbl = wb.create_sheet(title="Report Data")
    ws_tbl.views.sheetView[0].showGridLines = True
    ws_tbl.freeze_panes = "A4"

    # Title
    ws_tbl.cell(row=1, column=1, value="DETAILED OPERATIONAL & COMPARATIVE REPORT DATA").font = Font(name="Calibri", size=14, bold=True, color=NAVY_HEX)
    ws_tbl.cell(row=2, column=1, value=f"Comprehensive records, subsidiary breakdowns, and schema coverage for {report.organization} ({report.date_range}).").font = Font(name="Calibri", size=9, italic=True, color=MUTED_HEX)

    r_row = 4

    # Render structured tables
    for t_idx, t in enumerate(tables, 1):
        tbl_title = t.get('title', f'Data Table {t_idx}')
        t_cols = t.get('columns', [])
        t_rows = t.get('rows', [])

        ws_tbl.cell(row=r_row, column=1, value=f"{t_idx}. {tbl_title}").font = Font(name="Calibri", size=11, bold=True, color=ROYAL_HEX)
        r_row += 1

        if t.get('description'):
            ws_tbl.cell(row=r_row, column=1, value=t.get('description')).font = Font(name="Calibri", size=8.5, italic=True, color=MUTED_HEX)
            r_row += 1

        if t_cols:
            ws_tbl.row_dimensions[r_row].height = 22
            for c_idx, col_name in enumerate(t_cols, start=1):
                cell = ws_tbl.cell(row=r_row, column=c_idx, value=col_name)
                cell.font = Font(name="Calibri", size=9, bold=True, color="FFFFFF")
                cell.fill = navy_fill
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = thin_border
            r_row += 1

            for r_idx, row_vals in enumerate(t_rows[:100]):
                ws_tbl.row_dimensions[r_row].height = 19
                is_even = r_idx % 2 == 0
                for c_idx, val in enumerate(row_vals, start=1):
                    cell = ws_tbl.cell(row=r_row, column=c_idx, value=val)
                    cell.font = Font(name="Calibri", size=8.5)
                    cell.border = thin_border

                    col_hdr = t_cols[c_idx - 1].lower() if c_idx - 1 < len(t_cols) else ''
                    if c_idx == 1:
                        cell.font = Font(name="Calibri", size=8.5, bold=True, color=CHARCOAL_HEX)
                        cell.alignment = Alignment(horizontal="left", vertical="center")
                    elif 'status' in col_hdr:
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                        fill, font = _get_status_style(str(val))
                        if fill and font:
                            cell.fill = fill
                            cell.font = font
                    elif any(w in col_hdr for w in ('production', 'target', 'dispatch', 'variance', '%', 'value', 'change')):
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                    else:
                        cell.alignment = Alignment(horizontal="left", vertical="center")

                    if not cell.fill.fill_type and is_even:
                        cell.fill = light_fill
                r_row += 1

            if t.get('source'):
                ws_tbl.cell(row=r_row, column=1, value=f"Source Reference: {t.get('source')}").font = Font(name="Calibri", size=8, italic=True, color=MUTED_HEX)
                r_row += 1

            r_row += 2

    # Narrative & Discovery Sections on Sheet 2
    newly_avail = content.get('newly_available')
    if newly_avail and is_comparative:
        ws_tbl.cell(row=r_row, column=1, value="NEWLY AVAILABLE INFORMATION IN CURRENT REPORT").font = Font(name="Calibri", size=11, bold=True, color=GREEN_TXT_HEX)
        r_row += 1
        for line in newly_avail.split('\n'):
            if line.strip():
                c_lbl = ws_tbl.cell(row=r_row, column=1, value=line.strip())
                c_lbl.font = Font(name="Calibri", size=8.5)
                r_row += 1
        r_row += 1

    missing_info = content.get('missing_information')
    if missing_info and is_comparative:
        ws_tbl.cell(row=r_row, column=1, value="MISSING / UNAVAILABLE INFORMATION DISCLOSURE").font = Font(name="Calibri", size=11, bold=True, color=MUTED_HEX)
        r_row += 1
        for line in missing_info.split('\n'):
            if line.strip():
                c_lbl = ws_tbl.cell(row=r_row, column=1, value=line.strip())
                c_lbl.font = Font(name="Calibri", size=8.5, italic=True, color=MUTED_HEX)
                r_row += 1
        r_row += 1

    ai_insights = content.get('ai_insights', [])
    if ai_insights:
        ws_tbl.cell(row=r_row, column=1, value="AI-GENERATED OPERATIONAL INSIGHTS (STRICTLY GROUNDED)").font = Font(name="Calibri", size=11, bold=True, color=ROYAL_HEX)
        r_row += 1
        for i, ins in enumerate(ai_insights, 1):
            c_ins = ws_tbl.cell(row=r_row, column=1, value=f"{i}. {ins}")
            c_ins.font = Font(name="Calibri", size=8.5)
            r_row += 1
        r_row += 1

    # =============================================================
    # Tab 3: Provenance & Audit
    # =============================================================
    ws_prov = wb.create_sheet(title="Provenance & Audit")
    ws_prov.views.sheetView[0].showGridLines = True
    ws_prov.freeze_panes = "A4"

    ws_prov.cell(row=1, column=1, value="DATA SOURCE TRACEABILITY & AUDIT PROVENANCE LEDGER").font = Font(name="Calibri", size=13, bold=True, color=NAVY_HEX)
    ws_prov.cell(row=2, column=1, value="Complete verified source references for all figures and comparative metrics.").font = Font(name="Calibri", size=9, italic=True, color=MUTED_HEX)

    prov_headers = ["#", "Source Type", "Document / Dataset Title", "Sheet / Page", "Row / Ref", "Field / Metric", "Extracted Value", "Method", "Confidence"]
    ws_prov.row_dimensions[3].height = 22

    for c_idx, h in enumerate(prov_headers, start=1):
        cell = ws_prov.cell(row=3, column=c_idx, value=h)
        cell.font = Font(name="Calibri", size=9, bold=True, color="FFFFFF")
        cell.fill = royal_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    prov_list = report.provenance_json or []
    for r_idx, p in enumerate(prov_list[:150], start=4):
        ws_prov.row_dimensions[r_idx].height = 18
        is_even = r_idx % 2 == 0

        p_type = p.get('source_type', 'dataset').upper()
        doc_name = p.get('name') or p.get('document_title') or 'Verified Source'
        pg_sheet = f"p. {p.get('page_number')}" if p.get('page_number') else (p.get('sheet_name') or 'Main')
        row_ref = p.get('source_ref') or f"Row {p.get('row_index', '-')}"
        field_name = p.get('field', 'data')
        val_str = str(p.get('value', '—'))[:60]
        method = p.get('extractor_type', 'xlsx')
        conf = f"{int((p.get('confidence') or 1.0) * 100)}%"

        row_data = [r_idx - 3, p_type, doc_name, pg_sheet, row_ref, field_name, val_str, method, conf]

        for c_idx, val in enumerate(row_data, start=1):
            cell = ws_prov.cell(row=r_idx, column=c_idx, value=val)
            cell.font = Font(name="Calibri", size=8.5)
            cell.border = thin_border
            if c_idx in (1, 2, 8, 9):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

            if is_even:
                cell.fill = light_fill

    last_prov_row = max(len(prov_list) + 3, 4)
    ws_prov.auto_filter.ref = f"A3:I{last_prov_row}"

    # =============================================================
    # Column Auto-Width Calculation (Robust & Balanced)
    # =============================================================
    for sheet in wb.worksheets:
        merged_cell_coords = set()
        for rng in sheet.merged_cells.ranges:
            for cell_coord in rng.cells:
                merged_cell_coords.add(cell_coord)

        for col in sheet.columns:
            col_letter = get_column_letter(col[0].column)
            max_len = 0
            for cell in col:
                # Ignore merged cells and very long text paragraphs
                if (cell.row, cell.column) in merged_cell_coords:
                    continue
                val = str(cell.value or '')
                if '\n' in val:
                    val = max(val.split('\n'), key=len)
                if len(val) > 40:
                    continue
                if len(val) > max_len:
                    max_len = len(val)

            # Assign sensible column widths
            sheet.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 35)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
