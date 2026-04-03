"""
core/models.py — Abstract base models shared across all apps.

TimeStampedModel  → created_at / updated_at
SoftDeleteModel   → soft-delete via deleted_at; exposes objects (active-only)
                    and all_objects (unfiltered) managers
"""
from django.db import models
from django.utils import timezone

from .managers import ActiveManager, AllObjectsManager


class TimeStampedModel(models.Model):
    """Abstract base that adds created_at and updated_at to every model."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(TimeStampedModel):
    """
    Abstract base that adds soft-delete support.

    .delete()      → sets deleted_at; does NOT remove the row
    .hard_delete() → permanently removes the row
    .restore()     → clears deleted_at

    Manager 'objects'     → active (non-deleted) records only
    Manager 'all_objects' → all records including soft-deleted
    """

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = ActiveManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def hard_delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])
