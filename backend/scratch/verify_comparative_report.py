"""
scratch/verify_comparative_report.py — Targeted Verification Script for Advanced Comparative Intelligence Report
"""

import os
import django

import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from apps.reports.models import Report, ReportType, ReportStatus
from apps.reports.services.engine import ReportEngine
from apps.reports.services.exporters.pdf_exporter import generate_pdf_report
from apps.datasets.models import StructuredDataset
from apps.documents.models import Document

User = get_user_model()
admin = User.objects.first()

print("=================================================================")
print("TARGETED VERIFICATION: ADVANCED COMPARATIVE INTELLIGENCE REPORT")
print("=================================================================")

# 1. Verification with FY2023-24 Reference (Dataset 10, Doc 15) vs FY2024-25 Current (Dataset 11, Doc 16)
print("\n--- Test Scenario 1: Baseline FY23-24 vs Current FY24-25 ---")
ds_past = StructuredDataset.objects.get(id=10)
ds_curr = StructuredDataset.objects.get(id=11)
doc_past = Document.objects.get(id=15)
doc_curr = Document.objects.get(id=16)

rep1 = ReportEngine.create_and_generate(
    user=admin,
    report_type='Comparative Intelligence Report',
    organization='CMPDI (HQ)',
    date_range='FY 2023-24 vs FY 2024-25',
    source_dataset_ids=[ds_past.id, ds_curr.id],
    source_document_ids=[doc_past.id, doc_curr.id],
)

content1 = rep1.content_json
tables1 = content1.get('tables', [])
chart1 = content1.get('chart_data', {})

print(f"Report ID: {rep1.id}")
print(f"Report Title: {rep1.title}")
print(f"Status: {rep1.status}")
print(f"Date Range: {rep1.date_range}")
print(f"Is Comparative: {content1.get('is_comparative')}")

# Verify Executive Summary
print(f"\nExecutive Summary:\n{content1.get('executive_summary')}")

# Verify Table 1: Direct Metric Comparison
print("\nTable 1: Direct Key Metric Comparison:")
t1_rows = tables1[0]['rows']
for r in t1_rows:
    print(f"  {r[0]:<22} | Past: {r[1]:<12} | Current: {r[2]:<12} | Diff: {r[3]:<12} | % Change: {r[4]:<10} | Status: {r[5]}")

# Assertions for Table 1
prod_row = [r for r in t1_rows if 'Production' in r[0] and 'Target' not in r[0]][0]
assert '1,000' in prod_row[1], f"Expected 1,000 in past prod, got {prod_row[1]}"
assert '1,200' in prod_row[2], f"Expected 1,200 in curr prod, got {prod_row[2]}"
assert '+200' in prod_row[3], f"Expected +200 in diff, got {prod_row[3]}"
assert '20.00%' in prod_row[4], f"Expected 20% in pct, got {prod_row[4]}"
assert prod_row[5] == 'Increased', f"Expected Increased, got {prod_row[5]}"

# Verify Table 2: Subsidiary Comparison
print("\nTable 2: Subsidiary Comparison:")
t2_rows = tables1[1]['rows']
for r in t2_rows:
    print(f"  {r[0]:<10} | Past: {r[1]:<12} | Current: {r[2]:<12} | Diff: {r[3]:<12} | % Change: {r[4]:<10} | Status: {r[5]}")

assert len(t2_rows) >= 4, f"Expected at least 4 subsidiaries, got {len(t2_rows)}"

# Verify Chart Data
print(f"\nChart Data Present: {chart1.get('has_chart')}")
print(f"Grouped Metric Categories: {chart1.get('grouped_metrics', {}).get('categories')}")
print(f"Grouped Past Series: {chart1.get('grouped_metrics', {}).get('past_series')}")
print(f"Grouped Curr Series: {chart1.get('grouped_metrics', {}).get('curr_series')}")
assert chart1.get('has_chart') is True, "Chart data must be present"

# Verify PDF Generation
pdf_bytes1 = generate_pdf_report(rep1)
print(f"\nPDF Generation: SUCCESS ({len(pdf_bytes1)} bytes)")
assert len(pdf_bytes1) > 5000, "PDF size should be substantial"

# 2. Verification with Dataset for Ask AI Test for New Info & Financials
print("\n--- Test Scenario 2: Baseline FY23-24 vs Current with Financials ---")
ds_fin = StructuredDataset.objects.filter(name__icontains='Demo_Document_for_Ask_AI_Test', source_document__is_archived=False).order_by('-id').first()
if not ds_fin:
    ds_fin = StructuredDataset.objects.get(id=22)
doc_fin = ds_fin.source_document

rep2 = ReportEngine.create_and_generate(
    user=admin,
    report_type='Comparative Intelligence Report',
    organization='CMPDI (HQ)',
    date_range='FY 2023-24 vs FY 2025-26',
    source_dataset_ids=[ds_past.id, ds_fin.id],
    source_document_ids=[doc_past.id, doc_fin.id],
)

content2 = rep2.content_json
tables2 = content2.get('tables', [])
print(f"Report ID: {rep2.id}")
print(f"Newly Available Information:\n{content2.get('newly_available')}")
print(f"Missing Information:\n{content2.get('missing_information')}")
print(f"Tables Count: {len(tables2)}")

# Check Financials Table
fin_table = [t for t in tables2 if 'Financial' in t['title']]
assert len(fin_table) == 1, "Financial table should be rendered when financial metrics are present"
print("\nFinancial & Value Metrics Table:")
for r in fin_table[0]['rows']:
    print(f"  {r[0]:<28} | Past: {r[1]:<14} | Current: {r[2]:<16} | Status: {r[5]}")

# Check Information Coverage Table
cov_table = [t for t in tables2 if 'Coverage' in t['title']]
assert len(cov_table) == 1, "Coverage matrix table should be rendered"
print("\nInformation Coverage Matrix Table:")
for r in cov_table[0]['rows']:
    print(f"  {r[0]:<35} | {r[1]:<32} | {r[4]}")

# Check AI Insights
print("\nAI-Generated Insights:")
for ins in content2.get('ai_insights', []):
    print(f"  - {ins}")

pdf_bytes2 = generate_pdf_report(rep2)
print(f"\nPDF Generation for Scenario 2: SUCCESS ({len(pdf_bytes2)} bytes)")
assert len(pdf_bytes2) > 5000, "PDF size should be substantial"

print("\n=================================================================")
print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY! ZERO FAILURES.")
print("=================================================================")
