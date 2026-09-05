"""
apps.maintainer — Django Admin
"""

from django.contrib import admin
from .models import MaintainerSuggestion


@admin.register(MaintainerSuggestion)
class MaintainerSuggestionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'dataset', 'record', 'field_name',
        'original_value', 'suggested_value',
        'issue_type', 'suggestion_source', 'status', 'confidence',
        'created_by', 'created_at',
    ]
    list_filter = ['status', 'suggestion_source', 'issue_type']
    search_fields = ['field_name', 'original_value', 'suggested_value', 'reason']
    readonly_fields = [
        'created_at', 'reviewed_at', 'applied_at',
        'created_by', 'reviewed_by',
        'applied_value', 'error_message',
    ]
    ordering = ['-created_at']
