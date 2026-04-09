"""
tests/crawling/test_rule_version_api.py — Rule version API tests.

Covers create, activate, canary, rollback, and list operations on rule versions.
"""
import json

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
