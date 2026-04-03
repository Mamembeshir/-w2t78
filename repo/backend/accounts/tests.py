"""
accounts/tests.py — Real-database integration tests for Phase 3.

All tests use DRF's APIClient with the full Django request/response cycle
against the test database (warehouse_db_test).  No mocking of any kind.

Run:
  docker compose exec backend python manage.py test accounts --verbosity=2
"""
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from audit.models import AuditLog
from .models import Role, User


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username, password, role=Role.INVENTORY_MANAGER, **kwargs):
    return User.objects.create_user(username=username, password=password, role=role, **kwargs)


def login(client, username, password):
    return client.post("/api/auth/login/", {"username": username, "password": password})


# ─────────────────────────────────────────────────────────────────────────────
# 3.1 — Auth API
# ─────────────────────────────────────────────────────────────────────────────

class LoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user("alice", "alicepass123", role=Role.ADMIN)

    def test_login_valid_credentials_returns_tokens(self):
        resp = login(self.client, "alice", "alicepass123")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("access", data)
        self.assertIn("refresh", data)
        self.assertIn("user", data)
        self.assertEqual(data["user"]["username"], "alice")
        self.assertEqual(data["user"]["role"], Role.ADMIN)

    def test_login_wrong_password_returns_401(self):
        resp = login(self.client, "alice", "wrongpassword")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_unknown_user_returns_401(self):
        resp = login(self.client, "nobody", "whatever123")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_missing_fields_returns_401(self):
        resp = self.client.post("/api/auth/login/", {})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_inactive_user_returns_401(self):
        create_user("inactive_user", "pass1234567", is_active=False)
        resp = login(self.client, "inactive_user", "pass1234567")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_hashed_with_argon2(self):
        """Verify Argon2 is active — passwords must start with 'argon2$'."""
        self.assertTrue(
            self.user.password.startswith("argon2$"),
            f"Expected Argon2 hash, got: {self.user.password[:30]}",
        )


class RefreshTokenTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        create_user("bob", "bobpassword1")
        resp = login(self.client, "bob", "bobpassword1")
        self.tokens = resp.json()

    def test_refresh_returns_new_access_token(self):
        resp = self.client.post("/api/auth/refresh/", {"refresh": self.tokens["refresh"]})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("access", data)
        # New access token is different from the original
        self.assertNotEqual(data["access"], self.tokens["access"])

    def test_refresh_with_invalid_token_returns_401(self):
        resp = self.client.post("/api/auth/refresh/", {"refresh": "not.a.valid.token"})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        create_user("carol", "carolpass123")
        resp = login(self.client, "carol", "carolpass123")
        self.tokens = resp.json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.tokens['access']}")

    def test_logout_returns_204(self):
        resp = self.client.post("/api/auth/logout/", {"refresh": self.tokens["refresh"]})
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_refresh_after_logout_returns_401(self):
        self.client.post("/api/auth/logout/", {"refresh": self.tokens["refresh"]})
        # Clear auth header before trying to refresh
        self.client.credentials()
        resp = self.client.post("/api/auth/refresh/", {"refresh": self.tokens["refresh"]})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_unauthenticated_returns_401(self):
        self.client.credentials()  # clear token
        resp = self.client.post("/api/auth/logout/", {"refresh": self.tokens["refresh"]})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_idempotent_already_blacklisted(self):
        """Logging out twice should still return 204 (idempotent)."""
        self.client.post("/api/auth/logout/", {"refresh": self.tokens["refresh"]})
        # Re-login to get a fresh access token for second logout call
        resp = login(APIClient(), "carol", "carolpass123")
        fresh_access = resp.json()["access"]
        fresh_client = APIClient()
        fresh_client.credentials(HTTP_AUTHORIZATION=f"Bearer {fresh_access}")
        resp2 = fresh_client.post("/api/auth/logout/", {"refresh": self.tokens["refresh"]})
        self.assertEqual(resp2.status_code, status.HTTP_204_NO_CONTENT)


class MeViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        create_user("dave", "davepass1234", role=Role.PROCUREMENT_ANALYST, email="dave@example.com")
        resp = login(self.client, "dave", "davepass1234")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.json()['access']}")

    def test_me_returns_current_user(self):
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["username"], "dave")
        self.assertEqual(data["role"], Role.PROCUREMENT_ANALYST)
        self.assertEqual(data["email"], "dave@example.com")

    def test_me_unauthenticated_returns_401(self):
        self.client.credentials()
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ─────────────────────────────────────────────────────────────────────────────
# Registration — POST /api/auth/register/
# ─────────────────────────────────────────────────────────────────────────────

class RegistrationTests(TestCase):
    REGISTER_URL = "/api/auth/register/"

    def setUp(self):
        self.client = APIClient()

    def _register(self, **kwargs):
        payload = {"username": "newanalyst", "password": "Str0ng!Pass1", **kwargs}
        return self.client.post(self.REGISTER_URL, payload)

    # ── Gate: disabled by default ─────────────────────────────────────────────

    def test_register_disabled_by_default(self):
        """With no env override, registration returns 403."""
        resp = self._register()
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("disabled", resp.json()["detail"].lower())

    def test_register_disabled_returns_403_for_any_payload(self):
        """Even a valid payload must be blocked when disabled."""
        resp = self.client.post(self.REGISTER_URL, {
            "username": "would_be_user", "password": "Str0ng!Pass1",
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(username="would_be_user").exists())

    # ── Functional tests: only run when REGISTRATION_OPEN=True ───────────────

    @override_settings(REGISTRATION_OPEN=True)
    def test_register_returns_201(self):
        resp = self._register()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    @override_settings(REGISTRATION_OPEN=True)
    def test_register_creates_user_in_db(self):
        self._register(username="dbcheck_user")
        self.assertTrue(User.objects.filter(username="dbcheck_user").exists())

    @override_settings(REGISTRATION_OPEN=True)
    def test_register_role_is_always_analyst(self):
        """Client cannot escalate role via the registration payload."""
        resp = self._register(username="escalation_attempt", role=Role.ADMIN)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="escalation_attempt")
        self.assertEqual(user.role, Role.PROCUREMENT_ANALYST)

    @override_settings(REGISTRATION_OPEN=True)
    def test_register_response_contains_role(self):
        resp = self._register()
        self.assertEqual(resp.json()["role"], Role.PROCUREMENT_ANALYST)

    @override_settings(REGISTRATION_OPEN=True)
    def test_register_password_hashed_argon2(self):
        self._register(username="argon2reg")
        user = User.objects.get(username="argon2reg")
        self.assertTrue(
            user.password.startswith("argon2$"),
            f"Expected Argon2 hash, got: {user.password[:30]}",
        )

    @override_settings(REGISTRATION_OPEN=True)
    def test_register_duplicate_username_returns_400(self):
        self._register(username="dupeanalyst")
        resp = self._register(username="dupeanalyst")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(REGISTRATION_OPEN=True)
    def test_register_password_too_short_returns_400(self):
        """Password must be at least 10 characters (AUTH_PASSWORD_VALIDATORS)."""
        resp = self._register(password="short")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(REGISTRATION_OPEN=True)
    def test_register_missing_username_returns_400(self):
        resp = self.client.post(self.REGISTER_URL, {"password": "Str0ng!Pass1"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(REGISTRATION_OPEN=True)
    def test_register_missing_password_returns_400(self):
        resp = self.client.post(self.REGISTER_URL, {"username": "nopwduser"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(REGISTRATION_OPEN=True)
    def test_register_account_can_login_immediately(self):
        """End-to-end: register → login with the same credentials."""
        self._register(username="full_flow_user", password="Str0ng!Pass1")
        resp = login(self.client, "full_flow_user", "Str0ng!Pass1")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.json())

    @override_settings(REGISTRATION_OPEN=True)
    def test_register_account_has_analyst_dashboard_access(self):
        """Registered analyst can reach /api/auth/me/ and sees correct role."""
        self._register(username="me_analyst")
        resp = login(self.client, "me_analyst", "Str0ng!Pass1")
        token = resp.json()["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.json()["role"], Role.PROCUREMENT_ANALYST)


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


# ─────────────────────────────────────────────────────────────────────────────
# 3.4 — User Management API
# ─────────────────────────────────────────────────────────────────────────────

class UserManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = create_user("admin_mgr", "adminmgr123", role=Role.ADMIN)
        resp = login(self.client, "admin_mgr", "adminmgr123")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.json()['access']}")

    # ── List ─────────────────────────────────────────────────────────────────

    def test_list_users_returns_200(self):
        resp = self.client.get("/api/users/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        # DRF paginated response includes 'results'
        self.assertIn("results", data)

    def test_list_users_includes_created_user(self):
        create_user("listed_user", "listedpass1")
        resp = self.client.get("/api/users/")
        usernames = [u["username"] for u in resp.json()["results"]]
        self.assertIn("listed_user", usernames)

    # ── Create ───────────────────────────────────────────────────────────────

    def test_create_user_returns_201(self):
        resp = self.client.post("/api/users/", {
            "username": "newuser1",
            "password": "newpassword1",
            "role": Role.INVENTORY_MANAGER,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_create_user_password_not_in_response(self):
        resp = self.client.post("/api/users/", {
            "username": "newuser2",
            "password": "newpassword2",
            "role": Role.INVENTORY_MANAGER,
        })
        self.assertNotIn("password", resp.json())

    def test_create_user_password_hashed_argon2(self):
        self.client.post("/api/users/", {
            "username": "argon2user",
            "password": "argon2password",
            "role": Role.INVENTORY_MANAGER,
        })
        user = User.objects.get(username="argon2user")
        self.assertTrue(
            user.password.startswith("argon2$"),
            f"Expected Argon2 hash, got: {user.password[:30]}",
        )

    def test_create_user_without_password_returns_400(self):
        resp = self.client.post("/api/users/", {
            "username": "nopwduser",
            "role": Role.INVENTORY_MANAGER,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_user_duplicate_username_returns_400(self):
        create_user("dupeuser", "dupepass123")
        resp = self.client.post("/api/users/", {
            "username": "dupeuser",
            "password": "anotherpass1",
            "role": Role.INVENTORY_MANAGER,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Retrieve ─────────────────────────────────────────────────────────────

    def test_retrieve_user(self):
        user = create_user("retrieveme", "retrieve1pass")
        resp = self.client.get(f"/api/users/{user.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["username"], "retrieveme")

    # ── Update ───────────────────────────────────────────────────────────────

    def test_patch_user_role(self):
        user = create_user("patchme", "patchmepass1", role=Role.INVENTORY_MANAGER)
        resp = self.client.patch(f"/api/users/{user.pk}/", {"role": Role.PROCUREMENT_ANALYST})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["role"], Role.PROCUREMENT_ANALYST)
        user.refresh_from_db()
        self.assertEqual(user.role, Role.PROCUREMENT_ANALYST)

    def test_patch_user_deactivate(self):
        user = create_user("deactivateme", "deactivate1p")
        resp = self.client.patch(f"/api/users/{user.pk}/", {"is_active": False})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_put_ignores_password_field(self):
        """PUT with a 'password' field should not change the password (update() pops it)."""
        user = create_user("putpasstest", "original1pass", role=Role.INVENTORY_MANAGER)
        original_hash = user.password
        self.client.put(f"/api/users/{user.pk}/", {
            "username": "putpasstest",
            "role": Role.INVENTORY_MANAGER,
            "password": "shouldbeignored1",
        })
        user.refresh_from_db()
        self.assertEqual(user.password, original_hash)

    def test_delete_not_allowed(self):
        user = create_user("deleteme", "deleteme1pass")
        resp = self.client.delete(f"/api/users/{user.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # ── Reset Password ────────────────────────────────────────────────────────

    def test_reset_password_changes_password(self):
        user = create_user("resetpwd", "oldpassword1")
        resp = self.client.post(f"/api/users/{user.pk}/reset-password/", {"password": "brandnewpass1"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("brandnewpass1"))

    def test_reset_password_hashed_argon2(self):
        user = create_user("resetargon", "resetpass123")
        self.client.post(f"/api/users/{user.pk}/reset-password/", {"password": "freshhash1234"})
        user.refresh_from_db()
        self.assertTrue(user.password.startswith("argon2$"))

    def test_reset_password_too_short_returns_400(self):
        user = create_user("shortpwd", "initialpass1")
        resp = self.client.post(f"/api/users/{user.pk}/reset-password/", {"password": "short"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password_missing_field_returns_400(self):
        user = create_user("nopwd", "initialpass12")
        resp = self.client.post(f"/api/users/{user.pk}/reset-password/", {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


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
