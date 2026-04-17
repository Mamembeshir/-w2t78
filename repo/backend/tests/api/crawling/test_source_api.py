"""
tests/crawling/test_source_api.py — Crawl source API tests.

Covers CRUD operations on /api/crawl/sources/ including role-based access.
"""
from django.test import TestCase
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
# 6.1 Source API
# ─────────────────────────────────────────────────────────────────────────────

class SourceAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.analyst = create_user("src_analyst", Role.PROCUREMENT_ANALYST)
        self.inv = create_user("src_inv", Role.INVENTORY_MANAGER)
        self.token = login(self.client, "src_analyst")
        self.inv_token = login(self.client, "src_inv")

    def test_list_sources_authenticated(self):
        make_source("SRC01")
        auth(self.client, self.token)
        resp = self.client.get("/api/crawl/sources/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.json()["count"], 1)

    def test_create_source_analyst(self):
        auth(self.client, self.token)
        resp = self.client.post("/api/crawl/sources/", {
            "name": "New Source", "base_url": "http://example.local",
            "rate_limit_rpm": 30, "crawl_delay_seconds": 2,
            "user_agents": ["Agent/1"],
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.json()["name"], "New Source")

    def test_create_source_inventory_manager_forbidden(self):
        auth(self.client, self.inv_token)
        resp = self.client.post("/api/crawl/sources/", {
            "name": "X", "base_url": "http://x.local",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_source(self):
        src = make_source("UPD01")
        auth(self.client, self.token)
        resp = self.client.patch(f"/api/crawl/sources/{src.pk}/", {"rate_limit_rpm": 30})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["rate_limit_rpm"], 30)

    def test_source_detail_shows_active_rule_version(self):
        src = make_source("DET01")
        rv = make_rule_version(src, is_active=True)
        auth(self.client, self.token)
        resp = self.client.get(f"/api/crawl/sources/{src.pk}/")
        self.assertEqual(resp.json()["active_rule_version"], rv.pk)

    def test_full_update_source(self):
        src = make_source("PUT_SRC")
        auth(self.client, self.token)
        resp = self.client.put(f"/api/crawl/sources/{src.pk}/", {
            "name": "PUT_SRC",
            "base_url": "http://updated.local",
            "rate_limit_rpm": 120,
            "crawl_delay_seconds": 5,
            "user_agents": ["UpdatedAgent/2.0"],
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["base_url"], "http://updated.local")
        self.assertEqual(resp.json()["rate_limit_rpm"], 120)

    def test_full_update_source_inventory_manager_forbidden(self):
        src = make_source("PUT_FORBID")
        auth(self.client, self.inv_token)
        resp = self.client.put(f"/api/crawl/sources/{src.pk}/", {
            "name": "PUT_FORBID",
            "base_url": "http://x.local",
            "rate_limit_rpm": 10,
            "crawl_delay_seconds": 1,
            "user_agents": ["X/1"],
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Quota endpoint ─────────────────────────────────────────────────────────

    def test_quota_returns_zero_when_no_acquisitions(self):
        """GET /api/crawl/sources/:id/quota/ returns current_count=0 for a fresh source."""
        src = make_source("QUOTA_FRESH")
        auth(self.client, self.token)
        resp = self.client.get(f"/api/crawl/sources/{src.pk}/quota/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["current_count"], 0)
        self.assertEqual(data["rpm_limit"], 60)

    def test_quota_reflects_acquisitions(self):
        """GET .../quota/ current_count increments after quota acquisitions."""
        from crawling.quota import acquire_quota
        src = make_source("QUOTA_ACQ")
        acquire_quota(src)
        acquire_quota(src)
        auth(self.client, self.token)
        resp = self.client.get(f"/api/crawl/sources/{src.pk}/quota/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["current_count"], 2)

    def test_quota_forbidden_for_inventory_manager(self):
        """INVENTORY_MANAGER gets 403 on the quota endpoint."""
        src = make_source("QUOTA_403")
        auth(self.client, self.inv_token)
        resp = self.client.get(f"/api/crawl/sources/{src.pk}/quota/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
