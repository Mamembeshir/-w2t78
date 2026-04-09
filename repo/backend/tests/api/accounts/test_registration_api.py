"""
tests/accounts/test_registration_api.py — Registration API tests.

Covers the /api/auth/register/ endpoint, including the disabled-by-default gate
and all functional validation cases when REGISTRATION_OPEN=True.
"""
from django.test import TestCase, override_settings
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
