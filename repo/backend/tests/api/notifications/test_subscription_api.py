"""
tests/notifications/test_subscription_api.py — Subscription API tests.

Covers list, create, upsert/reactivate, delete, user scoping, and IDOR guard.
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from notifications.models import EventType, NotificationSubscription


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
