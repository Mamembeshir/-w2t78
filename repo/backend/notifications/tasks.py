"""
notifications/tasks.py — Celery beat tasks for the notification system.

Tasks:
  send_daily_digests   — runs every minute; fires for users whose send_time matches now
  send_outbound_queued — every 5 minutes; retry QUEUED outbound messages
"""
from datetime import timedelta

from celery import shared_task
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# 7.4 Daily Digest
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name="notifications.send_daily_digests")
def send_daily_digests(_now=None) -> dict:
    """
    Runs every minute (configured in CELERY_BEAT_SCHEDULE).

    Finds DigestSchedule rows whose send_time hour:minute matches the current
    UTC minute and have not already been sent today, then for each:
      - Collect unread non-DIGEST notifications from today
      - If any exist, create a single DIGEST Notification summarising them
      - Update last_sent_at to prevent same-day duplicate sends

    _now: optional datetime for testing; defaults to timezone.now().
    """
    from .models import DigestSchedule, EventType, Notification
    from .dispatcher import _queue_outbound

    now = _now if _now is not None else timezone.now()
    # Convert to the configured Django timezone so the digest fires at the
    # operator's wall-clock 6 PM (SPEC: "6:00 PM"), not necessarily 6 PM UTC.
    local_now = timezone.localtime(now)
    today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Only process schedules whose send_time matches the current hour:minute
    # (in the site's configured TIME_ZONE) and that have not already been
    # sent today.
    due_schedules = DigestSchedule.objects.select_related("user").filter(
        user__is_active=True,
        send_time__hour=local_now.hour,
        send_time__minute=local_now.minute,
    ).exclude(
        last_sent_at__gte=today_start,
    )

    digests_sent = 0

    for schedule in due_schedules:
        unread = Notification.objects.filter(
            user=schedule.user,
            is_read=False,
            created_at__gte=today_start,
        ).exclude(event_type=EventType.DIGEST)

        count = unread.count()
        if count == 0:
            # Mark as processed so we don't re-check if the task re-runs
            # at the same minute (e.g. worker restart).
            schedule.last_sent_at = now
            schedule.save(update_fields=["last_sent_at"])
            continue

        # Build summary body
        lines = [f"You have {count} unread notification{'s' if count != 1 else ''} today:\n"]
        for n in unread[:20]:
            lines.append(f"• [{n.event_type}] {n.title}")
        if count > 20:
            lines.append(f"…and {count - 20} more.")

        body = "\n".join(lines)
        title = f"Daily digest: {count} unread notification{'s' if count != 1 else ''}"

        digest_n = Notification.objects.create(
            user=schedule.user,
            event_type=EventType.DIGEST,
            title=title,
            body=body,
        )
        _queue_outbound(digest_n)

        schedule.last_sent_at = now
        schedule.save(update_fields=["last_sent_at"])
        digests_sent += 1

    return {"digests_sent": digests_sent}


# ─────────────────────────────────────────────────────────────────────────────
# 7.5 Outbound retry
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name="notifications.send_outbound_queued")
def send_outbound_queued() -> dict:
    """
    Runs every 5 minutes.

    Retries any OutboundMessage stuck in QUEUED status.
    Gateway configuration is read from SystemSettings (admin-managed DB record),
    not from environment variables, so UI-saved values govern delivery.
    """
    from .models import OutboundChannel, OutboundMessage, OutboundStatus, SystemSettings
    from .dispatcher import _send_smtp, _send_sms

    cfg = SystemSettings.get()

    queued = OutboundMessage.objects.filter(
        status=OutboundStatus.QUEUED
    ).select_related("notification__user")

    attempted = 0
    sent_success = 0
    for msg in queued:
        if msg.channel == OutboundChannel.SMTP and cfg.smtp_host:
            _send_smtp(msg, cfg)
            attempted += 1
        elif msg.channel == OutboundChannel.SMS and cfg.sms_gateway_url:
            _send_sms(msg, cfg.sms_gateway_url)
            attempted += 1
        else:
            continue
        msg.refresh_from_db()
        if msg.status == OutboundStatus.SENT:
            sent_success += 1

    return {"attempted": attempted, "sent_success": sent_success}


# ─────────────────────────────────────────────────────────────────────────────
# 365-day retention purge
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name="notifications.purge_old_notification_records")
def purge_old_notification_records() -> dict:
    """
    Nightly. Delete Notification and OutboundMessage rows older than 365 days.

    OutboundMessage is deleted first (FK → Notification) to avoid constraint
    violations on databases that do not cascade deletes automatically.
    """
    from .models import Notification, OutboundMessage

    cutoff = timezone.now() - timedelta(days=365)

    # Outbound messages reference Notifications — delete them first
    deleted_outbound, _ = OutboundMessage.objects.filter(created_at__lt=cutoff).delete()
    deleted_notif, _ = Notification.objects.filter(created_at__lt=cutoff).delete()

    return {
        "notifications_deleted": deleted_notif,
        "outbound_deleted": deleted_outbound,
        "cutoff": cutoff.isoformat(),
    }
