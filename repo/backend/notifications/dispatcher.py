"""
notifications/dispatcher.py — Central event dispatcher.

Usage:
    from notifications.dispatcher import dispatch_event

    dispatch_event(
        event_type=EventType.SAFETY_STOCK_BREACH,
        title="Safety stock breach: Widget A",
        body="On-hand qty dropped below threshold for 10 consecutive minutes.",
        user_ids=None,   # None = all active subscribers for this event type
    )

Behaviour:
  1. Resolve target users (subscribers or explicit list).
  2. Create a Notification record for each.
  3. Queue one OutboundMessage per channel (SMTP / SMS) per notification.
  4. Attempt immediate outbound delivery if gateway is configured.
"""
from __future__ import annotations

import logging
from typing import Iterable

logger = logging.getLogger(__name__)


def dispatch_event(
    event_type: str,
    title: str,
    body: str,
    user_ids: Iterable[int] | None = None,
) -> list:
    """
    Create Notification objects for subscribers and queue outbound messages.

    Returns the list of created Notification instances.
    """
    from .models import (
        Notification,
        NotificationSubscription,
        OutboundChannel,
        OutboundMessage,
    )

    if user_ids is not None:
        user_id_set = set(user_ids)
    else:
        # Broadcast: all active subscribers for this event type
        user_id_set = set(
            NotificationSubscription.objects.filter(
                event_type=event_type,
                is_active=True,
            ).values_list("user_id", flat=True)
        )

    created: list[Notification] = []

    for uid in user_id_set:
        n = Notification.objects.create(
            user_id=uid,
            event_type=event_type,
            title=title,
            body=body,
        )
        created.append(n)
        _queue_outbound(n)

    return created


def _queue_outbound(notification: "Notification") -> None:
    """Queue SMTP and/or SMS outbound messages based on configured gateways."""
    from django.conf import settings
    from .models import OutboundChannel, OutboundMessage

    smtp_host = getattr(settings, "SMTP_HOST", "")
    sms_url = getattr(settings, "SMS_GATEWAY_URL", "")

    if smtp_host:
        msg = OutboundMessage.objects.create(
            notification=notification,
            channel=OutboundChannel.SMTP,
        )
        _send_smtp(msg)

    if sms_url:
        msg = OutboundMessage.objects.create(
            notification=notification,
            channel=OutboundChannel.SMS,
        )
        _send_sms(msg, sms_url)

    # If no gateway is configured, no OutboundMessage is created.
    # In-app notification is always available.


def _send_smtp(outbound: "OutboundMessage") -> None:
    """Attempt SMTP delivery; update status in-place."""
    import smtplib
    from email.mime.text import MIMEText
    from django.conf import settings
    from django.utils import timezone
    from .models import OutboundStatus

    n = outbound.notification
    recipient = getattr(n.user, "email", "") or ""
    if not recipient:
        outbound.status = OutboundStatus.FAILED
        outbound.error = "User has no email address configured."
        outbound.save(update_fields=["status", "error"])
        return

    try:
        msg = MIMEText(n.body)
        msg["Subject"] = n.title
        msg["From"] = f"warehouse-notifications@{settings.SMTP_HOST}"
        msg["To"] = recipient

        with smtplib.SMTP(settings.SMTP_HOST, getattr(settings, "SMTP_PORT", 25)) as s:
            if getattr(settings, "SMTP_USE_TLS", False):
                s.starttls()
            s.sendmail(msg["From"], [recipient], msg.as_string())

        outbound.status = OutboundStatus.SENT
        outbound.sent_at = timezone.now()
        outbound.save(update_fields=["status", "sent_at"])
    except Exception as exc:
        outbound.status = OutboundStatus.FAILED
        outbound.error = str(exc)[:1000]
        outbound.save(update_fields=["status", "error"])
        logger.warning("SMTP delivery failed for notification %d: %s", n.pk, exc)


def _send_sms(outbound: "OutboundMessage", gateway_url: str) -> None:
    """Attempt SMS delivery via locally hosted gateway; update status in-place."""
    import requests
    from django.utils import timezone
    from .models import OutboundStatus

    n = outbound.notification
    phone = getattr(n.user, "phone_number", "") or ""

    try:
        resp = requests.post(
            gateway_url,
            json={"to": phone or "unknown", "message": f"{n.title}\n{n.body[:160]}"},
            timeout=10,
        )
        resp.raise_for_status()
        outbound.status = OutboundStatus.SENT
        outbound.sent_at = timezone.now()
        outbound.save(update_fields=["status", "sent_at"])
    except Exception as exc:
        outbound.status = OutboundStatus.FAILED
        outbound.error = str(exc)[:1000]
        outbound.save(update_fields=["status", "error"])
        logger.warning("SMS delivery failed for notification %d: %s", n.pk, exc)
