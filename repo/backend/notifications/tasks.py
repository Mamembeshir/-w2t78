"""
notifications/tasks.py — Celery beat tasks for the notification system.

Tasks:
  send_daily_digests   — 18:00 UTC daily; per-user digest of unread notifications
  send_outbound_queued — every 5 minutes; retry QUEUED outbound messages
"""
from celery import shared_task
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# 7.4 Daily Digest
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name="notifications.send_daily_digests")
def send_daily_digests() -> dict:
    """
    Runs at 18:00 UTC daily (configured in CELERY_BEAT_SCHEDULE).

    For each user with an active DigestSchedule:
      - Collect unread non-DIGEST notifications from today
      - If any exist, create a single DIGEST Notification summarising them
      - Update last_sent_at
    """
    from .models import DigestSchedule, EventType, Notification
    from .dispatcher import dispatch_event, _queue_outbound

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    digests_sent = 0

    for schedule in DigestSchedule.objects.select_related("user").filter(
        user__is_active=True
    ):
        unread = Notification.objects.filter(
            user=schedule.user,
            is_read=False,
            created_at__gte=today_start,
        ).exclude(event_type=EventType.DIGEST)

        count = unread.count()
        if count == 0:
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
    Useful when a gateway becomes available after the initial attempt.
    """
    from django.conf import settings
    from .models import OutboundChannel, OutboundMessage, OutboundStatus
    from .dispatcher import _send_smtp, _send_sms

    smtp_host = getattr(settings, "SMTP_HOST", "")
    sms_url = getattr(settings, "SMS_GATEWAY_URL", "")

    queued = OutboundMessage.objects.filter(
        status=OutboundStatus.QUEUED
    ).select_related("notification__user")

    sent = 0
    for msg in queued:
        if msg.channel == OutboundChannel.SMTP and smtp_host:
            _send_smtp(msg)
            sent += 1
        elif msg.channel == OutboundChannel.SMS and sms_url:
            _send_sms(msg, sms_url)
            sent += 1

    return {"sent": sent}
