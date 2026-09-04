"""
SIH26023 — Audit Event Model.
Immutable audit log for all significant system actions.
"""

import uuid
from django.db import models


class AuditEvent(models.Model):
    """
    Immutable audit record for tracking user and system actions.
    Each event captures who did what, to which entity, and when.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(
        max_length=200,
        help_text="Action identifier, e.g., 'document.uploaded', 'record.validated'.",
    )
    actor = models.CharField(
        max_length=200,
        help_text="Username or system identifier that performed the action.",
    )
    entity_type = models.CharField(
        max_length=100,
        help_text="Type of entity affected, e.g., 'document', 'dataset', 'record'.",
    )
    entity_id = models.CharField(
        max_length=200,
        help_text="ID of the affected entity (UUID as string).",
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context about the action.",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit Event"
        verbose_name_plural = "Audit Events"
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.actor} at {self.timestamp}"
