"""
tests/accounts/test_audit_middleware.py — Audit middleware tests (accounts perspective).

Covers audit log creation triggered by user management operations,
password masking, and exclusion of auth/unauthenticated requests.
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from audit.models import AuditLog


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username, password, role=Role.INVENTORY_MANAGER, **kwargs):
    return User.objects.create_user(username=username, password=password, role=role, **kwargs)


def login(client, username, password):
    return client.post("/api/auth/login/", {"username": username, "password": password})


# ─────────────────────────────────────────────────────────────────────────────
# 3.3 — Audit Middleware
# ─────────────────────────────────────────────────────────────────────────────

class AuditMiddlewareTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = create_user("audit_admin", "auditpass123", role=Role.ADMIN)
        resp = login(self.client, "audit_admin", "auditpass123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.json()['access']}")

    def test_create_user_creates_audit_log_entry(self):
        before_count = AuditLog.objects.count()
        self.client.post("/api/users/", {
            "username": "auditeduser",
            "password": "auditedpass1",
            "role": Role.INVENTORY_MANAGER,
        })
        self.assertEqual(AuditLog.objects.count(), before_count + 1)
        entry = AuditLog.objects.latest("timestamp")
        self.assertEqual(entry.action, "CREATE")
        self.assertEqual(entry.model_name, "users")
        self.assertEqual(entry.user, self.admin)

    def test_patch_user_creates_update_audit_log(self):
        user = create_user("patchaudit", "patchaudit1p")
        before_count = AuditLog.objects.count()
        self.client.patch(f"/api/users/{user.pk}/", {"role": Role.PROCUREMENT_ANALYST})
        self.assertEqual(AuditLog.objects.count(), before_count + 1)
        entry = AuditLog.objects.latest("timestamp")
        self.assertEqual(entry.action, "UPDATE")

    def test_audit_log_masks_password_in_changes(self):
        """Password values in the request body must be [REDACTED] in the audit log."""
        self.client.post("/api/users/", {
            "username": "maskeduser",
            "password": "supersecret123",
            "role": Role.INVENTORY_MANAGER,
        })
        entry = AuditLog.objects.latest("timestamp")
        changes_str = str(entry.changes)
        self.assertNotIn("supersecret123", changes_str)

    def test_auth_login_not_audited(self):
        """Login requests (POST /api/auth/login/) must NOT create an audit log entry."""
        before_count = AuditLog.objects.count()
        login(self.client, "audit_admin", "auditpass123")
        self.assertEqual(AuditLog.objects.count(), before_count)

    def test_unauthenticated_request_not_audited(self):
        """Requests without a valid JWT must NOT create an audit log entry."""
        anon_client = APIClient()
        before_count = AuditLog.objects.count()
        anon_client.post("/api/users/", {"username": "anon", "password": "anonpass1"})
        self.assertEqual(AuditLog.objects.count(), before_count)
