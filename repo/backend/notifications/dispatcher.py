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
    """
    Create SMTP and SMS OutboundMessage rows for this notification and attempt
    immediate delivery if the respective gateway is configured in SystemSettings.

    Rows are always created (status=QUEUED) so that when no gateway is present
    messages remain available for manual export per SPEC §7.
    """
    from .models import OutboundChannel, OutboundMessage, SystemSettings

    cfg = SystemSettings.get()

    smtp_msg = OutboundMessage.objects.create(
        notification=notification,
        channel=OutboundChannel.SMTP,
    )
    if cfg.smtp_host:
        _send_smtp(smtp_msg, cfg)

    sms_msg = OutboundMessage.objects.create(
        notification=notification,
        channel=OutboundChannel.SMS,
    )
    if cfg.sms_gateway_url:
        _send_sms(sms_msg, cfg.sms_gateway_url)


def _send_smtp(outbound: "OutboundMessage", cfg=None) -> None:
    """
    Attempt SMTP delivery; update status in-place.

    cfg — SystemSettings instance (fetched from DB if not supplied).
    """
    import smtplib
    from email.mime.text import MIMEText
    from django.utils import timezone
    from .models import OutboundStatus, SystemSettings

    if cfg is None:
        cfg = SystemSettings.get()

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
        msg["From"] = f"warehouse-notifications@{cfg.smtp_host}"
        msg["To"] = recipient

        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as s:
            if cfg.smtp_use_tls:
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
