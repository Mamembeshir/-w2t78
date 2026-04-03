"""
crawling/quota.py — Per-source quota acquisition and release.

All public functions use SELECT … FOR UPDATE inside a transaction to ensure
strong consistency when multiple workers compete for quota slots.

Business rules (CLAUDE.md §4):
  - Quota deducted BEFORE the request executes.
  - On completion (success or failure), quota is released.
  - Held quotas auto-released after 15 minutes via Celery beat task.
  - Waitlisted tasks auto-promote within 5 seconds when capacity frees.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import CrawlSource, SourceQuota

_HOLD_MINUTES = 15
_WINDOW_SECONDS = 60


def acquire_quota(source: CrawlSource) -> bool:
    """
    Attempt to acquire one quota slot for *source*.

    Returns True (slot granted, current_count incremented, held_until set)
    or False (window is full — caller should set task status to WAITING).

    Runs atomically inside SELECT FOR UPDATE.
    """
    with transaction.atomic():
        quota, _ = SourceQuota.objects.select_for_update().get_or_create(
            source=source,
            defaults={
                "rpm_limit": source.rate_limit_rpm,
                "current_count": 0,
                "window_start": timezone.now(),
            },
        )

        now = timezone.now()

        # Sync rpm_limit with source config on every check
        if quota.rpm_limit != source.rate_limit_rpm:
            quota.rpm_limit = source.rate_limit_rpm

        # Expire the current window if 60 seconds have passed
        if quota.window_start is None or (now - quota.window_start).total_seconds() >= _WINDOW_SECONDS:
            quota.current_count = 0
            quota.window_start = now
            quota.held_until = None

        if quota.current_count < quota.rpm_limit:
            quota.current_count += 1
            quota.held_until = now + timedelta(minutes=_HOLD_MINUTES)
            quota.save()
            return True

        return False


def release_quota(source: CrawlSource) -> None:
    """
    Release one quota slot for *source* after request completion.

    Decrements current_count (floor 0) and clears held_until.
    """
    with transaction.atomic():
        try:
            quota = SourceQuota.objects.select_for_update().get(source=source)
            quota.current_count = max(0, quota.current_count - 1)
            quota.held_until = None
            quota.save(update_fields=["current_count", "held_until"])
        except SourceQuota.DoesNotExist:
            pass
