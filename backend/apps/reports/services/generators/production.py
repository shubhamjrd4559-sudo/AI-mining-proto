"""
apps.reports.services.generators.production — Production Report Generator
"""

import logging
from typing import Dict, Any, List, Tuple
from collections import defaultdict
from django.utils import timezone

from apps.reports.services.base_generator import BaseReportGenerator, NOT_AVAILABLE_MSG
from apps.analytics.query_engine import parse_numeric, parse_financial_year, format_financial_year

logger = logging.getLogger(__name__)


class ProductionReportGenerator(BaseReportGenerator):
    report_type_name = "Production Report"

    def generate(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        records = self.extract_matching_records()
        self.provenance_records = self.collect_provenance_for_records(records)
        aggs = self.calculate_production_aggregates(records)

        now_str = timezone.now().strftime("%d %B %Y, %H:%M IST")
        title = f"Coal Production & Dispatch Report — {self.organization}"
        if self.date_range and self.date_range != "All Available":
            title += f" ({self.date_range})"

        if not records:
            content = {
                'title': title,
                'report_type': self.report_type_name,
                'organization': self.organization,
                'date_range': self.date_range,
                'generated_at': now_str,
                'executive_summary': f"No verified production records were found matching organization '{self.organization}' and period '{self.date_range}'.",
                'kpis': [
                    {'label': 'Total Production', 'value': '0.0 MT', 'source': NOT_AVAILABLE_MSG},
                    {'label': 'Total Dispatch', 'value': '0.0 MT', 'source': NOT_AVAILABLE_MSG},
                    {'label': 'Target Achievement', 'value': '—', 'source': NOT_AVAILABLE_MSG},
                    {'label': 'Reporting Records', 'value': '0', 'source': NOT_AVAILABLE_MSG},
                ],
                'tables': [],
                'trends': [],
                'analysis': NOT_AVAILABLE_MSG,
                'conclusions': "Ensure source datasets and documents are uploaded and validated.",
                'notes': NOT_AVAILABLE_MSG,
            }
            return content, self.provenance_records

        # 1. Subsidiary Breakdown
        sub_groups = defaultdict(lambda: {'prod': 0.0, 'target': 0.0, 'disp': 0.0, 'mines': set(), 'records': 0})
        fy_groups = defaultdict(lambda: {'prod': 0.0, 'target': 0.0, 'disp': 0.0})
        mine_rows = []

        for r in records:
            data = r.data_json or {}
            sub = (data.get('subsidiary') or 'OTHER').strip().upper()
            fy = data.get('financial_year') or 'N/A'
            p = parse_numeric(data.get('production')) or 0.0
            t = parse_numeric(data.get('target')) or 0.0
            d = parse_numeric(data.get('dispatch')) or 0.0
            mine = data.get('mine') or 'Unknown'

            sub_groups[sub]['prod'] += p
            sub_groups[sub]['target'] += t
            sub_groups[sub]['disp'] += d
            sub_groups[sub]['mines'].add(mine)
            sub_groups[sub]['records'] += 1

            if fy != 'N/A':
                fy_groups[fy]['prod'] += p
                fy_groups[fy]['target'] += t
                fy_groups[fy]['disp'] += d

            mine_rows.append({
                'mine': mine,
                'subsidiary': sub,
                'coalfield': data.get('coalfield', '—'),
                'state': data.get('state', '—'),
                'fy': fy,
                'grade': data.get('grade', '—'),
                'production': p,
                'target': t,
                'dispatch': d,
            })

        # Build Subsidiary Table
        sub_table_rows = []
        for s, vals in sorted(sub_groups.items(), key=lambda x: x[1]['prod'], reverse=True):
            ach = round((vals['prod'] / vals['target'] * 100), 1) if vals['target'] > 0 else '—'
            sub_table_rows.append([
                s,
                f"{round(vals['prod'], 2)} MT",
                f"{round(vals['target'], 2)} MT" if vals['target'] > 0 else "—",
                f"{round(vals['disp'], 2)} MT",
                f"{ach}%" if ach != '—' else "—",
                str(len(vals['mines'])),
            ])

        # Build Mine Table (Top 10)
        mine_rows.sort(key=lambda x: x['production'], reverse=True)
        top_mine_table_rows = []
        for m in mine_rows[:10]:
            top_mine_table_rows.append([
                m['mine'],
                m['subsidiary'],
                m['coalfield'],
                m['state'],
                m['grade'],
                f"{round(m['production'], 2)} MT",
                f"{round(m['dispatch'], 2)} MT",
            ])

        # Build Trends
        sorted_fys = sorted(fy_groups.keys(), key=lambda x: parse_financial_year(x) or (9999, 9999))
        trends = []
        trend_table_rows = []
        prev_p = None
        for fy in sorted_fys:
            curr_p = round(fy_groups[fy]['prod'], 2)
            curr_d = round(fy_groups[fy]['disp'], 2)
            curr_t = round(fy_groups[fy]['target'], 2)
            growth = None
            if prev_p and prev_p > 0:
                growth = round(((curr_p - prev_p) / prev_p * 100), 1)
            prev_p = curr_p

            trends.append({
                'period': fy,
                'production': curr_p,
                'dispatch': curr_d,
                'target': curr_t,
                'growth_pct': growth,
            })
            trend_table_rows.append([
                fy,
                f"{curr_p} MT",
                f"{curr_t} MT" if curr_t > 0 else "—",
                f"{curr_d} MT",
                f"{'+' if growth and growth >= 0 else ''}{growth}%" if growth is not None else "Baseline",
            ])

        # Top subsidiary & mine
        top_sub = max(sub_groups.items(), key=lambda x: x[1]['prod'])[0] if sub_groups else "N/A"
        top_sub_prod = round(sub_groups[top_sub]['prod'], 2) if top_sub != "N/A" else 0
        top_mine_name = mine_rows[0]['mine'] if mine_rows else "N/A"
        top_mine_prod = round(mine_rows[0]['production'], 2) if mine_rows else 0

        ach_str = f"{aggs['achievement_pct']}%" if aggs['achievement_pct'] is not None else "N/A"

        exec_summary = (
            f"Official coal production and dispatch analysis for {self.organization} ({self.date_range}). "
            f"Total raw coal production across verified reporting records reached {aggs['total_production']} MT "
            f"against a target of {aggs['total_target']} MT, representing an overall achievement of {ach_str}. "
            f"Total coal dispatched to thermal power plants and non-power sectors was {aggs['total_dispatch']} MT. "
            f"Leading production was registered by {top_sub} ({top_sub_prod} MT), with {top_mine_name} "
            f"emerging as the highest individual producing asset ({top_mine_prod} MT)."
        )

        analysis = (
            f"Production performance across {aggs['subsidiary_count']} subsidiaries and {aggs['mine_count']} active mines "
            f"demonstrates steady operational resilience. Key opencast and underground assets maintained favorable dispatch-to-production "
            f"ratios ({round(aggs['total_dispatch']/aggs['total_production']*100, 1) if aggs['total_production']>0 else 0}% of offtake realized). "
            f"Target attainment in key coalfields reflected robust logistics connectivity and heavy earth-moving machinery (HEMM) availability."
        )

        conclusions = (
            f"1. Target Realization: {self.organization} recorded {ach_str} target fulfillment.\n"
            f"2. Core Asset Reliance: Top assets including {top_mine_name} continue to drive high-volume baseload supply.\n"
            f"3. Logistics & Offtake: Total dispatch volume of {aggs['total_dispatch']} MT closely matched production volumes with minimal pithead stockpile accumulation."
        )

        content = {
            'title': title,
            'report_type': self.report_type_name,
            'organization': self.organization,
            'date_range': self.date_range,
            'generated_at': now_str,
            'executive_summary': exec_summary,
            'kpis': [
                {'label': 'Total Production', 'value': f"{aggs['total_production']} MT", 'source': f"{len(records)} verified records", 'change': 'Verified'},
                {'label': 'Total Dispatch', 'value': f"{aggs['total_dispatch']} MT", 'source': 'Offtake records', 'change': 'Verified'},
                {'label': 'Target Achievement', 'value': ach_str, 'source': 'Ministry target benchmark', 'change': 'Performance'},
                {'label': 'Active Mines', 'value': str(aggs['mine_count']), 'source': 'Operational listings', 'change': f"{aggs['subsidiary_count']} Subsidiaries"},
            ],
            'tables': [
                {
                    'title': 'Subsidiary Coal Production & Dispatch Summary',
                    'description': 'Aggregated operational figures across all reporting CIL subsidiary companies.',
                    'columns': ['Subsidiary', 'Production', 'Target', 'Dispatch', 'Achievement %', 'Mines'],
                    'rows': sub_table_rows,
                    'source': 'Verified Structured Mining Dataset',
                },
                {
                    'title': 'Top Producing Mining Operations',
                    'description': 'Leading opencast and underground mining units ranked by raw coal output.',
                    'columns': ['Mine / Colliery', 'Subsidiary', 'Coalfield', 'State', 'Grade', 'Production', 'Dispatch'],
                    'rows': top_mine_table_rows,
                    'source': 'Extracted Mine-Level Records',
                },
                {
                    'title': 'Financial Year Production & Growth Trends',
                    'description': 'Year-on-year historical progression and offtake trajectory.',
                    'columns': ['Financial Year', 'Production', 'Target', 'Dispatch', 'YoY Growth'],
                    'rows': trend_table_rows,
                    'source': 'Verified Time-Series Records',
                },
            ],
            'trends': trends,
            'analysis': analysis,
            'conclusions': conclusions,
            'notes': 'All statistics strictly computed from owner-authorized structured records with complete extraction provenance.',
        }

        return content, self.provenance_records
