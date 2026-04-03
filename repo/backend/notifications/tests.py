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
        """No SMTP_HOST or SMS_GATEWAY_URL → no OutboundMessage created."""
        subscribe(self.user1, EventType.CRAWL_TASK_FAILED)
        dispatch_event(
            EventType.CRAWL_TASK_FAILED,
            title="Failed",
            body="Test.",
        )
        # No gateway configured in test settings → no outbound messages
        self.assertEqual(OutboundMessage.objects.count(), 0)


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
        DigestSchedule.objects.create(user=self.user, send_time=self.fixed_send_time)

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
        DigestSchedule.objects.create(user=user_a, send_time=self.fixed_send_time)
        DigestSchedule.objects.create(user=user_b, send_time=self.other_send_time)

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
        DigestSchedule.objects.create(user=user, send_time=self.other_send_time)
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
        self.assertEqual(result["sent"], 0)

    def test_queued_smtp_not_sent_when_no_smtp_host(self):
        """With no SMTP_HOST, queued SMTP messages remain untouched."""
        self._make_queued(self.OutboundChannel.SMTP)
        result = send_outbound_queued()
        self.assertEqual(result["sent"], 0)
        # Status must still be QUEUED
        self.assertEqual(
            OutboundMessage.objects.filter(status=OutboundStatus.QUEUED).count(), 1
        )

    def test_queued_sms_not_sent_when_no_sms_gateway(self):
        """With no SMS_GATEWAY_URL, queued SMS messages remain untouched."""
        self._make_queued(self.OutboundChannel.SMS)
        result = send_outbound_queued()
        self.assertEqual(result["sent"], 0)
        self.assertEqual(
            OutboundMessage.objects.filter(status=OutboundStatus.QUEUED).count(), 1
        )

    def test_already_sent_messages_are_not_retried(self):
        """Messages in SENT status are not processed by the retry task."""
        msg = self._make_queued()
        msg.status = OutboundStatus.SENT
        msg.save()

        result = send_outbound_queued()
        self.assertEqual(result["sent"], 0)

    def test_already_failed_messages_are_not_retried(self):
        """Messages in FAILED status are not processed by the retry task."""
        msg = self._make_queued()
        msg.status = OutboundStatus.FAILED
        msg.save()

        result = send_outbound_queued()
        self.assertEqual(result["sent"], 0)

    def test_queued_smtp_attempted_when_smtp_host_set(self):
        """When SMTP_HOST is set, the task attempts delivery (will fail → FAILED status)."""
        from django.test import override_settings
        self.user.email = "test@example.local"
        self.user.save()
        msg = self._make_queued(self.OutboundChannel.SMTP)

        # With a bogus SMTP host the connection will fail gracefully (→ FAILED)
        with override_settings(SMTP_HOST="localhost", SMTP_PORT=1):
            result = send_outbound_queued()

        self.assertEqual(result["sent"], 1)  # task attempted it
        msg.refresh_from_db()
        # Delivery failed → status is FAILED (not QUEUED)
        self.assertEqual(msg.status, OutboundStatus.FAILED)
        self.assertTrue(len(msg.error) > 0)
