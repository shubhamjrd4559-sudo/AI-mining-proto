"""
SIH26023 — Users Admin Registration.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "organization", "is_active", "is_staff")
    list_filter = ("role", "organization", "is_active", "is_staff")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("SIH26023 Fields", {"fields": ("role", "organization")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("SIH26023 Fields", {"fields": ("role", "organization")}),
    )
