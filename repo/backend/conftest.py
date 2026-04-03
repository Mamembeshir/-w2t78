"""
conftest.py — pytest-django configuration and shared factory fixtures.

All tests use a real MySQL test database spun up by pytest-django.
No mocking — APIClient calls hit real views and real DB.
"""
import pytest
from rest_framework.test import APIClient

from accounts.models import User, Role


# ── User factories ────────────────────────────────────────────────────────────

def make_user(username: str, role: str, password: str = "TestPass123!") -> User:
    """Create a real User in the test DB."""
    return User.objects.create_user(username=username, password=password, role=role)


def get_token(client: APIClient, username: str, password: str = "TestPass123!") -> str:
    """Obtain a JWT access token via the real login endpoint."""
    resp = client.post(
        "/api/auth/login/",
        {"username": username, "password": password},
        format="json",
    )
    assert resp.status_code == 200, f"Login failed for {username}: {resp.json()}"
    return resp.json()["access"]


def auth_client(role: str, username: str | None = None) -> APIClient:
    """Return an authenticated APIClient for the given role."""
    username = username or f"fixture_{role.lower()}"
    client = APIClient()
    user = make_user(username, role)
    token = get_token(client, username)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client, user


# ── Pytest fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def admin_client():
    client, user = auth_client(Role.ADMIN, "cfg_admin")
    return client


@pytest.fixture
def inventory_client():
    client, user = auth_client(Role.INVENTORY_MANAGER, "cfg_inv")
    return client


@pytest.fixture
def analyst_client():
    client, user = auth_client(Role.PROCUREMENT_ANALYST, "cfg_analyst")
    return client


@pytest.fixture
def anon_client():
    return APIClient()
