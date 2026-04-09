"""
tests/notifications/test_digest_task.py — Digest task tests.

Covers daily digest creation for unread notifications, send_time filtering,
idempotency, and last_sent_at tracking.
"""
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User
from notifications.models import DigestSchedule, EventType, Notification
from notifications.tasks import send_daily_digests


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
