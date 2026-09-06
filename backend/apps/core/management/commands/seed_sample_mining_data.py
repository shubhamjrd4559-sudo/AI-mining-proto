"""
Management command: seed_sample_mining_data

Seeds a realistic CIL / CMPDI mining dataset into StructuredDataset, StructuredRecord,
ExtractionProvenance, and ValidationResult for end-to-end verification of Phase 6.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from apps.documents.models import Document, DocumentStatus
from apps.datasets.models import StructuredDataset, StructuredRecord
from apps.pipeline.models import ExtractionProvenance, ValidationResult
from apps.maintainer.models import MaintainerSuggestion, SuggestionStatus, SuggestionSource, SuggestionIssueType


class Command(BaseCommand):
    help = 'Seed realistic sample mining datasets and records for Phase 6 verification.'

    def handle(self, *args, **options):
        User = get_user_model()
        user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not user:
            user = User.objects.create_superuser('admin', 'admin@cmpdi.local', 'admin123')
            self.stdout.write(self.style.SUCCESS(f"Created dev admin user '{user.username}'"))

        # Create source document
        doc, _ = Document.objects.get_or_create(
            title='CIL_Subsidiaries_Coal_Production_and_Target_2021_2025.xlsx',
            uploaded_by=user,
            defaults={
                'original_filename': 'CIL_Subsidiaries_Coal_Production_and_Target_2021_2025.xlsx',
                'file_extension': '.xlsx',
                'status': DocumentStatus.COMPLETED,
                'mime_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            }
        )

        # Clear existing dataset with this name if re-running
        StructuredDataset.objects.filter(name='CIL National Coal Production & Dispatch (FY21-FY25)', source_document=doc).delete()

        schema = {
            'columns': [
                'subsidiary', 'mine', 'coalfield', 'state', 'financial_year',
                'coal_type', 'grade', 'production', 'target', 'dispatch'
            ],
            'column_map': {
                'subsidiary': {'concept': 'subsidiary', 'confidence': 1.0},
                'mine': {'concept': 'mine', 'confidence': 1.0},
                'coalfield': {'concept': 'coalfield', 'confidence': 1.0},
                'state': {'concept': 'state', 'confidence': 1.0},
                'financial_year': {'concept': 'financial_year', 'confidence': 1.0},
                'coal_type': {'concept': 'coal_type', 'confidence': 1.0},
                'grade': {'concept': 'grade', 'confidence': 1.0},
                'production': {'concept': 'production', 'confidence': 1.0},
                'target': {'concept': 'target', 'confidence': 1.0},
                'dispatch': {'concept': 'dispatch', 'confidence': 1.0},
            },
            'extractor_type': 'xlsx',
        }

        dataset = StructuredDataset.objects.create(
            name='CIL National Coal Production & Dispatch (FY21-FY25)',
            description='Official CIL subsidiary performance, dispatch and geological grade breakdown across major coalfields.',
            source_document=doc,
            schema_json=schema,
        )

        sample_rows = [
            # FY 2021-22
            {'subsidiary': 'SECL', 'mine': 'Gevra OC', 'coalfield': 'Korba', 'state': 'Chhattisgarh', 'financial_year': '2021-22', 'coal_type': 'Non-Coking', 'grade': 'G10', 'production': 45.2, 'target': 44.0, 'dispatch': 44.8},
            {'subsidiary': 'SECL', 'mine': 'Kusmunda OC', 'coalfield': 'Korba', 'state': 'Chhattisgarh', 'financial_year': '2021-22', 'coal_type': 'Non-Coking', 'grade': 'G11', 'production': 38.6, 'target': 37.5, 'dispatch': 38.0},
            {'subsidiary': 'MCL', 'mine': 'Kulda OC', 'coalfield': 'Ib Valley', 'state': 'Odisha', 'financial_year': '2021-22', 'coal_type': 'Non-Coking', 'grade': 'G12', 'production': 32.1, 'target': 31.0, 'dispatch': 31.5},
            {'subsidiary': 'NCL', 'mine': 'Jayant OC', 'coalfield': 'Singrauli', 'state': 'Madhya Pradesh', 'financial_year': '2021-22', 'coal_type': 'Non-Coking', 'grade': 'G8', 'production': 24.5, 'target': 25.0, 'dispatch': 24.0},
            {'subsidiary': 'BCCL', 'mine': 'Moonidih UG', 'coalfield': 'Jharia', 'state': 'Jharkhand', 'financial_year': '2021-22', 'coal_type': 'Coking', 'grade': 'Steel-I', 'production': 18.2, 'target': 20.0, 'dispatch': 17.9},
            {'subsidiary': 'ECL', 'mine': 'Rajmahal OC', 'coalfield': 'Rajmahal', 'state': 'Jharkhand', 'financial_year': '2021-22', 'coal_type': 'Non-Coking', 'grade': 'G8', 'production': 15.4, 'target': 16.0, 'dispatch': 15.1},

            # FY 2022-23
            {'subsidiary': 'SECL', 'mine': 'Gevra OC', 'coalfield': 'Korba', 'state': 'Chhattisgarh', 'financial_year': '2022-23', 'coal_type': 'Non-Coking', 'grade': 'G10', 'production': 48.5, 'target': 47.0, 'dispatch': 48.0},
            {'subsidiary': 'SECL', 'mine': 'Kusmunda OC', 'coalfield': 'Korba', 'state': 'Chhattisgarh', 'financial_year': '2022-23', 'coal_type': 'Non-Coking', 'grade': 'G11', 'production': 41.2, 'target': 40.0, 'dispatch': 40.8},
            {'subsidiary': 'MCL', 'mine': 'Kulda OC', 'coalfield': 'Ib Valley', 'state': 'Odisha', 'financial_year': '2022-23', 'coal_type': 'Non-Coking', 'grade': 'G12', 'production': 35.8, 'target': 34.5, 'dispatch': 35.2},
            {'subsidiary': 'NCL', 'mine': 'Jayant OC', 'coalfield': 'Singrauli', 'state': 'Madhya Pradesh', 'financial_year': '2022-23', 'coal_type': 'Non-Coking', 'grade': 'G8', 'production': 26.8, 'target': 26.0, 'dispatch': 26.5},
            {'subsidiary': 'BCCL', 'mine': 'Moonidih UG', 'coalfield': 'Jharia', 'state': 'Jharkhand', 'financial_year': '2022-23', 'coal_type': 'Coking', 'grade': 'Steel-I', 'production': 19.8, 'target': 20.5, 'dispatch': 19.5},
            {'subsidiary': 'ECL', 'mine': 'Rajmahal OC', 'coalfield': 'Rajmahal', 'state': 'Jharkhand', 'financial_year': '2022-23', 'coal_type': 'Non-Coking', 'grade': 'G8', 'production': 16.7, 'target': 17.0, 'dispatch': 16.5},

            # FY 2023-24
            {'subsidiary': 'SECL', 'mine': 'Gevra OC', 'coalfield': 'Korba', 'state': 'Chhattisgarh', 'financial_year': '2023-24', 'coal_type': 'Non-Coking', 'grade': 'G10', 'production': 52.3, 'target': 50.0, 'dispatch': 51.9},
            {'subsidiary': 'SECL', 'mine': 'Kusmunda OC', 'coalfield': 'Korba', 'state': 'Chhattisgarh', 'financial_year': '2023-24', 'coal_type': 'Non-Coking', 'grade': 'G11', 'production': 44.1, 'target': 43.0, 'dispatch': 43.5},
            {'subsidiary': 'MCL', 'mine': 'Kulda OC', 'coalfield': 'Ib Valley', 'state': 'Odisha', 'financial_year': '2023-24', 'coal_type': 'Non-Coking', 'grade': 'G12', 'production': 39.4, 'target': 38.0, 'dispatch': 38.9},
            {'subsidiary': 'NCL', 'mine': 'Jayant OC', 'coalfield': 'Singrauli', 'state': 'Madhya Pradesh', 'financial_year': '2023-24', 'coal_type': 'Non-Coking', 'grade': 'G8', 'production': 29.2, 'target': 28.5, 'dispatch': 29.0},
            {'subsidiary': 'BCCL', 'mine': 'Moonidih UG', 'coalfield': 'Jharia', 'state': 'Jharkhand', 'financial_year': '2023-24', 'coal_type': 'Coking', 'grade': 'Steel-I', 'production': 21.6, 'target': 22.0, 'dispatch': 21.2},
            {'subsidiary': 'ECL', 'mine': 'Rajmahal OC', 'coalfield': 'Rajmahal', 'state': 'Jharkhand', 'financial_year': '2023-24', 'coal_type': 'Non-Coking', 'grade': 'G8', 'production': 18.2, 'target': 18.0, 'dispatch': 18.0},

            # FY 2024-25
            {'subsidiary': 'SECL', 'mine': 'Gevra OC', 'coalfield': 'Korba', 'state': 'Chhattisgarh', 'financial_year': '2024-25', 'coal_type': 'Non-Coking', 'grade': 'G10', 'production': 56.8, 'target': 54.0, 'dispatch': 56.0},
            {'subsidiary': 'SECL', 'mine': 'Kusmunda OC', 'coalfield': 'Korba', 'state': 'Chhattisgarh', 'financial_year': '2024-25', 'coal_type': 'Non-Coking', 'grade': 'G11', 'production': 47.9, 'target': 46.5, 'dispatch': 47.2},
            {'subsidiary': 'MCL', 'mine': 'Kulda OC', 'coalfield': 'Ib Valley', 'state': 'Odisha', 'financial_year': '2024-25', 'coal_type': 'Non-Coking', 'grade': 'G12', 'production': 43.5, 'target': 42.0, 'dispatch': 43.1},
            {'subsidiary': 'NCL', 'mine': 'Jayant OC', 'coalfield': 'Singrauli', 'state': 'Madhya Pradesh', 'financial_year': '2024-25', 'coal_type': 'Non-Coking', 'grade': 'G8', 'production': 32.4, 'target': 31.0, 'dispatch': 32.0},
            {'subsidiary': 'BCCL', 'mine': 'Moonidih UG', 'coalfield': 'Jharia', 'state': 'Jharkhand', 'financial_year': '2024-25', 'coal_type': 'Coking', 'grade': 'Steel-I', 'production': 23.9, 'target': 24.0, 'dispatch': 23.5},
            {'subsidiary': 'ECL', 'mine': 'Rajmahal OC', 'coalfield': 'Rajmahal', 'state': 'Jharkhand', 'financial_year': '2024-25', 'coal_type': 'Non-Coking', 'grade': 'G8', 'production': 20.1, 'target': 19.5, 'dispatch': 19.8},

            # Row with a Warning-level issue (Suspicious low production)
            {'subsidiary': 'WCL', 'mine': 'Inder UG', 'coalfield': 'Wardha', 'state': 'Maharashtra', 'financial_year': '2024-25', 'coal_type': 'Non-Coking', 'grade': 'G10', 'production': 3.2, 'target': 8.0, 'dispatch': 3.1},

            # Row with an Error-level issue (Corrupted numeric target)
            {'subsidiary': 'CCL', 'mine': 'Amrapali OC', 'coalfield': 'North Karanpura', 'state': 'Jharkhand', 'financial_year': '2024-25', 'coal_type': 'Non-Coking', 'grade': 'G11', 'production': 0.0, 'target': -999.0, 'dispatch': 0.0},
        ]

        created_records = []
        for idx, row in enumerate(sample_rows):
            is_err_row = (idx == len(sample_rows) - 1)
            rec = StructuredRecord.objects.create(
                dataset=dataset,
                row_index=idx + 1,
                data_json=row,
                is_valid=not is_err_row,
                validation_errors=[{'issue_type': 'invalid_numeric', 'severity': 'ERROR', 'message': 'Negative target value'}] if is_err_row else [],
            )
            created_records.append(rec)

            sheet_name = 'Summary_FY21_25' if idx < 24 else 'Special_Cases'
            ExtractionProvenance.objects.create(
                record=rec,
                document=doc,
                sheet_name=sheet_name,
                page_number=1 if idx < 12 else 2,
                section_heading='Table 4.1: Subsidiary Production Summaries',
                table_reference=f'tab_{sheet_name}',
                row_index=idx + 2,
                extraction_method='xlsx',
                confidence=0.98,
                source_reference=f'doc:{doc.id}:sheet:{sheet_name}:row:{idx + 2}',
            )

        # Create validation findings
        ValidationResult.objects.create(
            document=doc,
            record=created_records[24],  # Inder UG
            field_name='production',
            issue_type='suspicious_value',
            severity='WARNING',
            original_value='3.2',
            suggested_value='3.2',
            explanation='Production is over 60% below target for Inder UG colliery.',
            confidence=0.85,
            status='open',
        )
        ValidationResult.objects.create(
            document=doc,
            record=created_records[25],  # Amrapali OC
            field_name='target',
            issue_type='invalid_numeric',
            severity='ERROR',
            original_value='-999.0',
            suggested_value='15.0',
            explanation='Negative target detected; excluded from analytical aggregations.',
            confidence=0.99,
            status='open',
        )

        # Create an applied MaintainerSuggestion on Gevra OC FY24-25
        MaintainerSuggestion.objects.create(
            dataset=dataset,
            record=created_records[18],
            document=doc,
            field_name='subsidiary',
            original_value='secl',
            suggested_value='SECL',
            applied_value='SECL',
            issue_type=SuggestionIssueType.CAPITALIZATION,
            reason='Normalized subsidiary abbreviation casing to SECL.',
            confidence=1.0,
            suggestion_source=SuggestionSource.DETERMINISTIC,
            status=SuggestionStatus.APPLIED,
            created_by=user,
            reviewed_by=user,
        )

        dataset.record_count = len(created_records)
        dataset.save(update_fields=['record_count'])

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded dataset '{dataset.name}' with {len(created_records)} records "
            f"across 7 subsidiaries and 4 financial years (FY21-FY25)."
        ))
