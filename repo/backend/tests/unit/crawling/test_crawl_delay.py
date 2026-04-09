"""
tests/crawling/test_crawl_delay.py — Crawl delay field and behavior tests.

Covers honor_local_crawl_delay model field defaults, API exposure,
and worker timing behavior.
"""
from django.test import LiveServerTestCase, TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from crawling.models import CrawlRuleVersion, CrawlSource, CrawlTask, CrawlTaskStatus
from crawling.views import _compute_fingerprint


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
# 6.8  honor_local_crawl_delay — field default and worker branch (CLAUDE.md §9)
# ─────────────────────────────────────────────────────────────────────────────

class CrawlDelayFieldTests(TestCase):
    """Model and API contract tests for honor_local_crawl_delay."""

    def setUp(self):
        self.client = APIClient()
        self.analyst = create_user("delay_analyst", Role.PROCUREMENT_ANALYST)
        self.token = login(self.client, "delay_analyst")

    def test_honor_local_crawl_delay_defaults_to_true(self):
        """New CrawlSource must default honor_local_crawl_delay to True (CLAUDE.md §9)."""
        source = make_source("DELAY_DEFAULT_SRC")
        self.assertTrue(source.honor_local_crawl_delay)

    def test_honor_false_persists_to_db(self):
        source = CrawlSource.objects.create(
            name="DELAY_FALSE_SRC",
            base_url="http://delay.local",
            honor_local_crawl_delay=False,
            user_agents=[],
        )
        source.refresh_from_db()
        self.assertFalse(source.honor_local_crawl_delay)

    def test_api_exposes_honor_local_crawl_delay_field(self):
        """GET /api/crawl/sources/ response must include honor_local_crawl_delay."""
        make_source("DELAY_API_SRC")
        auth(self.client, self.token)
        resp = self.client.get("/api/crawl/sources/")
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertTrue(len(results) > 0)
        self.assertIn("honor_local_crawl_delay", results[0])

    def test_api_can_set_honor_false_on_create(self):
        """POST /api/crawl/sources/ should accept honor_local_crawl_delay=false."""
        auth(self.client, self.token)
        resp = self.client.post("/api/crawl/sources/", {
            "name": "DELAY_CREATE_FALSE",
            "base_url": "http://delay-create.local",
            "honor_local_crawl_delay": False,
            "user_agents": [],
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.json()["honor_local_crawl_delay"])


class CrawlDelayBehaviorTests(LiveServerTestCase):
    """
    Worker integration tests for honor_local_crawl_delay.

    Uses a 2-page pagination config so the delay condition (page > start_page)
    can fire.  crawl_delay_seconds=1 is large enough to measure reliably.

    - honor=False: 2-page crawl completes in well under 1 s (no sleep).
    - honor=True:  2-page crawl takes >= 1 s (one inter-page sleep).
    """

    def _make_source(self, name, honor):
        return CrawlSource.objects.create(
            name=name,
            base_url=self.live_server_url,
            rate_limit_rpm=600,
            crawl_delay_seconds=1,
            honor_local_crawl_delay=honor,
            user_agents=["TestAgent/1.0"],
        )

    def _make_two_page_rv(self, source):
        return CrawlRuleVersion.objects.create(
            source=source,
            version_number=1,
            url_pattern=f"{self.live_server_url}/api/health/",
            parameters={},
            pagination_config={
                "type": "page_number",
                "param": "page",
                "max_pages": 2,
            },
            is_active=True,
        )

    def _make_task(self, source, rv):
        url = f"{self.live_server_url}/api/health/"
        fp = _compute_fingerprint(url, {})
        return CrawlTask.objects.create(
            source=source,
            rule_version=rv,
            fingerprint=fp,
            url=url,
            status=CrawlTaskStatus.PENDING,
        )

    def test_delay_skipped_when_honor_false(self):
        """With honor_local_crawl_delay=False, inter-page sleep is not called."""
        import time as _time
        from crawling.worker import execute_crawl_task

        source = self._make_source("DELAY_SKIP_SRC", honor=False)
        rv = self._make_two_page_rv(source)
        task = self._make_task(source, rv)

        start = _time.monotonic()
        execute_crawl_task(task.pk)
        elapsed = _time.monotonic() - start

        task.refresh_from_db()
        self.assertEqual(task.status, CrawlTaskStatus.COMPLETED)
        # No sleep: 2 real HTTP requests to localhost should finish well under 1 s
        self.assertLess(elapsed, 0.8,
            f"Expected < 0.8 s with honor=False but took {elapsed:.2f} s")

    def test_delay_applied_when_honor_true(self):
        """With honor_local_crawl_delay=True, inter-page sleep of 1 s fires once."""
        import time as _time
        from crawling.worker import execute_crawl_task

        source = self._make_source("DELAY_APPLY_SRC", honor=True)
        rv = self._make_two_page_rv(source)
        task = self._make_task(source, rv)

        start = _time.monotonic()
        execute_crawl_task(task.pk)
        elapsed = _time.monotonic() - start

        task.refresh_from_db()
        self.assertEqual(task.status, CrawlTaskStatus.COMPLETED)
        # One inter-page sleep of 1 s must be present
        self.assertGreaterEqual(elapsed, 1.0,
            f"Expected >= 1.0 s with honor=True but took {elapsed:.2f} s")
