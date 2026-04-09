"""
tests/notifications/test_signals.py — DigestSchedule signal tests.

Covers auto-provisioning of DigestSchedule on user creation and
verifies that subsequent user saves do not create extra rows.
"""
from django.test import TestCase

from accounts.models import Role, User
from notifications.models import DigestSchedule


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username, role=Role.PROCUREMENT_ANALYST):
    return User.objects.create_user(
        username=username, password="testpass1234", role=role
    )


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
