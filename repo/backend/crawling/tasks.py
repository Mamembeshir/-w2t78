"""
crawling/tasks.py — Celery beat tasks for crawling automation.

Tasks:
  monitor_canary_versions    — every minute; auto-rollback or auto-promote canaries
  release_held_quotas        — every 15 minutes; expire stale quota holds
  promote_waiting_tasks      — every 5 seconds; retry WAITING tasks when quota frees
"""
from datetime import timedelta

from celery import shared_task
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# 6.7 Canary Monitoring
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name="crawling.monitor_canary_versions")
def monitor_canary_versions() -> dict:
    """
    Runs every minute.

    For each rule version currently in canary:
      - If error_rate > 2%: auto-rollback + fire notification
      - If 30 minutes elapsed with error_rate ≤ 2%: promote to active
    """
    from .models import CrawlRuleVersion, CrawlTaskStatus

    now = timezone.now()
    canary_window = timedelta(minutes=30)
    error_threshold = 2.0

    rolled_back = 0
    promoted = 0

    canaries = CrawlRuleVersion.objects.filter(is_canary=True).select_related("source")

    for version in canaries:
        if version.canary_started_at is None:
            continue

        # Calculate error rate for tasks using this canary version
        total = version.tasks.filter(
            status__in=[CrawlTaskStatus.COMPLETED, CrawlTaskStatus.FAILED]
        ).count()
        failed = version.tasks.filter(status=CrawlTaskStatus.FAILED).count()
        error_rate = (failed / total * 100) if total > 0 else 0.0

        elapsed = now - version.canary_started_at

        if error_rate > error_threshold:
            _rollback_canary(version, reason=f"error_rate={error_rate:.1f}% > {error_threshold}%")
            rolled_back += 1

        elif elapsed >= canary_window:
            _promote_canary(version)
            promoted += 1

    return {"rolled_back": rolled_back, "promoted": promoted}


def _rollback_canary(version, reason: str = "") -> None:
    """Deactivate the canary, restore the previous active version."""
    from notifications.models import EventType, Notification, NotificationSubscription

    source = version.source

    # Find the version that was active before this canary
    previous = (
        source.rule_versions
        .filter(is_active=True)
        .exclude(pk=version.pk)
        .order_by("-version_number")
        .first()
    )

    version.is_canary = False
    version.is_active = False
    version.canary_started_at = None
    version.save(update_fields=["is_canary", "is_active", "canary_started_at"])

    # Ensure previous version is still active (it should be — we never deactivated it)
    if previous and not previous.is_active:
        previous.is_active = True
        previous.save(update_fields=["is_active"])

    # Notify CRAWL_CANARY_FAILED subscribers
    try:
        subscriptions = NotificationSubscription.objects.filter(
            event_type=EventType.CANARY_ROLLBACK,
            is_active=True,
        ).select_related("user")
        body = (
            f"Canary rollback for '{source.name}' v{version.version_number}.\n"
            f"Reason: {reason}\n"
            f"Restored to: v{previous.version_number if previous else '—'}"
        )
        for sub in subscriptions:
            Notification.objects.create(
                user=sub.user,
                event_type=EventType.CANARY_ROLLBACK,
                title=f"Canary rolled back: {source.name}",
                body=body,
            )
    except Exception:
        pass


def _promote_canary(version) -> None:
    """Promote the canary version to full active, deactivate old active."""
    source = version.source

    # Deactivate all other active versions for this source
    source.rule_versions.filter(is_active=True).exclude(pk=version.pk).update(
        is_active=False
    )

    version.is_canary = False
    version.is_active = True
    version.canary_started_at = None
    version.save(update_fields=["is_canary", "is_active", "canary_started_at"])


# ─────────────────────────────────────────────────────────────────────────────
# 6.4 Quota auto-release
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name="crawling.release_held_quotas")
def release_held_quotas() -> dict:
    """
    Runs every 15 minutes.

    Resets current_count to 0 for any SourceQuota rows where
    held_until has passed — prevents resource oversubscription when
    workers crash without releasing quota.
    """
    from .models import SourceQuota

    now = timezone.now()
    updated = SourceQuota.objects.filter(held_until__lt=now).update(
        current_count=0, held_until=None
    )
    return {"quotas_released": updated}


# ─────────────────────────────────────────────────────────────────────────────
# 6.4 Waitlist promotion
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name="crawling.promote_waiting_tasks")
def promote_waiting_tasks() -> dict:
    """
    Runs every 5 seconds.

    Finds WAITING tasks and, for each, attempts to acquire quota.
    On success: re-trigger execute_crawl_task.
    """
    from .models import CrawlTask, CrawlTaskStatus
    from .quota import acquire_quota
    from .worker import execute_crawl_task

    waiting = CrawlTask.objects.filter(
        status=CrawlTaskStatus.WAITING
    ).select_related("source").order_by("priority", "created_at")

    promoted = 0
    for task in waiting:
        if acquire_quota(task.source):
            task.status = CrawlTaskStatus.PENDING
            task.save(update_fields=["status"])
            execute_crawl_task.delay(task.pk)
            promoted += 1

    return {"promoted": promoted}
