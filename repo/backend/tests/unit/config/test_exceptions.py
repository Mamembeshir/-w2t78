"""
tests/unit/config/test_exceptions.py

Tests for the custom DRF exception handler (config/exceptions.py).

Strategy: exercise the handler via real API endpoints so the full
middleware + DRF dispatch chain runs, then assert the response JSON
always conforms to { code, message, details }.

We also call the handler directly with synthetic DRF Response objects
to cover edge-case branches (list errors, plain string data, None response).
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.test import APIClient

from accounts.models import Role, User
from config.exceptions import custom_exception_handler


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username, role=Role.PROCUREMENT_ANALYST):
    return User.objects.create_user(username=username, password="testpass1234", role=role)


def login(client, username):
    resp = client.post("/api/auth/login/", {"username": username, "password": "testpass1234"})
    return resp.json()["access"]


def auth(client, token):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


# ─────────────────────────────────────────────────────────────────────────────
# Integration: response shape via real endpoints
# ─────────────────────────────────────────────────────────────────────────────

class ExceptionHandlerShapeTests(TestCase):
    """Every error response must be { code, message, details }."""

    def setUp(self):
        self.client = APIClient()

    def _assert_shape(self, resp):
        data = resp.json()
        self.assertIn("code", data, f"Missing 'code' in {data}")
        self.assertIn("message", data, f"Missing 'message' in {data}")
        self.assertIn("details", data, f"Missing 'details' in {data}")

    def test_401_shape(self):
        resp = self.client.get("/api/items/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self._assert_shape(resp)

    def test_401_code_is_unauthorized(self):
        resp = self.client.get("/api/items/")
        self.assertEqual(resp.json()["code"], "unauthorized")

    def test_404_shape(self):
        user = create_user("exc_404")
        token = login(self.client, "exc_404")
        auth(self.client, token)
        resp = self.client.get("/api/items/99999/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self._assert_shape(resp)

    def test_404_code_is_not_found(self):
        user = create_user("exc_404b")
        token = login(self.client, "exc_404b")
        auth(self.client, token)
        resp = self.client.get("/api/items/99999/")
        self.assertEqual(resp.json()["code"], "not_found")

    def test_403_shape(self):
        """Inventory manager hitting crawling endpoint → 403."""
        inv = User.objects.create_user(username="exc_inv", password="testpass1234", role=Role.INVENTORY_MANAGER)
        token = login(self.client, "exc_inv")
        auth(self.client, token)
        resp = self.client.get("/api/crawl/sources/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self._assert_shape(resp)

    def test_403_code_is_forbidden(self):
        User.objects.create_user(username="exc_inv2", password="testpass1234", role=Role.INVENTORY_MANAGER)
        token = login(self.client, "exc_inv2")
        auth(self.client, token)
        resp = self.client.get("/api/crawl/sources/")
        self.assertEqual(resp.json()["code"], "forbidden")

    def test_400_validation_shape(self):
        # Use INVENTORY_MANAGER — the role that has write access to /api/items/
        User.objects.create_user(username="exc_val", password="testpass1234", role=Role.INVENTORY_MANAGER)
        token = login(self.client, "exc_val")
        auth(self.client, token)
        # POST without required fields → 400
        resp = self.client.post("/api/items/", {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self._assert_shape(resp)

    def test_400_code_is_bad_request(self):
        User.objects.create_user(username="exc_val2", password="testpass1234", role=Role.INVENTORY_MANAGER)
        token = login(self.client, "exc_val2")
        auth(self.client, token)
        resp = self.client.post("/api/items/", {})
        self.assertEqual(resp.json()["code"], "bad_request")


# ─────────────────────────────────────────────────────────────────────────────
# Unit: handler called directly with synthetic exceptions
# ─────────────────────────────────────────────────────────────────────────────

class ExceptionHandlerUnitTests(TestCase):
    """Test the handler function directly for branch coverage."""

    def _ctx(self):
        return {"view": MagicMock()}

    def test_returns_none_for_unhandled_exceptions(self):
        """Non-DRF exceptions: handler must log and return 500."""
        exc = RuntimeError("boom")
        with patch("config.exceptions.exception_handler", return_value=None):
            with patch("config.exceptions.logger") as mock_log:
                resp = custom_exception_handler(exc, self._ctx())
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.data["code"], "internal_server_error")
        mock_log.exception.assert_called_once()

    def test_dict_with_detail_key(self):
        exc = NotFound("Resource not found")
        resp = custom_exception_handler(exc, self._ctx())
        self.assertIsNotNone(resp)
        self.assertEqual(resp.data["code"], "not_found")
        self.assertIsInstance(resp.data["message"], str)
        self.assertIn("details", resp.data)

    def test_dict_without_detail_uses_status_code_fallback(self):
        exc = PermissionDenied()
        resp = custom_exception_handler(exc, self._ctx())
        self.assertIsNotNone(resp)
        self.assertEqual(resp.data["code"], "forbidden")

    def test_list_error_data_is_joined(self):
        """DRF can return a list for non-field errors; handler joins them."""
        exc = ValidationError(["Error one", "Error two"])
        resp = custom_exception_handler(exc, self._ctx())
        self.assertIsNotNone(resp)
        self.assertIn("Error one", resp.data["message"])
        self.assertIn("Error two", resp.data["message"])
        self.assertEqual(resp.data["details"], {})

    def test_validation_error_field_errors_in_details(self):
        """Field-level validation errors appear in details, not in message."""
        exc = ValidationError({"sku": ["This field is required."]})
        resp = custom_exception_handler(exc, self._ctx())
        self.assertIsNotNone(resp)
        self.assertIn("sku", resp.data["details"])

    def test_unknown_status_code_falls_back_to_error(self):
        """Unmapped status codes get a generic 'error' code string."""
        exc = AuthenticationFailed()
        # Patch the response to have a status code not in _STATUS_CODES
        with patch("config.exceptions.exception_handler") as mock_handler:
            fake_resp = MagicMock()
            fake_resp.status_code = 418  # I'm a teapot — not in the map
            fake_resp.data = {"detail": "I'm a teapot"}
            mock_handler.return_value = fake_resp
            resp = custom_exception_handler(exc, self._ctx())
        self.assertEqual(resp.data["code"], "error")
