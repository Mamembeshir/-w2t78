"""
tests/notifications/test_dispatcher.py — Event dispatcher tests.

Covers notification creation for subscribers, active-only filtering,
explicit user_ids, outbound message queueing, and SMTP delivery attempt.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from notifications.dispatcher import dispatch_event
from notifications.models import (
    EventType,
    Notification,
    NotificationSubscription,
    OutboundMessage,
    OutboundStatus,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username, role=Role.PROCUREMENT_ANALYST):
    return User.objects.create_user(
        username=username, password="testpass1234", role=role
    )


def login(client, username):
    resp = client.post(
        "/api/auth/login/", {"username": username, "password": "testpass1234"}
    )
    return resp.json()["access"]


def auth(client, token):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def subscribe(user, event_type, threshold=None):
    return NotificationSubscription.objects.create(
        user=user,
        event_type=event_type,
        threshold_value=threshold,
        is_active=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7.1 Event Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

class DispatcherTests(TestCase):
    def setUp(self):
        self.user1 = create_user("disp_user1")
        self.user2 = create_user("disp_user2")

    def test_dispatch_creates_notification_for_subscribers(self):
        subscribe(self.user1, EventType.CRAWL_TASK_FAILED)
        subscribe(self.user2, EventType.CRAWL_TASK_FAILED)

        created = dispatch_event(
            EventType.CRAWL_TASK_FAILED,
            title="Crawl task failed",
            body="Task #1 exhausted retries.",
        )

        self.assertEqual(len(created), 2)
        user_ids = {n.user_id for n in created}
        self.assertIn(self.user1.pk, user_ids)
        self.assertIn(self.user2.pk, user_ids)

    def test_dispatch_only_active_subscribers(self):
        subscribe(self.user1, EventType.SLOW_MOVING_STOCK)
        # user2 is inactive
        NotificationSubscription.objects.create(
            user=self.user2,
            event_type=EventType.SLOW_MOVING_STOCK,
            is_active=False,
        )

        created = dispatch_event(
            EventType.SLOW_MOVING_STOCK,
            title="Slow moving",
            body="Item X has no issues for 90 days.",
        )
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].user_id, self.user1.pk)

    def test_dispatch_explicit_user_ids(self):
        # Even without subscription, explicit user_ids receive notifications
        created = dispatch_event(
            EventType.SYSTEM,
            title="System message",
            body="Maintenance tonight.",
            user_ids=[self.user1.pk],
        )
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].user_id, self.user1.pk)

    def test_dispatch_no_subscribers_creates_none(self):
        created = dispatch_event(
            EventType.CANARY_ROLLBACK,
            title="Canary rolled back",
            body="Source X v2 rolled back.",
        )
        self.assertEqual(len(created), 0)

    def test_notification_fields(self):
        subscribe(self.user1, EventType.SAFETY_STOCK_BREACH)
        created = dispatch_event(
            EventType.SAFETY_STOCK_BREACH,
            title="Low stock: Widget A",
            body="Below threshold for 10 minutes.",
        )
        n = created[0]
        self.assertEqual(n.event_type, EventType.SAFETY_STOCK_BREACH)
        self.assertEqual(n.title, "Low stock: Widget A")
        self.assertFalse(n.is_read)
        self.assertIsNone(n.read_at)

    def test_outbound_message_queued_when_no_gateway(self):
        """
        When no gateway is configured, OutboundMessages are still created with
        QUEUED status so they are available for manual export (SPEC §7).
        """
        from notifications.models import OutboundChannel, OutboundStatus
        subscribe(self.user1, EventType.CRAWL_TASK_FAILED)
        dispatch_event(
            EventType.CRAWL_TASK_FAILED,
            title="Failed",
            body="Test.",
        )
        # One SMTP row + one SMS row created per notification, both QUEUED
        self.assertEqual(OutboundMessage.objects.count(), 2)
        channels = set(OutboundMessage.objects.values_list("channel", flat=True))
        self.assertIn(OutboundChannel.SMTP, channels)
        self.assertIn(OutboundChannel.SMS, channels)
        queued = OutboundMessage.objects.filter(status=OutboundStatus.QUEUED).count()
        self.assertEqual(queued, 2)

    def test_outbound_message_smtp_attempted_when_smtp_configured(self):
        """
        When smtp_host is set in SystemSettings, dispatch attempts SMTP delivery
        immediately (fails with bogus host → FAILED status, not QUEUED).
        """
        from notifications.models import OutboundChannel, OutboundStatus, SystemSettings
        subscribe(self.user1, EventType.CRAWL_TASK_FAILED)
        self.user1.email = "analyst@warehouse.local"
        self.user1.save()

        cfg = SystemSettings.get()
        cfg.smtp_host = "localhost"
        cfg.smtp_port = 1  # unreachable → triggers exception path
        cfg.save()

        dispatch_event(EventType.CRAWL_TASK_FAILED, title="T", body="B")

        smtp_msg = OutboundMessage.objects.get(channel=OutboundChannel.SMTP)
        # Immediate delivery was attempted; bogus host → FAILED (not QUEUED)
        self.assertEqual(smtp_msg.status, OutboundStatus.FAILED)
        self.assertTrue(len(smtp_msg.error) > 0)
