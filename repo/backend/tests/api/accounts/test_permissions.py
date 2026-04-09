"""
tests/accounts/test_permissions.py — Permission class tests.

Covers role-based access control enforcement on the /api/users/ endpoint.
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username, password, role=Role.INVENTORY_MANAGER, **kwargs):
    return User.objects.create_user(username=username, password=password, role=role, **kwargs)


def login(client, username, password):
    return client.post("/api/auth/login/", {"username": username, "password": password})


# ─────────────────────────────────────────────────────────────────────────────
# 3.2 — Permission Classes
# ─────────────────────────────────────────────────────────────────────────────

class PermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = create_user("admin1", "adminpass123", role=Role.ADMIN)
        self.inv_mgr = create_user("inv1", "invpass1234", role=Role.INVENTORY_MANAGER)
        self.proc_analyst = create_user("proc1", "procpass123", role=Role.PROCUREMENT_ANALYST)

    def _auth_client(self, username, password):
        c = APIClient()
        resp = login(c, username, password)
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.json()['access']}")
        return c

    def test_unauthenticated_cannot_access_users(self):
        resp = self.client.get("/api/users/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_access_users(self):
        c = self._auth_client("admin1", "adminpass123")
        resp = c.get("/api/users/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_inventory_manager_cannot_access_users(self):
        c = self._auth_client("inv1", "invpass1234")
        resp = c.get("/api/users/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_procurement_analyst_cannot_access_users(self):
        c = self._auth_client("proc1", "procpass123")
        resp = c.get("/api/users/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
