"""
tests/accounts/test_auth_api.py — Authentication API tests.

Covers login, token refresh, logout, and /me endpoint.
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
