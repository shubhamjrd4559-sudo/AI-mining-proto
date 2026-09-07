from django.contrib import admin
from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'report_type', 'status', 'organization', 'date_range', 'created_by', 'created_at')
    list_filter = ('report_type', 'status', 'organization', 'created_at')
    search_fields = ('title', 'organization', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at', 'verified_at', 'approved_at', 'revision_count')
