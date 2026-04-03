from django.db import models
from django.utils import timezone


class ActiveManager(models.Manager):
    """Default manager that excludes soft-deleted records."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class AllObjectsManager(models.Manager):
    """Unfiltered manager — includes soft-deleted records."""

    def get_queryset(self):
        return super().get_queryset()
