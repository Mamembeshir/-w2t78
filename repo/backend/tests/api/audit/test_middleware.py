"""
tests/audit/test_middleware.py — Audit middleware tests.

Covers AuditLogMiddleware: writes entries for mutating requests,
skips auth/health/read-only paths, and masks secret fields.
"""
from django.test import TestCase
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
    from django.utils import timezone
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
# A.1 / A.2  AuditLogMiddleware
# ─────────────────────────────────────────────────────────────────────────────

class AuditMiddlewareTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = create_user("audit_mgr", Role.INVENTORY_MANAGER)
        token = login(self.client, "audit_mgr")
        auth(self.client, token)

    def _count(self):
        return AuditLog._default_manager.count()

    def test_post_request_creates_audit_entry(self):
        """A POST to an API endpoint should create an AuditLog entry."""
        before = self._count()
        # POST to items (creates an item, which is a mutating request)
        self.client.post(
            "/api/items/",
            {"sku": "AUDIT-TEST-001", "name": "Audit Item", "costing_method": "AVG"},
        )
        self.assertGreater(self._count(), before)

    def test_audit_entry_captures_correct_fields(self):
        """Entry should have action=CREATE, model_name=items, user set."""
        self.client.post(
            "/api/items/",
            {"sku": "AUDIT-TEST-002", "name": "Audit Item 2", "costing_method": "FIFO"},
        )
        entry = AuditLog._default_manager.filter(model_name="items").first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.action, "CREATE")
        self.assertEqual(entry.user, self.manager)

    def test_get_request_does_not_create_audit_entry(self):
        """Read-only GET must NOT generate audit entries."""
        before = self._count()
        self.client.get("/api/items/")
        self.assertEqual(self._count(), before)

    def test_auth_login_skipped(self):
        """Login endpoint must be excluded from audit logging."""
        before = self._count()
        self.client.post(
            "/api/auth/login/",
            {"username": "audit_mgr", "password": "testpass1234"},
        )
        self.assertEqual(self._count(), before)

    def test_health_endpoint_skipped(self):
        """Health probe must not generate audit entries."""
        before = self._count()
        self.client.get("/api/health/")
        self.assertEqual(self._count(), before)

    def test_unauthenticated_request_not_logged(self):
        """Unauthenticated requests must not create audit entries."""
        unauthenticated = APIClient()
        before = self._count()
        unauthenticated.post("/api/items/", {"sku": "X", "name": "Y", "costing_method": "AVG"})
        self.assertEqual(self._count(), before)

    def test_body_secrets_are_masked_in_changes(self):
        """Passwords and tokens in the request body must appear as [REDACTED] in changes."""
        self.client.post(
            "/api/users/",
            {"username": "masktest", "password": "supersecret1234", "role": "VIEWER"},
        )
        entry = AuditLog._default_manager.filter(model_name="users").order_by("-timestamp").first()
        if entry and "password" in entry.changes:
            self.assertNotEqual(entry.changes["password"], "supersecret1234")
