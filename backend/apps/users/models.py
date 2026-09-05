"""
SIH26023 — User Model.
Minimal user/role foundation for the prototype.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    Adds role and organization for CMPDI/CIL context.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        ANALYST = "analyst", "Analyst"
        VIEWER = "viewer", "Viewer"

    role = models.CharField(
        max_length=50,
        choices=Role.choices,
        default=Role.VIEWER,
    )
    organization = models.CharField(
        max_length=200,
        blank=True,
        help_text="Organization or subsidiary name.",
    )

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
