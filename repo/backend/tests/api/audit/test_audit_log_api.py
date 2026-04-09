"""
tests/audit/test_api.py — Audit log API tests.

Covers the /api/audit/ endpoint: admin access, filtering by action/model/user/date,
ordering, and entry field presence.
"""
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from audit.models import AuditLog


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username, role=Role.INVENTORY_MANAGER, password="testpass1234"):
    return User.objects.create_user(username=username, password=password, role=role)


def login(client, username, password="testpass1234"):
    resp = client.post("/api/auth/login/", {"username": username, "password": password})
    return resp.json()["access"]


def auth(client, token):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def make_log(user=None, action="CREATE", model_name="Item", object_id="1", days_ago=0):
    from datetime import timedelta
    log = AuditLog._default_manager.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=object_id,
        changes={"field": ["old", "new"]},
    )
    if days_ago:
        # Backdate the timestamp directly via queryset update (bypasses immutability guard)
        AuditLog._default_manager.filter(pk=log.pk).update(
            timestamp=timezone.now() - timedelta(days=days_ago)
        )
    return log


# ─────────────────────────────────────────────────────────────────────────────
# A.4 / A.5  AuditLogView API
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = create_user("audit_admin", Role.ADMIN)
        self.manager = create_user("audit_mgr2", Role.INVENTORY_MANAGER)
        token = login(self.client, "audit_admin")
        auth(self.client, token)

        # Seed some log entries
        make_log(user=self.admin, action="CREATE", model_name="Item", object_id="1")
        make_log(user=self.manager, action="UPDATE", model_name="Warehouse", object_id="2")
        make_log(user=self.admin, action="DELETE", model_name="Item", object_id="3")

    def test_admin_can_list_audit_entries(self):
        resp = self.client.get("/api/audit/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.json()["count"], 3)

    def test_non_admin_is_forbidden(self):
        client2 = APIClient()
        token = login(client2, "audit_mgr2")
        auth(client2, token)
        resp = client2.get("/api/audit/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_is_401(self):
        resp = APIClient().get("/api/audit/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_by_action(self):
        resp = self.client.get("/api/audit/?action=DELETE")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for entry in resp.json()["results"]:
            self.assertEqual(entry["action"], "DELETE")

    def test_filter_by_model(self):
        resp = self.client.get("/api/audit/?model=Item")
        for entry in resp.json()["results"]:
            self.assertIn("Item", entry["model_name"])

    def test_filter_by_user_id(self):
        resp = self.client.get(f"/api/audit/?user_id={self.admin.pk}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for entry in resp.json()["results"]:
            self.assertEqual(entry["user"], "audit_admin")

    def test_filter_by_date_range(self):
        today = timezone.now().date().isoformat()
        resp = self.client.get(f"/api/audit/?from_date={today}&to_date={today}")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.json()["count"], 3)

    def test_entries_ordered_newest_first(self):
        resp = self.client.get("/api/audit/")
        results = resp.json()["results"]
        if len(results) > 1:
            timestamps = [r["timestamp"] for r in results]
            self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_changes_field_present(self):
        """Each entry must expose a changes dict."""
        resp = self.client.get("/api/audit/")
        for entry in resp.json()["results"]:
            self.assertIn("changes", entry)
