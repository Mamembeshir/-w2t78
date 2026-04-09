"""
tests/crawling/test_canary.py — Canary monitoring, routing, and checkpoint tests.

Covers auto-rollback, auto-promote, routing by canary_pct, and checkpoint
persistence.
"""
from datetime import timedelta

from django.test import LiveServerTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User
from crawling.models import (
    CrawlRequestLog,
    CrawlRuleVersion,
    CrawlSource,
    CrawlTask,
    CrawlTaskStatus,
)
from crawling.tasks import _promote_canary, _rollback_canary, monitor_canary_versions
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
# 6.7 Canary Monitoring
# ─────────────────────────────────────────────────────────────────────────────

class CanaryMonitoringTests(TestCase):
    def setUp(self):
        self.source = make_source("CANARY_SRC")
        self.rv_active = make_rule_version(self.source, version_number=1, is_active=True)
        self.rv_canary = make_rule_version(self.source, version_number=2, is_active=False)
        self.rv_canary.is_canary = True
        self.rv_canary.canary_started_at = timezone.now()
        self.rv_canary.save()

    def _make_task(self, status_val, rule_version=None):
        rv = rule_version or self.rv_canary
        fp = _compute_fingerprint(f"http://c.local/p{CrawlTask.objects.count()}", {})
        return CrawlTask.objects.create(
            source=self.source, rule_version=rv,
            fingerprint=fp, url="http://c.local/products",
            status=status_val,
        )

    def test_auto_rollback_on_high_error_rate(self):
        # 3 completed, 3 failed → 50% error rate > 2%
        for _ in range(3):
            self._make_task(CrawlTaskStatus.COMPLETED)
        for _ in range(3):
            self._make_task(CrawlTaskStatus.FAILED)
        result = monitor_canary_versions()
        self.assertEqual(result["rolled_back"], 1)
        self.rv_canary.refresh_from_db()
        self.assertFalse(self.rv_canary.is_canary)

    def test_auto_promote_after_30_minutes_clean(self):
        # 10 completed, 0 failed → 0% error rate, window elapsed
        for _ in range(10):
            self._make_task(CrawlTaskStatus.COMPLETED)
        self.rv_canary.canary_started_at = timezone.now() - timedelta(minutes=31)
        self.rv_canary.save()
        result = monitor_canary_versions()
        self.assertEqual(result["promoted"], 1)
        self.rv_canary.refresh_from_db()
        self.assertFalse(self.rv_canary.is_canary)
        self.assertTrue(self.rv_canary.is_active)

    def test_no_action_within_window_low_errors(self):
        # 10 completed, 0 failed → 0% error rate, window NOT elapsed
        for _ in range(10):
            self._make_task(CrawlTaskStatus.COMPLETED)
        result = monitor_canary_versions()
        self.assertEqual(result["rolled_back"], 0)
        self.assertEqual(result["promoted"], 0)

    def test_debug_log_endpoint(self):
        client = APIClient()
        analyst = create_user("dbg_analyst", Role.PROCUREMENT_ANALYST)
        token = login(client, "dbg_analyst")
        auth(client, token)
        task = self._make_task(CrawlTaskStatus.COMPLETED)
        CrawlRequestLog.objects.create(
            task=task, request_url="http://c.local/products",
            request_headers='{"User-Agent": "Test/1.0"}',
            response_status=200, response_snippet="OK", duration_ms=50,
        )
        resp = client.get(f"/api/crawl/sources/{self.source.pk}/debug-log/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()), 1)


# ─────────────────────────────────────────────────────────────────────────────
# 8.4 Checkpoint Persistence
# ─────────────────────────────────────────────────────────────────────────────

class CheckpointTests(LiveServerTestCase):
    """
    Verify the worker resumes from checkpoint_page instead of page 1.

    Uses Django's LiveServerTestCase so the worker can make real HTTP requests
    to the local health endpoint — no mocking.
    """

    def setUp(self):
        self.source = make_source("CKPT_SRC", rate_limit=60)
        self.source.crawl_delay_seconds = 0
        self.source.save()
        # Rule version with page_number pagination, 3 pages
        self.rv = CrawlRuleVersion.objects.create(
            source=self.source,
            version_number=1,
            url_pattern=f"{{live_server}}/api/health/",
            version_note="checkpoint test",
            is_active=True,
            pagination_config={
                "type": "page_number",
                "param": "page",
                "start": 1,
                "max_pages": 3,
            },
        )

    def _make_task(self, checkpoint_page=0):
        fp = _compute_fingerprint(
            f"{self.live_server_url}/api/health/",
            {"checkpoint": checkpoint_page},
        )
        return CrawlTask.objects.create(
            source=self.source,
            rule_version=self.rv,
            fingerprint=fp,
            url=f"{self.live_server_url}/api/health/",
            status=CrawlTaskStatus.PENDING,
            checkpoint_page=checkpoint_page,
        )

    def test_worker_completes_from_zero_checkpoint(self):
        """A fresh task (checkpoint_page=0) completes successfully."""
        from crawling.worker import execute_crawl_task
        task = self._make_task(checkpoint_page=0)
        result = execute_crawl_task(task.pk)
        task.refresh_from_db()
        self.assertTrue(result.get("completed"))
        self.assertEqual(task.status, CrawlTaskStatus.COMPLETED)

    def test_worker_resumes_from_nonzero_checkpoint(self):
        """
        A task with checkpoint_page=2 should start from page 2 (not page 1).
        With max_pages=3 and start_page=max(2,1)=2, pages [2,3,4] are processed.
        Task completes successfully and creates one log entry per page.
        """
        from crawling.worker import execute_crawl_task
        task = self._make_task(checkpoint_page=2)
        result = execute_crawl_task(task.pk)
        task.refresh_from_db()
        self.assertTrue(result.get("completed"), f"Worker failed: {result}")
        self.assertEqual(task.status, CrawlTaskStatus.COMPLETED)
        # With checkpoint_page=2 and max_pages=3, the loop runs pages [2,3,4]
        # → 3 requests → 3 log entries
        logs = CrawlRequestLog.objects.filter(task=task)
        self.assertEqual(logs.count(), 3)
        # checkpoint_page should remain at 2 (checkpointing saves only every 100 pages;
        # total loop is only 3 iterations so no checkpoint write happens)
        self.assertEqual(task.checkpoint_page, 2)


# ─────────────────────────────────────────────────────────────────────────────
# 8.4 Canary Version Routing (5% probability)
# ─────────────────────────────────────────────────────────────────────────────

class CanaryRoutingTests(TestCase):
    """
    Verify _pick_rule_version() routes to the canary version according to
    canary_pct without mocking the random module.
    """

    def setUp(self):
        self.source = make_source("ROUTE_SRC")
        self.rv_active = make_rule_version(self.source, version_number=1, is_active=True)
        self.rv_canary = CrawlRuleVersion.objects.create(
            source=self.source,
            version_number=2,
            url_pattern="http://route.test/products",
            version_note="canary routing test",
            is_active=False,
            is_canary=True,
            canary_pct=100,  # 100% → always picks canary
            canary_started_at=timezone.now(),
        )

    def _make_task(self):
        fp = _compute_fingerprint(f"http://route.test/{CrawlTask.objects.count()}", {})
        return CrawlTask.objects.create(
            source=self.source,
            rule_version=self.rv_active,
            fingerprint=fp,
            url="http://route.test/products",
            status=CrawlTaskStatus.PENDING,
        )

    def test_canary_100pct_always_routes_to_canary(self):
        """With canary_pct=100 every task picks the canary version."""
        from crawling.worker import _pick_rule_version
        for _ in range(10):
            task = self._make_task()
            picked = _pick_rule_version(task)
            self.assertEqual(
                picked.pk, self.rv_canary.pk,
                "Expected canary version to be picked with canary_pct=100",
            )

    def test_canary_0pct_never_routes_to_canary(self):
        """With canary_pct=0 the active version is always used."""
        from crawling.worker import _pick_rule_version
        self.rv_canary.canary_pct = 0
        self.rv_canary.save()
        for _ in range(10):
            task = self._make_task()
            picked = _pick_rule_version(task)
            self.assertEqual(
                picked.pk, self.rv_active.pk,
                "Expected active version to be picked with canary_pct=0",
            )

    def test_no_canary_returns_active_version(self):
        """Without a canary version active the worker always picks rv_active."""
        from crawling.worker import _pick_rule_version
        self.rv_canary.is_canary = False
        self.rv_canary.save()
        task = self._make_task()
        picked = _pick_rule_version(task)
        self.assertEqual(picked.pk, self.rv_active.pk)
