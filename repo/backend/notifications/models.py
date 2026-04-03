"""
notifications/models.py — In-app notifications, outbound messages,
subscriptions, and digest schedules.

Delivery rules:
  - In-app notifications always created regardless of gateway config.
  - SMTP/SMS outbound messages are queued; if no gateway is configured,
    messages remain QUEUED and are available for manual export.
  - Digest notifications fire daily at the time set in DigestSchedule
    (default 18:00 / 6 PM local to the server).
"""
from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class EventType(models.TextChoices):
    SAFETY_STOCK_BREACH = "SAFETY_STOCK_BREACH", "Safety Stock Breach"
    SAFETY_STOCK_RECOVERED = "SAFETY_STOCK_RECOVERED", "Safety Stock Recovered"
    CYCLE_COUNT_VARIANCE = "CYCLE_COUNT_VARIANCE", "Cycle Count Variance"
    CRAWL_TASK_FAILED = "CRAWL_TASK_FAILED", "Crawl Task Failed"
    CANARY_ROLLBACK = "CANARY_ROLLBACK", "Canary Rollback"
    SLOW_MOVING_STOCK = "SLOW_MOVING_STOCK", "Slow-Moving Stock"
    DIGEST = "DIGEST", "Daily Digest"
    SYSTEM = "SYSTEM", "System"


class OutboundChannel(models.TextChoices):
    SMTP = "SMTP", "Email (SMTP)"
    SMS = "SMS", "SMS Gateway"


class OutboundStatus(models.TextChoices):
    QUEUED = "QUEUED", "Queued"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


# ─────────────────────────────────────────────────────────────────────────────

class NotificationSubscription(TimeStampedModel):
    """
    Per-user subscription to a specific event type.

    threshold_value is used for numeric events (e.g. safety stock qty).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_subscriptions",
    )
    event_type = models.CharField(max_length=40, choices=EventType.choices, db_index=True)
    threshold_value = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "notifications_subscription"
        ordering = ["user", "event_type"]
        unique_together = [("user", "event_type")]

    def __str__(self):
        return f"{self.user.username} → {self.event_type}"


class Notification(TimeStampedModel):
    """In-app notification record."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event_type = models.CharField(max_length=40, choices=EventType.choices, db_index=True)
    title = models.CharField(max_length=300)
    body = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications_notification"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "-created_at"]),
        ]

    def __str__(self):
        read_flag = "✓" if self.is_read else "●"
        return f"{read_flag} [{self.event_type}] {self.title}"


class OutboundMessage(TimeStampedModel):
    """
    Queued or sent outbound message (SMTP / SMS).

    Linked to the Notification that triggered it.
    """

    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="outbound_messages"
    )
    channel = models.CharField(max_length=10, choices=OutboundChannel.choices)
    status = models.CharField(
        max_length=10,
        choices=OutboundStatus.choices,
        default=OutboundStatus.QUEUED,
        db_index=True,
    )
    queued_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        db_table = "notifications_outbound_message"
        ordering = ["-queued_at"]

    def __str__(self):
        return f"{self.channel}/{self.status} — {self.notification.title}"


class DigestSchedule(TimeStampedModel):
    """
    Per-user daily digest send schedule.

    send_time is a time-of-day value (HH:MM) stored as a Django TimeField.
    Default: 18:00 (6 PM).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="digest_schedule",
    )
    send_time = models.TimeField(default="18:00")
    last_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications_digest_schedule"

    def __str__(self):
        return f"{self.user.username} digest @ {self.send_time}"
