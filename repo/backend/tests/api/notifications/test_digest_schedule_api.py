"""
tests/notifications/test_digest_schedule_api.py — Digest schedule API tests.

Covers GET and PATCH for /api/notifications/digest/.
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User


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
