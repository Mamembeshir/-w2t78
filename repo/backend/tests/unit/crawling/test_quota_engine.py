"""
tests/crawling/test_quota_engine.py — Quota engine tests.

Covers quota acquisition, release, window reset, auto-release task,
and the quota API endpoint.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User
from crawling.models import CrawlRuleVersion, CrawlSource, SourceQuota
from crawling.quota import acquire_quota, release_quota


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
# 6.4 Quota Engine
# ─────────────────────────────────────────────────────────────────────────────

class QuotaEngineTests(TestCase):
    def setUp(self):
        self.source = make_source("QUOTA_SRC", rate_limit=3)

    def test_acquire_within_limit(self):
        self.assertTrue(acquire_quota(self.source))
        self.assertTrue(acquire_quota(self.source))
        self.assertTrue(acquire_quota(self.source))

    def test_acquire_exceeds_limit(self):
        acquire_quota(self.source)
        acquire_quota(self.source)
        acquire_quota(self.source)
        self.assertFalse(acquire_quota(self.source))  # 4th slot denied

    def test_release_decrements_count(self):
        acquire_quota(self.source)
        acquire_quota(self.source)
        acquire_quota(self.source)
        release_quota(self.source)
        self.assertTrue(acquire_quota(self.source))  # slot freed

    def test_window_reset_allows_new_slots(self):
        acquire_quota(self.source)
        acquire_quota(self.source)
        acquire_quota(self.source)
        # Manually expire the window
        quota = SourceQuota.objects.get(source=self.source)
        quota.window_start = timezone.now() - timedelta(seconds=61)
        quota.save()
        self.assertTrue(acquire_quota(self.source))  # window reset

    def test_held_quota_auto_release_task(self):
        from crawling.tasks import release_held_quotas
        acquire_quota(self.source)
        # Expire held_until
        quota = SourceQuota.objects.get(source=self.source)
        quota.held_until = timezone.now() - timedelta(seconds=1)
        quota.save()
        result = release_held_quotas()
        self.assertGreaterEqual(result["quotas_released"], 1)

    def test_quota_endpoint(self):
        client = APIClient()
        analyst = create_user("quota_analyst", Role.PROCUREMENT_ANALYST)
        token = login(client, "quota_analyst")
        auth(client, token)
        acquire_quota(self.source)
        resp = client.get(f"/api/crawl/sources/{self.source.pk}/quota/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["current_count"], 1)
