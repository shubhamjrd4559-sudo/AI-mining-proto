from django.db import models

class ExtractionResult(models.Model):
    EXTRACTOR_TYPES = [
        ('pdf_text', 'PDF Text'),
        ('pdf_ocr', 'PDF OCR'),
        ('docx', 'DOCX'),
        ('xlsx', 'XLSX'),
        ('csv', 'CSV'),
        ('txt', 'TXT'),
        ('image_ocr', 'Image OCR'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('ocr_unavailable', 'OCR Unavailable')
    ]
    
    document = models.OneToOneField('documents.Document', on_delete=models.CASCADE, related_name='extraction_result')
    extractor_type = models.CharField(max_length=30, choices=EXTRACTOR_TYPES)
    ocr_used = models.BooleanField(default=False)
    page_count = models.PositiveIntegerField(default=0)
    extraction_metadata = models.JSONField(default=dict, blank=True)  # per-page confidence, sheet names, etc.
    raw_text = models.TextField(blank=True)  # full extracted text
    extracted_tables = models.JSONField(default=list, blank=True)  # [{sheet/page, headers, rows}]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ExtractionProvenance(models.Model):
    record = models.ForeignKey('datasets.StructuredRecord', on_delete=models.CASCADE, related_name='provenance')
    document = models.ForeignKey('documents.Document', on_delete=models.CASCADE)
    page_number = models.PositiveIntegerField(null=True, blank=True)
    section_heading = models.CharField(max_length=512, blank=True)
    table_reference = models.CharField(max_length=128, blank=True)
    sheet_name = models.CharField(max_length=256, blank=True)
    row_index = models.PositiveIntegerField(null=True, blank=True)
    col_index = models.PositiveIntegerField(null=True, blank=True)
    extraction_method = models.CharField(max_length=30, blank=True)  # pdfplumber, ocr, python-docx, etc.
    ocr_used = models.BooleanField(default=False)
    confidence = models.FloatField(null=True, blank=True)
    source_reference = models.CharField(max_length=512, blank=True)  # e.g. 'doc:42:page:3:table:1:row:5'
    created_at = models.DateTimeField(auto_now_add=True)

class ValidationResult(models.Model):
    SEVERITY = [('INFO','INFO'),('WARNING','WARNING'),('ERROR','ERROR')]
    ISSUE_TYPES = [('missing_required','Missing Required'),('duplicate','Duplicate'),
                   ('invalid_numeric','Invalid Numeric'),('invalid_date','Invalid Date'),
                   ('inconsistent_unit','Inconsistent Unit'),('suspicious_value','Suspicious Value'),
                   ('coordinate_error','Coordinate Error'),('schema_mismatch','Schema Mismatch'),
                   ('extraction_failure','Extraction Failure'),('duplicate_record','Duplicate Record')]
    STATUS_CHOICES = [('open','Open'),('resolved','Resolved')]
    
    document = models.ForeignKey('documents.Document', on_delete=models.CASCADE, related_name='validation_results')
    record = models.ForeignKey('datasets.StructuredRecord', on_delete=models.SET_NULL, null=True, blank=True)
    field_name = models.CharField(max_length=256, blank=True)
    issue_type = models.CharField(max_length=30, choices=ISSUE_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY)
    original_value = models.TextField(blank=True)
    suggested_value = models.TextField(blank=True)
    explanation = models.TextField()
    confidence = models.FloatField(default=1.0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
