"""
audit/models.py — Immutable audit log and 365-day purge Celery task.

AuditLog captures every mutating request (POST/PUT/PATCH/DELETE) via
the audit middleware written in Phase 3.3.  Records are immutable — no
update or delete is exposed through the ORM on purpose.

Retention: 365 days, enforced nightly by the purge_old_audit_logs task.
"""
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


class AuditLog(TimeStampedModel):
    """
    One row per state-changing API action.

    user       — nullable so system-level actions (e.g. Celery tasks) can
                 be logged with user=None.
    changes    — JSON dict of {field: [old_value, new_value]} pairs.
    ip_address — taken from request.META['REMOTE_ADDR'].
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=20, db_index=True)   # CREATE / UPDATE / DELETE
    model_name = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=50, db_index=True)
    changes = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_log"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["model_name", "object_id"]),
            models.Index(fields=["user", "-timestamp"]),
        ]

    def __str__(self):
        who = self.user.username if self.user else "system"
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {who} {self.action} {self.model_name}#{self.object_id}"

    def delete(self, *args, **kwargs):
        """Audit logs are immutable — disallow ORM deletion."""
        raise NotImplementedError("AuditLog records cannot be deleted via ORM. Use the purge task.")

    def save(self, *args, **kwargs):
        """Prevent updates to existing rows."""
        if self.pk is not None:
            raise NotImplementedError("AuditLog records are immutable.")
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Celery task — nightly purge of records older than 365 days
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name="audit.purge_old_audit_logs")
def purge_old_audit_logs():
    """
    Delete AuditLog rows older than 365 days.

    Scheduled in settings.CELERY_BEAT_SCHEDULE to run nightly at 02:00.
    Uses AuditLog._base_manager to bypass the immutability guard on .delete().
    """
    cutoff = timezone.now() - timedelta(days=365)
    # QuerySet.delete() uses SQL DELETE directly — it does NOT invoke the
    # model's instance .delete() method, so our immutability guard is not triggered.
    deleted_count, _ = AuditLog._default_manager.filter(timestamp__lt=cutoff).delete()
    return {"deleted": deleted_count, "cutoff": cutoff.isoformat()}
