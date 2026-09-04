"""
apps.audit — AuditEvent model

Provides a full, immutable audit trail of all significant events in the system.

Design principles:
  - Records are append-only (never updated or deleted in normal operation).
  - Actor is stored as a string (email/username) to preserve history even if
    the user account is later deleted.
  - metadata_json allows flexible extra context per event type.

Phase 1: Model and DB table only.
Phase 2+: AuditEvent records created automatically via Django signals.
"""

from django.db import models


class AuditEventType(models.TextChoices):
    # Document lifecycle
    DOCUMENT_UPLOADED = 'document.uploaded', 'Document Uploaded'
    DOCUMENT_PROCESSED = 'document.processed', 'Document Processed'
    DOCUMENT_FAILED = 'document.failed', 'Document Processing Failed'
    DOCUMENT_REVIEWED = 'document.reviewed', 'Document Reviewed'
    DOCUMENT_APPROVED = 'document.approved', 'Document Approved'
    DOCUMENT_REJECTED = 'document.rejected', 'Document Rejected'
    DOCUMENT_DELETED = 'document.deleted', 'Document Deleted'

    # Dataset lifecycle
    DATASET_CREATED = 'dataset.created', 'Dataset Created'
    DATASET_UPDATED = 'dataset.updated', 'Dataset Updated'

    # AI / Query
    AI_QUERY_SUBMITTED = 'ai.query', 'AI Query Submitted'
    AI_REPORT_GENERATED = 'ai.report', 'AI Report Generated'

    # User / Auth
    USER_LOGIN = 'user.login', 'User Login'
    USER_LOGOUT = 'user.logout', 'User Logout'
    USER_PASSWORD_CHANGE = 'user.password_change', 'Password Changed'

    # System
    SYSTEM_HEALTH_CHECK = 'system.health_check', 'Health Check'
    SYSTEM_BACKUP = 'system.backup', 'System Backup'


class AuditEvent(models.Model):
    """
    An immutable audit log entry.

    Every significant action in the system should produce an AuditEvent.
    Records are never updated after creation.
    """

    event_type = models.CharField(
        max_length=64,
        choices=AuditEventType.choices,
        db_index=True,
        help_text='Type of event that occurred.',
    )
    actor = models.CharField(
        max_length=256,
        blank=True,
        db_index=True,
        help_text='Username or email of the user who performed the action.',
    )
    actor_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='IP address of the actor at time of action.',
    )
    resource_type = models.CharField(
        max_length=64,
        blank=True,
        help_text='Type of resource affected (e.g. "document", "dataset").',
    )
    resource_id = models.CharField(
        max_length=256,
        blank=True,
        db_index=True,
        help_text='ID or identifier of the affected resource.',
    )
    description = models.TextField(
        help_text='Human-readable description of what happened.',
    )
    metadata_json = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional structured context for this event.',
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text='When the event occurred (server time, UTC).',
    )

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Event'
        verbose_name_plural = 'Audit Events'
        # Prevent accidental updates — audit log is append-only
        # (enforced at application level; database level via signals in Phase 2)

    def __str__(self):
        return f'[{self.timestamp:%Y-%m-%d %H:%M}] {self.event_type} by {self.actor or "system"}'

    def save(self, *args, **kwargs):
        """Prevent updates to existing records — audit trail is immutable."""
        if self.pk:
            raise ValueError(
                'AuditEvent records are immutable. '
                'Do not update existing audit events.'
            )
        super().save(*args, **kwargs)
