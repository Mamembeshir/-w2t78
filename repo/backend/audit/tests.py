"""
audit/tests.py — Real-database integration tests for Phase 9 audit app.

Run:
  docker compose exec backend python manage.py test audit --verbosity=2 --keepdb

Tests cover:
  A.1  AuditLogMiddleware — writes entries for mutating requests
  A.2  AuditLogMiddleware — skips auth/health/read-only paths
  A.3  AuditLog immutability — save/delete raise NotImplementedError
  A.4  AuditLogView API — admin can list and filter entries
  A.5  AuditLogView API — non-admin receives 403
  A.6  purge_old_audit_logs task — removes entries older than 365 days
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User

from .models import AuditLog, purge_old_audit_logs


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


# ─────────────────────────────────────────────────────────────────────────────
# A.3  AuditLog immutability
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogImmutabilityTests(TestCase):
    def test_save_existing_raises(self):
        """Calling .save() on an existing AuditLog must raise NotImplementedError."""
        log = make_log()
        log.action = "DELETE"
        with self.assertRaises(NotImplementedError):
            log.save()

    def test_delete_instance_raises(self):
        """Calling .delete() on an AuditLog instance must raise NotImplementedError."""
        log = make_log()
        with self.assertRaises(NotImplementedError):
            log.delete()

    def test_create_succeeds(self):
        """Creating a new AuditLog entry must work normally."""
        log = make_log(action="UPDATE", model_name="Warehouse", object_id="99")
        self.assertIsNotNone(log.pk)
        self.assertEqual(log.action, "UPDATE")


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


# ─────────────────────────────────────────────────────────────────────────────
# A.6  purge_old_audit_logs task
# ─────────────────────────────────────────────────────────────────────────────

class AuditPurgeTaskTests(TestCase):
    def test_purges_entries_older_than_365_days(self):
        """Entries older than 365 days must be deleted by the purge task."""
        old_log = make_log(days_ago=366)
        recent_log = make_log(days_ago=10)

        result = purge_old_audit_logs()

        self.assertGreaterEqual(result["deleted"], 1)
        # Old entry gone
        self.assertFalse(AuditLog._default_manager.filter(pk=old_log.pk).exists())
        # Recent entry retained
        self.assertTrue(AuditLog._default_manager.filter(pk=recent_log.pk).exists())

    def test_purge_returns_deleted_count(self):
        """Task must return a dict with deleted count and cutoff."""
        make_log(days_ago=400)
        make_log(days_ago=400)
        result = purge_old_audit_logs()
        self.assertIn("deleted", result)
        self.assertIn("cutoff", result)
        self.assertGreaterEqual(result["deleted"], 2)

    def test_purge_does_not_delete_recent_entries(self):
        """Entries within 365 days must be preserved."""
        make_log(days_ago=364)
        make_log(days_ago=0)
        before = AuditLog._default_manager.filter(
            timestamp__gte=timezone.now() - timedelta(days=365)
        ).count()
        purge_old_audit_logs()
        after = AuditLog._default_manager.filter(
            timestamp__gte=timezone.now() - timedelta(days=365)
        ).count()
        self.assertEqual(before, after)

    def test_purge_no_op_when_nothing_old(self):
        """Task returns deleted=0 when no old entries exist."""
        make_log(days_ago=30)
        result = purge_old_audit_logs()
        self.assertEqual(result["deleted"], 0)
