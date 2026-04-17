"""
tests/notifications/test_outbound.py — Outbound queue and retention tests.

Covers the admin outbound-queued endpoint, send_outbound_queued retry task,
and 365-day notification/outbound retention purge.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from notifications.models import (
    EventType,
    Notification,
    OutboundMessage,
    OutboundStatus,
)
from notifications.tasks import send_outbound_queued


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
    from notifications.models import NotificationSubscription
    return NotificationSubscription.objects.create(
        user=user,
        event_type=event_type,
        threshold_value=threshold,
        is_active=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7.5 Outbound Queue Endpoint (admin)
# ─────────────────────────────────────────────────────────────────────────────

class OutboundQueuedTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = create_user("out_admin", Role.ADMIN)
        self.user = create_user("out_user")
        token = login(self.client, "out_admin")
        auth(self.client, token)

    def _create_queued_message(self):
        n = Notification.objects.create(
            user=self.user,
            event_type=EventType.SYSTEM,
            title="Test notification",
            body=".",
        )
        from notifications.models import OutboundChannel
        return OutboundMessage.objects.create(
            notification=n,
            channel=OutboundChannel.SMTP,
            status=OutboundStatus.QUEUED,
        )

    def test_admin_can_list_queued_messages(self):
        self._create_queued_message()
        resp = self.client.get("/api/notifications/outbound/queued/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["count"], 1)

    def test_non_admin_cannot_access(self):
        client2 = APIClient()
        token = login(client2, "out_user")
        auth(client2, token)
        resp = client2.get("/api/notifications/outbound/queued/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_sent_messages_not_in_queued_list(self):
        msg = self._create_queued_message()
        msg.status = OutboundStatus.SENT
        msg.save()
        resp = self.client.get("/api/notifications/outbound/queued/")
        self.assertEqual(resp.json()["count"], 0)

    def test_retrieve_queued_message_detail(self):
        msg = self._create_queued_message()
        resp = self.client.get(f"/api/notifications/outbound/queued/{msg.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("channel", data)
        self.assertIn("status", data)
        self.assertEqual(data["status"], OutboundStatus.QUEUED)

    def test_retrieve_queued_message_non_admin_forbidden(self):
        msg = self._create_queued_message()
        client2 = APIClient()
        token = login(client2, "out_user")
        auth(client2, token)
        resp = client2.get(f"/api/notifications/outbound/queued/{msg.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ─────────────────────────────────────────────────────────────────────────────
# 7.8 send_outbound_queued task
# ─────────────────────────────────────────────────────────────────────────────

class SendOutboundQueuedTaskTests(TestCase):
    """Tests for the send_outbound_queued Celery task (retry logic)."""

    def setUp(self):
        from notifications.models import OutboundChannel
        self.user = create_user("queued_user")
        self.OutboundChannel = OutboundChannel

    def _make_queued(self, channel=None):
        if channel is None:
            channel = self.OutboundChannel.SMTP
        n = Notification.objects.create(
            user=self.user,
            event_type=EventType.SYSTEM,
            title="Queued msg",
            body=".",
        )
        return OutboundMessage.objects.create(
            notification=n,
            channel=channel,
            status=OutboundStatus.QUEUED,
        )

    def test_returns_zero_when_no_queued_messages(self):
        result = send_outbound_queued()
        self.assertEqual(result["attempted"], 0)
        self.assertEqual(result["sent_success"], 0)

    def test_queued_smtp_not_sent_when_no_smtp_host(self):
        """With no SMTP_HOST, queued SMTP messages remain untouched."""
        self._make_queued(self.OutboundChannel.SMTP)
        result = send_outbound_queued()
        self.assertEqual(result["attempted"], 0)
        # Status must still be QUEUED
        self.assertEqual(
            OutboundMessage.objects.filter(status=OutboundStatus.QUEUED).count(), 1
        )

    def test_queued_sms_not_sent_when_no_sms_gateway(self):
        """With no SMS_GATEWAY_URL, queued SMS messages remain untouched."""
        self._make_queued(self.OutboundChannel.SMS)
        result = send_outbound_queued()
        self.assertEqual(result["attempted"], 0)
        self.assertEqual(
            OutboundMessage.objects.filter(status=OutboundStatus.QUEUED).count(), 1
        )

    def test_already_sent_messages_are_not_retried(self):
        """Messages in SENT status are not processed by the retry task."""
        msg = self._make_queued()
        msg.status = OutboundStatus.SENT
        msg.save()

        result = send_outbound_queued()
        self.assertEqual(result["attempted"], 0)

    def test_already_failed_messages_are_not_retried(self):
        """Messages in FAILED status are not processed by the retry task."""
        msg = self._make_queued()
        msg.status = OutboundStatus.FAILED
        msg.save()

        result = send_outbound_queued()
        self.assertEqual(result["attempted"], 0)

    def test_queued_smtp_attempted_when_smtp_host_set(self):
        """
        When smtp_host is set in SystemSettings, send_outbound_queued attempts
        delivery (fails with bogus host → FAILED status).
        attempted increments; sent_success stays 0 because the send failed.
        Gateway config is read from SystemSettings, not from env variables.
        """
        from notifications.models import SystemSettings
        self.user.email = "test@example.local"
        self.user.save()
        msg = self._make_queued(self.OutboundChannel.SMTP)

        # Configure gateway via SystemSettings (not env override)
        cfg = SystemSettings.get()
        cfg.smtp_host = "localhost"
        cfg.smtp_port = 1  # unreachable → triggers exception path
        cfg.save()

        result = send_outbound_queued()

        self.assertEqual(result["attempted"], 1)
        self.assertEqual(result["sent_success"], 0)
        msg.refresh_from_db()
        self.assertEqual(msg.status, OutboundStatus.FAILED)
        self.assertTrue(len(msg.error) > 0)

    def test_send_outbound_respects_system_settings_not_env(self):
        """
        send_outbound_queued must NOT use env SMTP_HOST; only SystemSettings governs delivery.
        A QUEUED message must remain untouched when env has SMTP_HOST but SystemSettings is empty.
        """
        from django.test import override_settings
        msg = self._make_queued(self.OutboundChannel.SMTP)

        # Env has SMTP_HOST but SystemSettings (default) has empty smtp_host
        with override_settings(SMTP_HOST="localhost", SMTP_PORT=25):
            result = send_outbound_queued()

        self.assertEqual(result["attempted"], 0)
        msg.refresh_from_db()
        self.assertEqual(msg.status, OutboundStatus.QUEUED)


# ─────────────────────────────────────────────────────────────────────────────
# 365-day notification/outbound retention purge (Finding 4)
# ─────────────────────────────────────────────────────────────────────────────

class NotificationRetentionTests(TestCase):
    """
    Verify purge_old_notification_records deletes Notification and
    OutboundMessage rows older than 365 days and retains recent ones.
    """

    def setUp(self):
        self.user = create_user("retention_user")

    def _make_notification(self):
        return Notification.objects.create(
            user=self.user,
            event_type=EventType.SYSTEM,
            title="Retention test",
            body=".",
        )

    def _make_outbound(self, notification):
        from notifications.models import OutboundChannel
        return OutboundMessage.objects.create(
            notification=notification,
            channel=OutboundChannel.SMTP,
            status=OutboundStatus.QUEUED,
        )

    def _age(self, obj, model_class, days):
        old_ts = timezone.now() - timedelta(days=days)
        model_class.objects.filter(pk=obj.pk).update(created_at=old_ts)

    def test_old_notifications_are_deleted(self):
        from notifications.tasks import purge_old_notification_records
        old = self._make_notification()
        self._age(old, Notification, 366)

        result = purge_old_notification_records()

        self.assertFalse(Notification.objects.filter(pk=old.pk).exists())
        self.assertGreaterEqual(result["notifications_deleted"], 1)

    def test_recent_notifications_are_kept(self):
        from notifications.tasks import purge_old_notification_records
        recent = self._make_notification()
        # created_at defaults to now — within retention window

        purge_old_notification_records()

        self.assertTrue(Notification.objects.filter(pk=recent.pk).exists())

    def test_old_outbound_messages_are_deleted(self):
        from notifications.tasks import purge_old_notification_records
        notif = self._make_notification()
        msg = self._make_outbound(notif)
        self._age(msg, OutboundMessage, 366)

        result = purge_old_notification_records()

        self.assertFalse(OutboundMessage.objects.filter(pk=msg.pk).exists())
        self.assertGreaterEqual(result["outbound_deleted"], 1)

    def test_recent_outbound_messages_are_kept(self):
        from notifications.tasks import purge_old_notification_records
        notif = self._make_notification()
        msg = self._make_outbound(notif)

        purge_old_notification_records()

        self.assertTrue(OutboundMessage.objects.filter(pk=msg.pk).exists())

    def test_purge_returns_cutoff_isoformat(self):
        from notifications.tasks import purge_old_notification_records
        result = purge_old_notification_records()
        self.assertIn("cutoff", result)
        # Should be parseable as an ISO datetime
        from django.utils.dateparse import parse_datetime
        self.assertIsNotNone(parse_datetime(result["cutoff"]))
