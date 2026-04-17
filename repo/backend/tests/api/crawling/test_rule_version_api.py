"""
tests/crawling/test_rule_version_api.py — Rule version API tests.

Covers create, activate, canary, rollback, list, and test-probe operations
on rule versions.
"""
import json
from unittest.mock import MagicMock, patch

import requests as req_lib
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from crawling.models import CrawlRuleVersion, CrawlSource


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


def make_source(name="TestSource", rate_limit=60):
    return CrawlSource.objects.create(
        name=name,
        base_url="http://example.local",
        rate_limit_rpm=rate_limit,
        crawl_delay_seconds=0,
        user_agents=["TestAgent/1.0"],
    )


def make_rule_version(source, version_number=1, is_active=True, note="Initial version"):
    return CrawlRuleVersion.objects.create(
        source=source,
        version_number=version_number,
        version_note=note,
        url_pattern="http://example.local/products",
        parameters={},
        pagination_config={},
        is_active=is_active,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6.2 Rule Version API
# ─────────────────────────────────────────────────────────────────────────────

class RuleVersionAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.analyst = create_user("rv_analyst", Role.PROCUREMENT_ANALYST)
        self.token = login(self.client, "rv_analyst")
        auth(self.client, self.token)
        self.source = make_source("RV_SOURCE")

    def test_create_rule_version_auto_increments(self):
        make_rule_version(self.source, version_number=1)
        resp = self.client.post(f"/api/crawl/sources/{self.source.pk}/rule-versions/", {
            "version_note": "v2 improvements",
            "url_pattern": "http://example.local/items",
            "parameters": {},
            "pagination_config": {},
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()["version_number"], 2)

    def test_create_version_note_required(self):
        resp = self.client.post(f"/api/crawl/sources/{self.source.pk}/rule-versions/", {
            "url_pattern": "http://example.local/items",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_activate_version(self):
        rv1 = make_rule_version(self.source, version_number=1, is_active=True)
        rv2 = make_rule_version(self.source, version_number=2, is_active=False)
        resp = self.client.post(f"/api/crawl/rule-versions/{rv2.pk}/activate/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rv1.refresh_from_db()
        rv2.refresh_from_db()
        self.assertFalse(rv1.is_active)
        self.assertTrue(rv2.is_active)

    def test_start_canary(self):
        rv_active = make_rule_version(self.source, version_number=1, is_active=True)
        rv_new = make_rule_version(self.source, version_number=2, is_active=False)
        resp = self.client.post(f"/api/crawl/rule-versions/{rv_new.pk}/canary/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rv_new.refresh_from_db()
        self.assertTrue(rv_new.is_canary)
        self.assertIsNotNone(rv_new.canary_started_at)

    def test_canary_requires_existing_active_version(self):
        rv_new = make_rule_version(self.source, version_number=1, is_active=False)
        resp = self.client.post(f"/api/crawl/rule-versions/{rv_new.pk}/canary/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rollback_canary(self):
        rv_active = make_rule_version(self.source, version_number=1, is_active=True)
        rv_canary = make_rule_version(self.source, version_number=2, is_active=False)
        rv_canary.is_canary = True
        rv_canary.canary_started_at = timezone.now()
        rv_canary.save()
        resp = self.client.post(f"/api/crawl/rule-versions/{rv_canary.pk}/rollback/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rv_canary.refresh_from_db()
        self.assertFalse(rv_canary.is_canary)
        self.assertFalse(rv_canary.is_active)

    def test_request_headers_masked_in_response(self):
        rv = make_rule_version(self.source, version_number=1)
        rv.request_headers = json.dumps({"Authorization": "Bearer secret123", "X-Custom": "value"})
        rv.save()
        resp = self.client.get(f"/api/crawl/rule-versions/{rv.pk}/")
        masked = resp.json()["request_headers_masked"]
        self.assertEqual(masked.get("Authorization"), "[REDACTED]")
        self.assertEqual(masked.get("X-Custom"), "[REDACTED]")

    def test_list_rule_versions_for_source(self):
        make_rule_version(self.source, version_number=1)
        make_rule_version(self.source, version_number=2, is_active=False)
        resp = self.client.get(f"/api/crawl/sources/{self.source.pk}/rule-versions/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["count"], 2)

    # ── POST .../test/ — dry-run probe ────────────────────────────────────────

    def test_rule_test_returns_probe_result_on_success(self):
        """POST .../test/ fires the probe and returns status_code, duration_ms, snippet."""
        rv = make_rule_version(self.source, version_number=1)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>OK</html>"
        with patch("requests.get", return_value=mock_resp):
            resp = self.client.post(f"/api/crawl/rule-versions/{rv.pk}/test/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["status_code"], 200)
        self.assertIsNotNone(data["duration_ms"])
        self.assertIsNone(data["error"])
        self.assertIn("snippet", data)

    def test_rule_test_snippet_contains_response_body(self):
        """Snippet field echoes the first 500 chars of the response body."""
        rv = make_rule_version(self.source, version_number=1)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "Hello from supplier"
        with patch("requests.get", return_value=mock_resp):
            resp = self.client.post(f"/api/crawl/rule-versions/{rv.pk}/test/")
        self.assertIn("Hello from supplier", resp.json()["snippet"])

    def test_rule_test_handles_network_error(self):
        """POST .../test/ returns error field and null status_code on network failure."""
        rv = make_rule_version(self.source, version_number=1)
        with patch("requests.get", side_effect=req_lib.ConnectionError("Connection refused")):
            resp = self.client.post(f"/api/crawl/rule-versions/{rv.pk}/test/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIsNone(data["status_code"])
        self.assertIsNotNone(data["error"])
        self.assertIn("Connection refused", data["error"])

    def test_rule_test_duration_ms_is_non_negative(self):
        """duration_ms is always a non-negative integer."""
        rv = make_rule_version(self.source, version_number=1)
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Not Found"
        with patch("requests.get", return_value=mock_resp):
            resp = self.client.post(f"/api/crawl/rule-versions/{rv.pk}/test/")
        self.assertGreaterEqual(resp.json()["duration_ms"], 0)

    def test_rule_test_forbidden_for_inventory_manager(self):
        """INVENTORY_MANAGER gets 403 on the test endpoint."""
        rv = make_rule_version(self.source, version_number=1)
        inv = create_user("rv_test_inv", Role.INVENTORY_MANAGER)
        inv_token = login(self.client, "rv_test_inv")
        auth(self.client, inv_token)
        resp = self.client.post(f"/api/crawl/rule-versions/{rv.pk}/test/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_rule_test_unauthenticated_returns_401(self):
        """Unauthenticated requests to .../test/ receive 401."""
        rv = make_rule_version(self.source, version_number=1)
        self.client.credentials()  # clear token
        resp = self.client.post(f"/api/crawl/rule-versions/{rv.pk}/test/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
