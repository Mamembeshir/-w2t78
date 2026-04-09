"""
tests/notifications/test_inbox_api.py — Inbox API tests.

Covers notification listing, filtering, mark-read, mark-all-read, unread count,
and IDOR guard for cross-user read attempts.
"""
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from notifications.models import EventType, Notification


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
