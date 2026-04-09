"""
notifications/tests.py — Real-database integration tests for Phase 7.

Run:
  docker compose exec backend python manage.py test notifications --verbosity=2 --keepdb

Tests cover:
  7.1  Event dispatcher — creates notifications for subscribers
  7.2  Subscription API — list, create, delete, upsert
  7.3  Inbox API — list, filter, mark read, mark all read, unread count
  7.4  Digest task — creates digest notification per user
  7.5  Outbound queueing — messages queued when no gateway configured
  7.6  Outbound queued endpoint (admin only)
  7.7  Digest schedule API — get and patch
  7.8  System Settings API — auth/validation/error contract
"""
from datetime import timedelta


from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User

from .dispatcher import dispatch_event
from .models import (
    DigestSchedule,
    EventType,
    Notification,
    NotificationSubscription,
    OutboundMessage,
    OutboundStatus,
)
from .tasks import send_daily_digests, send_outbound_queued


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
        from .models import OutboundChannel, OutboundStatus
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
        from .models import OutboundChannel, OutboundStatus, SystemSettings
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


# ─────────────────────────────────────────────────────────────────────────────
# 7.2 Subscription API
# ─────────────────────────────────────────────────────────────────────────────

class SubscriptionAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user("sub_user")
        token = login(self.client, "sub_user")
        auth(self.client, token)

    def test_list_subscriptions_empty(self):
        resp = self.client.get("/api/notifications/subscriptions/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["count"], 0)

    def test_subscribe_creates_subscription(self):
        resp = self.client.post(
            "/api/notifications/subscriptions/",
            {"event_type": "CRAWL_TASK_FAILED"},
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()["event_type"], "CRAWL_TASK_FAILED")
        self.assertTrue(resp.json()["is_active"])

    def test_subscribe_invalid_event_type(self):
        resp = self.client.post(
            "/api/notifications/subscriptions/",
            {"event_type": "FAKE_EVENT"},
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_subscribe_upsert_reactivates(self):
        # Create inactive subscription
        sub = subscribe(self.user, EventType.SLOW_MOVING_STOCK)
        sub.is_active = False
        sub.save()

        # POST again → should re-activate
        resp = self.client.post(
            "/api/notifications/subscriptions/",
            {"event_type": "SLOW_MOVING_STOCK"},
        )
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        sub.refresh_from_db()
        self.assertTrue(sub.is_active)

    def test_unsubscribe(self):
        sub = subscribe(self.user, EventType.CANARY_ROLLBACK)
        resp = self.client.delete(f"/api/notifications/subscriptions/{sub.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            NotificationSubscription.objects.filter(pk=sub.pk).exists()
        )

    def test_list_shows_my_subscriptions_only(self):
        other = create_user("other_sub_user")
        subscribe(other, EventType.DIGEST)
        subscribe(self.user, EventType.CRAWL_TASK_FAILED)

        resp = self.client.get("/api/notifications/subscriptions/")
        event_types = [s["event_type"] for s in resp.json()["results"]]
        self.assertIn("CRAWL_TASK_FAILED", event_types)
        self.assertNotIn("DIGEST", event_types)

    def test_cannot_delete_another_users_subscription(self):
        """IDOR guard: attempting to DELETE another user's subscription returns 404."""
        other = create_user("idor_sub_other")
        other_sub = subscribe(other, EventType.CRAWL_TASK_FAILED)
        resp = self.client.delete(f"/api/notifications/subscriptions/{other_sub.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        # Subscription still exists — not deleted
        self.assertTrue(NotificationSubscription.objects.filter(pk=other_sub.pk).exists())


# ─────────────────────────────────────────────────────────────────────────────
# 7.3 Inbox API
# ─────────────────────────────────────────────────────────────────────────────

class InboxAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user("inbox_user")
        token = login(self.client, "inbox_user")
        auth(self.client, token)

    def _make_notification(self, event_type=EventType.SYSTEM, title="Test"):
        return Notification.objects.create(
            user=self.user,
            event_type=event_type,
            title=title,
            body="Body text.",
        )

    def test_inbox_lists_own_notifications(self):
        other = create_user("inbox_other")
        self._make_notification()
        Notification.objects.create(
            user=other, event_type=EventType.SYSTEM, title="Other", body="."
        )
        resp = self.client.get("/api/notifications/inbox/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["count"], 1)

    def test_inbox_filter_unread(self):
        n1 = self._make_notification(title="Unread")
        n2 = self._make_notification(title="Read")
        n2.is_read = True
        n2.read_at = timezone.now()
        n2.save()

        resp = self.client.get("/api/notifications/inbox/?unread=1")
        titles = [n["title"] for n in resp.json()["results"]]
        self.assertIn("Unread", titles)
        self.assertNotIn("Read", titles)

    def test_inbox_filter_event_type(self):
        self._make_notification(event_type=EventType.SYSTEM, title="System msg")
        self._make_notification(event_type=EventType.DIGEST, title="Digest msg")

        resp = self.client.get("/api/notifications/inbox/?event_type=SYSTEM")
        titles = [n["title"] for n in resp.json()["results"]]
        self.assertIn("System msg", titles)
        self.assertNotIn("Digest msg", titles)

    def test_unread_count(self):
        self._make_notification()
        self._make_notification()
        n = self._make_notification()
        n.is_read = True
        n.save()

        resp = self.client.get("/api/notifications/inbox/unread-count/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["unread_count"], 2)

    def test_mark_notification_read(self):
        n = self._make_notification()
        self.assertFalse(n.is_read)

        resp = self.client.post(f"/api/notifications/inbox/{n.pk}/read/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        self.assertIsNotNone(n.read_at)

    def test_mark_all_read(self):
        for _ in range(5):
            self._make_notification()

        resp = self.client.post("/api/notifications/inbox/read-all/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["marked_read"], 5)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_read=False).count(), 0
        )

    def test_cannot_read_another_users_notification(self):
        other = create_user("inbox_other2")
        n = Notification.objects.create(
            user=other, event_type=EventType.SYSTEM, title="Other", body="."
        )
        resp = self.client.post(f"/api/notifications/inbox/{n.pk}/read/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


# ─────────────────────────────────────────────────────────────────────────────
# 7.4 Digest Task
# ─────────────────────────────────────────────────────────────────────────────

class DigestTaskTests(TestCase):
    """
    All tests pass a fixed `_now` to send_daily_digests() so they are never
    sensitive to wall-clock timing or minute-boundary race conditions.

    `fixed_now` is always today at 09:00 UTC so that `today_start` (derived
    from `_now`) aligns with the real timestamps of notifications created in
    each test.  `other_send_time` (18:00) is a distinct time guaranteed not to
    match `fixed_now`, making "no digest" assertions deterministic.
    """

    def setUp(self):
        # Today at 09:00 UTC — deterministic reference clock for all tests.
        self.fixed_now = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        self.fixed_send_time = self.fixed_now.time()          # 09:00:00
        self.other_send_time = self.fixed_now.replace(hour=18).time()  # 18:00:00

        self.user = create_user("digest_user")
        schedule, _ = DigestSchedule.objects.get_or_create(user=self.user)
        schedule.send_time = self.fixed_send_time
        schedule.save(update_fields=["send_time"])

    def test_digest_created_for_unread_notifications(self):
        for i in range(3):
            Notification.objects.create(
                user=self.user,
                event_type=EventType.SYSTEM,
                title=f"Alert {i}",
                body=".",
            )

        result = send_daily_digests(_now=self.fixed_now)
        self.assertEqual(result["digests_sent"], 1)

        digest = Notification.objects.filter(
            user=self.user, event_type=EventType.DIGEST
        ).first()
        self.assertIsNotNone(digest)
        self.assertIn("3", digest.title)
        self.assertIn("Alert 0", digest.body)

    def test_digest_not_sent_when_no_unread(self):
        result = send_daily_digests(_now=self.fixed_now)
        self.assertEqual(result["digests_sent"], 0)
        self.assertFalse(
            Notification.objects.filter(
                user=self.user, event_type=EventType.DIGEST
            ).exists()
        )

    def test_digest_excludes_existing_digest_notifications(self):
        Notification.objects.create(
            user=self.user,
            event_type=EventType.DIGEST,
            title="Yesterday's digest",
            body=".",
        )
        result = send_daily_digests(_now=self.fixed_now)
        self.assertEqual(result["digests_sent"], 0)

    def test_schedule_last_sent_updated(self):
        Notification.objects.create(
            user=self.user, event_type=EventType.SYSTEM, title="X", body="."
        )
        send_daily_digests(_now=self.fixed_now)
        schedule = DigestSchedule.objects.get(user=self.user)
        self.assertIsNotNone(schedule.last_sent_at)

    # ── send_time filtering tests (regression for the "ignored send_time" bug) ──

    def test_digest_only_sent_to_users_whose_send_time_matches_now(self):
        """
        User A: send_time=09:00 (matches fixed_now). User B: send_time=18:00 (does not match).
        Only user A should receive a digest.
        """
        user_a = create_user("digest_time_a")
        user_b = create_user("digest_time_b")
        sched_a, _ = DigestSchedule.objects.get_or_create(user=user_a)
        sched_a.send_time = self.fixed_send_time
        sched_a.save(update_fields=["send_time"])
        sched_b, _ = DigestSchedule.objects.get_or_create(user=user_b)
        sched_b.send_time = self.other_send_time
        sched_b.save(update_fields=["send_time"])

        for user in (user_a, user_b):
            Notification.objects.create(
                user=user, event_type=EventType.SYSTEM, title="Alert", body="."
            )

        result = send_daily_digests(_now=self.fixed_now)

        # user_a matches 09:00 and has notifications → 1 digest
        # self.user (setUp) also matches 09:00 but has no notifications → 0 digests
        self.assertEqual(result["digests_sent"], 1)
        self.assertTrue(
            Notification.objects.filter(user=user_a, event_type=EventType.DIGEST).exists()
        )
        self.assertFalse(
            Notification.objects.filter(user=user_b, event_type=EventType.DIGEST).exists(),
            "Digest must not fire for user_b whose send_time (18:00) does not match 09:00",
        )

    def test_digest_not_sent_twice_same_day(self):
        """Running the task twice with the same _now sends only one digest."""
        Notification.objects.create(
            user=self.user, event_type=EventType.SYSTEM, title="Once", body="."
        )

        send_daily_digests(_now=self.fixed_now)
        send_daily_digests(_now=self.fixed_now)  # excluded by last_sent_at guard

        digest_count = Notification.objects.filter(
            user=self.user, event_type=EventType.DIGEST
        ).count()
        self.assertEqual(digest_count, 1, "Digest must not be sent twice in the same day")

    def test_user_with_non_matching_send_time_never_receives_digest(self):
        """A schedule whose send_time (18:00) does not match fixed_now (09:00) receives nothing."""
        user = create_user("digest_no_match")
        sched, _ = DigestSchedule.objects.get_or_create(user=user)
        sched.send_time = self.other_send_time
        sched.save(update_fields=["send_time"])
        Notification.objects.create(
            user=user, event_type=EventType.SYSTEM, title="Pending", body="."
        )

        send_daily_digests(_now=self.fixed_now)

        self.assertFalse(
            Notification.objects.filter(user=user, event_type=EventType.DIGEST).exists()
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
        from .models import OutboundChannel
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


# ─────────────────────────────────────────────────────────────────────────────
# 7.7 Digest Schedule API
# ─────────────────────────────────────────────────────────────────────────────

class DigestScheduleAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user("sched_user")
        token = login(self.client, "sched_user")
        auth(self.client, token)

    def test_get_creates_default_schedule(self):
        resp = self.client.get("/api/notifications/digest/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn(resp.json()["send_time"], ["18:00:00", "18:00"])

    def test_patch_updates_send_time(self):
        resp = self.client.patch(
            "/api/notifications/digest/",
            {"send_time": "09:00:00"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["send_time"], "09:00:00")

    def test_patch_idempotent(self):
        self.client.patch("/api/notifications/digest/", {"send_time": "07:30:00"})
        resp = self.client.get("/api/notifications/digest/")
        self.assertEqual(resp.json()["send_time"], "07:30:00")


# ─────────────────────────────────────────────────────────────────────────────
# 7.8 send_outbound_queued task
# ─────────────────────────────────────────────────────────────────────────────

class SendOutboundQueuedTaskTests(TestCase):
    """Tests for the send_outbound_queued Celery task (retry logic)."""

    def setUp(self):
        from .models import OutboundChannel
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
        from .models import SystemSettings
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
        from .models import OutboundChannel
        return OutboundMessage.objects.create(
            notification=notification,
            channel=OutboundChannel.SMTP,
            status=OutboundStatus.QUEUED,
        )

    def _age(self, obj, model_class, days):
        old_ts = timezone.now() - timedelta(days=days)
        model_class.objects.filter(pk=obj.pk).update(created_at=old_ts)

    def test_old_notifications_are_deleted(self):
        from .tasks import purge_old_notification_records
        old = self._make_notification()
        self._age(old, Notification, 366)

        result = purge_old_notification_records()

        self.assertFalse(Notification.objects.filter(pk=old.pk).exists())
        self.assertGreaterEqual(result["notifications_deleted"], 1)

    def test_recent_notifications_are_kept(self):
        from .tasks import purge_old_notification_records
        recent = self._make_notification()
        # created_at defaults to now — within retention window

        purge_old_notification_records()

        self.assertTrue(Notification.objects.filter(pk=recent.pk).exists())

    def test_old_outbound_messages_are_deleted(self):
        from .tasks import purge_old_notification_records
        notif = self._make_notification()
        msg = self._make_outbound(notif)
        self._age(msg, OutboundMessage, 366)

        result = purge_old_notification_records()

        self.assertFalse(OutboundMessage.objects.filter(pk=msg.pk).exists())
        self.assertGreaterEqual(result["outbound_deleted"], 1)

    def test_recent_outbound_messages_are_kept(self):
        from .tasks import purge_old_notification_records
        notif = self._make_notification()
        msg = self._make_outbound(notif)

        purge_old_notification_records()

        self.assertTrue(OutboundMessage.objects.filter(pk=msg.pk).exists())

    def test_purge_returns_cutoff_isoformat(self):
        from .tasks import purge_old_notification_records
        result = purge_old_notification_records()
        self.assertIn("cutoff", result)
        # Should be parseable as an ISO datetime
        from django.utils.dateparse import parse_datetime
        self.assertIsNotNone(parse_datetime(result["cutoff"]))


# ─────────────────────────────────────────────────────────────────────────────
# 7.8  System Settings API — /api/settings/ and /api/settings/test-smtp|sms/
# ─────────────────────────────────────────────────────────────────────────────

class SystemSettingsAPITests(TestCase):
    """
    Endpoint-contract tests for the admin-only settings endpoints.

    Covers:
      - 401 when unauthenticated
      - 403 when authenticated as non-admin
      - 200 GET returns current settings
      - 200 PATCH updates valid fields
      - 400 PATCH rejects non-local SMS gateway URL
      - 400 POST /test-smtp/ when no SMTP host configured
      - 400 POST /test-sms/ when no SMS URL configured
    """

    SETTINGS_URL     = "/api/settings/"
    TEST_SMTP_URL    = "/api/settings/test-smtp/"
    TEST_SMS_URL     = "/api/settings/test-sms/"

    def setUp(self):
        self.admin    = create_user("settings_admin",   role=Role.ADMIN)
        self.analyst  = create_user("settings_analyst", role=Role.PROCUREMENT_ANALYST)
        self.manager  = create_user("settings_manager", role=Role.INVENTORY_MANAGER)
        self.client   = APIClient()

    # ── Authentication guard ──────────────────────────────────────────────────

    def test_get_settings_unauthenticated_returns_401(self):
        resp = self.client.get(self.SETTINGS_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_settings_unauthenticated_returns_401(self):
        resp = self.client.patch(self.SETTINGS_URL, {}, content_type="application/json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_test_smtp_unauthenticated_returns_401(self):
        resp = self.client.post(self.TEST_SMTP_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_test_sms_unauthenticated_returns_401(self):
        resp = self.client.post(self.TEST_SMS_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Role guard ────────────────────────────────────────────────────────────

    def test_get_settings_analyst_returns_403(self):
        auth(self.client, login(self.client, "settings_analyst"))
        resp = self.client.get(self.SETTINGS_URL)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_settings_manager_returns_403(self):
        auth(self.client, login(self.client, "settings_manager"))
        resp = self.client.get(self.SETTINGS_URL)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_test_smtp_non_admin_returns_403(self):
        auth(self.client, login(self.client, "settings_analyst"))
        resp = self.client.post(self.TEST_SMTP_URL)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_test_sms_non_admin_returns_403(self):
        auth(self.client, login(self.client, "settings_analyst"))
        resp = self.client.post(self.TEST_SMS_URL)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── GET 200 ───────────────────────────────────────────────────────────────

    def test_get_settings_admin_returns_200_with_expected_fields(self):
        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.get(self.SETTINGS_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        for field in ("smtp_host", "smtp_port", "smtp_use_tls", "sms_gateway_url"):
            self.assertIn(field, data)

    # ── PATCH 200 ─────────────────────────────────────────────────────────────

    def test_patch_smtp_host_admin_returns_200_and_persists(self):
        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.patch(
            self.SETTINGS_URL,
            {"smtp_host": "mailrelay.local", "smtp_port": 587},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["smtp_host"], "mailrelay.local")
        self.assertEqual(data["smtp_port"], 587)

        # Verify DB persistence
        from .models import SystemSettings
        cfg = SystemSettings.get()
        self.assertEqual(cfg.smtp_host, "mailrelay.local")

    def test_patch_local_sms_url_returns_200(self):
        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.patch(
            self.SETTINGS_URL,
            {"sms_gateway_url": "http://192.168.1.10:8080/sms"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["sms_gateway_url"], "http://192.168.1.10:8080/sms")

    # ── PATCH 400 — validation ────────────────────────────────────────────────

    def test_patch_external_sms_url_returns_400(self):
        """Offline policy: public internet SMS gateway URLs must be rejected."""
        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.patch(
            self.SETTINGS_URL,
            {"sms_gateway_url": "https://api.twilio.com/sms"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sms_gateway_url", resp.json().get("details", resp.json()))

    def test_patch_invalid_scheme_sms_url_returns_400(self):
        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.patch(
            self.SETTINGS_URL,
            {"sms_gateway_url": "ftp://192.168.1.5/sms"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sms_gateway_url", resp.json().get("details", resp.json()))

    def test_patch_external_smtp_host_returns_400(self):
        """Offline policy: public internet SMTP hosts must be rejected."""
        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.patch(
            self.SETTINGS_URL,
            {"smtp_host": "smtp.gmail.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("smtp_host", resp.json().get("details", resp.json()))

    def test_patch_external_smtp_ip_returns_400(self):
        """Offline policy: public IP as SMTP host must be rejected."""
        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.patch(
            self.SETTINGS_URL,
            {"smtp_host": "8.8.8.8"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("smtp_host", resp.json().get("details", resp.json()))

    # ── /test-smtp/ — 400 when unconfigured ──────────────────────────────────

    def test_test_smtp_returns_400_when_smtp_host_not_set(self):
        from .models import SystemSettings
        cfg = SystemSettings.get()
        cfg.smtp_host = ""
        cfg.save()

        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.post(self.TEST_SMTP_URL)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", resp.json())

    def test_test_smtp_returns_400_on_connection_failure(self):
        """With an unreachable host, test-smtp should return 400 with a message."""
        from .models import SystemSettings
        cfg = SystemSettings.get()
        cfg.smtp_host = "127.0.0.1"
        cfg.smtp_port = 1   # nothing listening here
        cfg.save()

        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.post(self.TEST_SMTP_URL)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", resp.json())

    # ── /test-sms/ — 400 when unconfigured ───────────────────────────────────

    def test_test_sms_returns_400_when_sms_url_not_set(self):
        from .models import SystemSettings
        cfg = SystemSettings.get()
        cfg.sms_gateway_url = ""
        cfg.save()

        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.post(self.TEST_SMS_URL)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", resp.json())

    def test_test_sms_returns_400_on_connection_failure(self):
        """With an unreachable local gateway, test-sms should return 400."""
        from .models import SystemSettings
        cfg = SystemSettings.get()
        cfg.sms_gateway_url = "http://127.0.0.1:1/sms"  # nothing listening
        cfg.save()

        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.post(self.TEST_SMS_URL)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", resp.json())


# ─────────────────────────────────────────────────────────────────────────────
# 7.9  DigestSchedule signal — auto-provision on user creation
# ─────────────────────────────────────────────────────────────────────────────

class DigestScheduleSignalTests(TestCase):
    """
    Regression tests for notifications/signals.py.

    The post_save signal must create exactly one DigestSchedule (with the
    default 18:00 send time) whenever a new User is created.  Subsequent
    saves of the same user must not create extra rows.
    """

    def test_new_user_creates_exactly_one_digest_schedule(self):
        user = create_user("signal_test_user")
        count = DigestSchedule.objects.filter(user=user).count()
        self.assertEqual(count, 1, "Expected exactly one DigestSchedule after user creation")

    def test_digest_schedule_defaults_to_1800(self):
        from datetime import time
        user = create_user("signal_default_time_user")
        schedule = DigestSchedule.objects.get(user=user)
        self.assertEqual(schedule.send_time, time(18, 0))

    def test_user_update_does_not_create_extra_schedule(self):
        user = create_user("signal_update_user")
        user.first_name = "Updated"
        user.save()
        count = DigestSchedule.objects.filter(user=user).count()
        self.assertEqual(count, 1, "User update must not create an additional DigestSchedule")
