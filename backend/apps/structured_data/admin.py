"""
SIH26023 — Structured Data Admin Registration.
"""

from django.contrib import admin
from .models import StructuredDataset, StructuredRecord


@admin.register(StructuredDataset)
class StructuredDatasetAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "source_document",
        "row_count",
        "created_at",
        "updated_at",
    )
    list_filter = ("created_at", "updated_at")
    search_fields = ("name", "description", "id")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(StructuredRecord)
class StructuredRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "dataset",
        "source_reference",
        "validation_status",
        "created_at",
        "updated_at",
    )
    list_filter = ("validation_status", "created_at")
    search_fields = ("source_reference", "dataset__name", "id")
    readonly_fields = ("id", "created_at", "updated_at")
