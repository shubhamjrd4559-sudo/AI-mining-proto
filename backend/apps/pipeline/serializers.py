from rest_framework import serializers
from .models import ExtractionResult, ValidationResult, ExtractionProvenance


class ValidationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValidationResult
        fields = ['id', 'field_name', 'issue_type', 'severity', 'original_value',
                  'suggested_value', 'explanation', 'confidence', 'status', 'created_at']


class ExtractionResultSerializer(serializers.ModelSerializer):
    validation_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = ExtractionResult
        fields = ['id', 'extractor_type', 'ocr_used', 'page_count', 'status',
                  'error_message', 'extraction_metadata', 'validation_summary', 'created_at']
    
    def get_validation_summary(self, obj):
        qs = ValidationResult.objects.filter(document=obj.document)
        return {
            'total': qs.count(),
            'errors': qs.filter(severity='ERROR').count(),
            'warnings': qs.filter(severity='WARNING').count(),
            'info': qs.filter(severity='INFO').count(),
        }
