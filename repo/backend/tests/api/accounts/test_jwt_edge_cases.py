"""
tests/accounts/test_jwt_edge_cases.py — JWT edge case tests.

Coverage for JWT edge cases flagged in the security audit: tampered tokens,
malformed bearer values, empty bearer, and blacklisted refresh tokens.
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
# JWT edge cases — tampered / malformed tokens
# ─────────────────────────────────────────────────────────────────────────────

class JWTEdgeCaseTests(TestCase):
    """
    Coverage for JWT edge cases flagged in the security audit.

    simplejwt validates signature and expiry on every request; these tests
    confirm that invalid bearer values are always rejected with 401 before
    any business logic runs.
    """

    def setUp(self):
        self.client = APIClient()
        create_user("jwt_edge_user", "jwt_edge_pass1")
        resp = login(self.client, "jwt_edge_user", "jwt_edge_pass1")
        self.tokens = resp.json()

    def test_tampered_access_token_returns_401(self):
        """Modifying the JWT signature must be rejected with 401."""
        token = self.tokens["access"]
        # Replace the entire signature segment (3rd part) with a bogus value
        parts = token.split(".")
        parts[2] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        tampered = ".".join(parts)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tampered}")
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_malformed_bearer_value_returns_401(self):
        """A non-JWT string in the Authorization header must return 401."""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not.a.jwt.at.all")
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_bearer_returns_401(self):
        """'Authorization: Bearer ' with no token must return 401."""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer ")
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_blacklisted_refresh_cannot_issue_new_access(self):
        """After logout the refresh token must be blacklisted — re-use returns 401."""
        # Authenticate then log out to blacklist the refresh token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.tokens['access']}")
        self.client.post("/api/auth/logout/", {"refresh": self.tokens["refresh"]})
        # Fresh client with no auth — attempt to reuse the blacklisted refresh
        fresh = APIClient()
        resp = fresh.post("/api/auth/refresh/", {"refresh": self.tokens["refresh"]})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
