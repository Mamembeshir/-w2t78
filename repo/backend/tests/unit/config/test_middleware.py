"""
tests/unit/config/test_middleware.py

Tests for SecurityHeadersMiddleware and RequestIDMiddleware.

Both middleware classes are registered in settings.MIDDLEWARE, so every
request through the Django test client exercises them.  We verify header
presence and value correctness by hitting a cheap, always-available endpoint
(/api/health/).
"""
import uuid

from django.test import TestCase, override_settings


class SecurityHeadersMiddlewareTests(TestCase):
    """Verify that SecurityHeadersMiddleware injects all required headers."""

    def _get(self):
        return self.client.get("/api/health/")

    def test_x_content_type_options_is_nosniff(self):
        resp = self._get()
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")

    def test_x_frame_options_is_deny(self):
        resp = self._get()
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")

    def test_referrer_policy_is_same_origin(self):
        resp = self._get()
        self.assertEqual(resp.headers.get("Referrer-Policy"), "same-origin")

    def test_content_security_policy_is_present(self):
        resp = self._get()
        self.assertIn("Content-Security-Policy", resp.headers)

    @override_settings(CSP_HEADER="default-src 'self'; img-src *")
    def test_custom_csp_header_from_settings(self):
        """CSP value should reflect whatever is in settings.CSP_HEADER."""
        resp = self._get()
        self.assertEqual(
            resp.headers.get("Content-Security-Policy"),
            "default-src 'self'; img-src *",
        )

    def test_security_headers_present_on_404(self):
        """Headers must appear on all responses, including error pages."""
        resp = self.client.get("/api/nonexistent-route-xyz/")
        self.assertIn("X-Content-Type-Options", resp.headers)
        self.assertIn("X-Frame-Options", resp.headers)


class RequestIDMiddlewareTests(TestCase):
    """Verify that RequestIDMiddleware attaches / propagates X-Request-ID."""

    def test_response_has_request_id_header(self):
        resp = self.client.get("/api/health/")
        self.assertIn("X-Request-ID", resp.headers)

    def test_generated_request_id_is_valid_uuid(self):
        resp = self.client.get("/api/health/")
        request_id = resp.headers.get("X-Request-ID", "")
        try:
            uuid.UUID(request_id)
        except ValueError:
            self.fail(f"X-Request-ID is not a valid UUID: {request_id!r}")

    def test_incoming_request_id_is_echoed_back(self):
        """When the client sends X-Request-ID, the same value is echoed."""
        client_id = "test-correlation-id-abc123"
        resp = self.client.get("/api/health/", HTTP_X_REQUEST_ID=client_id)
        self.assertEqual(resp.headers.get("X-Request-ID"), client_id)

    def test_missing_incoming_id_generates_new_uuid(self):
        """When no X-Request-ID is sent, a fresh UUID is generated."""
        resp = self.client.get("/api/health/")
        generated = resp.headers.get("X-Request-ID", "")
        self.assertTrue(len(generated) > 0)
        # Must be parseable as UUID (will raise if not)
        uuid.UUID(generated)

    def test_request_id_present_on_error_responses(self):
        """X-Request-ID must appear on all responses, not just 200s."""
        resp = self.client.get("/api/nonexistent-route-xyz/")
        self.assertIn("X-Request-ID", resp.headers)
