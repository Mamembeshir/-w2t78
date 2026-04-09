"""
tests/notifications/test_settings_api.py — System settings API tests.

Covers admin-only settings endpoints: GET /api/settings/, PATCH /api/settings/,
POST /api/settings/test-smtp/, POST /api/settings/test-sms/.
Includes authentication guards, role guards, validation, and connection failure handling.
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_user(username, role=Role.PROCUREMENT_ANALYST):
    return User.objects.create_user(
        username=username, password="testpass1234", role=role
    )


def login(client, username):
    resp = client.post(
        "/api/auth/login/", {"username": username, "password": "testpass1234"}
    )
    return resp.json()["access"]


def auth(client, token):
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


# ─────────────────────────────────────────────────────────────────────────────
# 7.8  System Settings API — /api/settings/ and /api/settings/test-smtp|sms/
# ─────────────────────────────────────────────────────────────────────────────

class SystemSettingsAPITests(TestCase):
    """
    Endpoint-contract tests for the admin-only settings endpoints.

    Covers:
      - 401 when unauthenticated
      - 403 when authenticated as non-admin
      - 200 GET returns current settings
      - 200 PATCH updates valid fields
      - 400 PATCH rejects non-local SMS gateway URL
      - 400 POST /test-smtp/ when no SMTP host configured
      - 400 POST /test-sms/ when no SMS URL configured
    """

    SETTINGS_URL     = "/api/settings/"
    TEST_SMTP_URL    = "/api/settings/test-smtp/"
    TEST_SMS_URL     = "/api/settings/test-sms/"

    def setUp(self):
        self.admin    = create_user("settings_admin",   role=Role.ADMIN)
        self.analyst  = create_user("settings_analyst", role=Role.PROCUREMENT_ANALYST)
        self.manager  = create_user("settings_manager", role=Role.INVENTORY_MANAGER)
        self.client   = APIClient()

    # ── Authentication guard ──────────────────────────────────────────────────

    def test_get_settings_unauthenticated_returns_401(self):
        resp = self.client.get(self.SETTINGS_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_settings_unauthenticated_returns_401(self):
        resp = self.client.patch(self.SETTINGS_URL, {}, content_type="application/json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_test_smtp_unauthenticated_returns_401(self):
        resp = self.client.post(self.TEST_SMTP_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_test_sms_unauthenticated_returns_401(self):
        resp = self.client.post(self.TEST_SMS_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Role guard ────────────────────────────────────────────────────────────

    def test_get_settings_analyst_returns_403(self):
        auth(self.client, login(self.client, "settings_analyst"))
        resp = self.client.get(self.SETTINGS_URL)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_settings_manager_returns_403(self):
        auth(self.client, login(self.client, "settings_manager"))
        resp = self.client.get(self.SETTINGS_URL)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_test_smtp_non_admin_returns_403(self):
        auth(self.client, login(self.client, "settings_analyst"))
        resp = self.client.post(self.TEST_SMTP_URL)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_test_sms_non_admin_returns_403(self):
        auth(self.client, login(self.client, "settings_analyst"))
        resp = self.client.post(self.TEST_SMS_URL)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── GET 200 ───────────────────────────────────────────────────────────────

    def test_get_settings_admin_returns_200_with_expected_fields(self):
        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.get(self.SETTINGS_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        for field in ("smtp_host", "smtp_port", "smtp_use_tls", "sms_gateway_url"):
            self.assertIn(field, data)

    # ── PATCH 200 ─────────────────────────────────────────────────────────────

    def test_patch_smtp_host_admin_returns_200_and_persists(self):
        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.patch(
            self.SETTINGS_URL,
            {"smtp_host": "mailrelay.local", "smtp_port": 587},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["smtp_host"], "mailrelay.local")
        self.assertEqual(data["smtp_port"], 587)

        # Verify DB persistence
        from notifications.models import SystemSettings
        cfg = SystemSettings.get()
        self.assertEqual(cfg.smtp_host, "mailrelay.local")

    def test_patch_local_sms_url_returns_200(self):
        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.patch(
            self.SETTINGS_URL,
            {"sms_gateway_url": "http://192.168.1.10:8080/sms"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["sms_gateway_url"], "http://192.168.1.10:8080/sms")

    # ── PATCH 400 — validation ────────────────────────────────────────────────

    def test_patch_external_sms_url_returns_400(self):
        """Offline policy: public internet SMS gateway URLs must be rejected."""
        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.patch(
            self.SETTINGS_URL,
            {"sms_gateway_url": "https://api.twilio.com/sms"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sms_gateway_url", resp.json().get("details", resp.json()))

    def test_patch_invalid_scheme_sms_url_returns_400(self):
        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.patch(
            self.SETTINGS_URL,
            {"sms_gateway_url": "ftp://192.168.1.5/sms"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("sms_gateway_url", resp.json().get("details", resp.json()))

    def test_patch_external_smtp_host_returns_400(self):
        """Offline policy: public internet SMTP hosts must be rejected."""
        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.patch(
            self.SETTINGS_URL,
            {"smtp_host": "smtp.gmail.com"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("smtp_host", resp.json().get("details", resp.json()))

    def test_patch_external_smtp_ip_returns_400(self):
        """Offline policy: public IP as SMTP host must be rejected."""
        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.patch(
            self.SETTINGS_URL,
            {"smtp_host": "8.8.8.8"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("smtp_host", resp.json().get("details", resp.json()))

    # ── /test-smtp/ — 400 when unconfigured ──────────────────────────────────

    def test_test_smtp_returns_400_when_smtp_host_not_set(self):
        from notifications.models import SystemSettings
        cfg = SystemSettings.get()
        cfg.smtp_host = ""
        cfg.save()

        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.post(self.TEST_SMTP_URL)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", resp.json())

    def test_test_smtp_returns_400_on_connection_failure(self):
        """With an unreachable host, test-smtp should return 400 with a message."""
        from notifications.models import SystemSettings
        cfg = SystemSettings.get()
        cfg.smtp_host = "127.0.0.1"
        cfg.smtp_port = 1   # nothing listening here
        cfg.save()

        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.post(self.TEST_SMTP_URL)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", resp.json())

    # ── /test-sms/ — 400 when unconfigured ───────────────────────────────────

    def test_test_sms_returns_400_when_sms_url_not_set(self):
        from notifications.models import SystemSettings
        cfg = SystemSettings.get()
        cfg.sms_gateway_url = ""
        cfg.save()

        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.post(self.TEST_SMS_URL)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", resp.json())

    def test_test_sms_returns_400_on_connection_failure(self):
        """With an unreachable local gateway, test-sms should return 400."""
        from notifications.models import SystemSettings
        cfg = SystemSettings.get()
        cfg.sms_gateway_url = "http://127.0.0.1:1/sms"  # nothing listening
        cfg.save()

        auth(self.client, login(self.client, "settings_admin"))
        resp = self.client.post(self.TEST_SMS_URL)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", resp.json())
