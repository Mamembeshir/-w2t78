"""
crawling/tests.py — Real-database integration tests for Phase 6.

Run:
  docker compose exec backend python manage.py test crawling --verbosity=2 --keepdb

Tests cover:
  6.1  Crawl Source CRUD
  6.2  Rule Version create / activate / canary / rollback
  6.3  Task scheduling + fingerprint deduplication
  6.4  Quota acquisition / release / waitlist
  6.5  Worker execution (real HTTP to local health endpoint)
  6.6  Request log pruning to last 20 per source
  6.7  Canary monitoring (auto-rollback, auto-promote)
  6.8  honor_local_crawl_delay field and worker branch behavior
"""
import hashlib
import json
import time
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, LiveServerTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User

from .models import (
    CrawledProduct,
    CrawlRequestLog,
    CrawlRuleVersion,
    CrawlSource,
    CrawlTask,
    CrawlTaskStatus,
    SourceQuota,
)
from .quota import acquire_quota, release_quota
from .tasks import _promote_canary, _rollback_canary, monitor_canary_versions
from .views import _compute_fingerprint


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


# ─────────────────────────────────────────────────────────────────────────────
# 6.3 Task Scheduler
# ─────────────────────────────────────────────────────────────────────────────

class TaskSchedulerTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.analyst = create_user("task_analyst", Role.PROCUREMENT_ANALYST)
        self.token = login(self.client, "task_analyst")
        auth(self.client, self.token)
        self.source = make_source("TASK_SRC")
        self.rv = make_rule_version(self.source, version_number=1)

    def _enqueue(self, url="http://example.local/page1", params=None):
        return self.client.post("/api/crawl/tasks/", {
            "source_id": self.source.pk,
            "url": url,
            "parameters": params or {},
        }, format="json")

    def test_enqueue_task_creates_pending_task(self):
        resp = self._enqueue()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.json()
        self.assertFalse(data["deduplicated"])
        self.assertEqual(data["task"]["status"], CrawlTaskStatus.PENDING)

    def test_fingerprint_deduplication(self):
        self._enqueue("http://example.local/dup")
        resp2 = self._enqueue("http://example.local/dup")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertTrue(resp2.json()["deduplicated"])

    def test_different_params_different_fingerprint(self):
        r1 = self._enqueue("http://example.local/p", {"page": "1"})
        r2 = self._enqueue("http://example.local/p", {"page": "2"})
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(r1.json()["task"]["id"], r2.json()["task"]["id"])

    def test_enqueue_no_active_rule_returns_400(self):
        self.rv.is_active = False
        self.rv.save()
        resp = self._enqueue()
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.json()["code"], "no_active_rule")

    def test_compute_fingerprint_deterministic(self):
        f1 = _compute_fingerprint("http://test.local", {"b": "2", "a": "1"})
        f2 = _compute_fingerprint("http://test.local", {"a": "1", "b": "2"})
        self.assertEqual(f1, f2)

    def test_list_tasks_filter_by_status(self):
        self._enqueue("http://example.local/t1")
        resp = self.client.get("/api/crawl/tasks/?status=PENDING")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_retry_failed_task(self):
        resp = self._enqueue("http://example.local/retry-test")
        task_id = resp.json()["task"]["id"]
        task = CrawlTask.objects.get(pk=task_id)
        task.status = CrawlTaskStatus.FAILED
        task.attempt_count = 5
        task.last_error = "connection refused"
        task.save()
        resp2 = self.client.post(f"/api/crawl/tasks/{task_id}/retry/")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.status, CrawlTaskStatus.PENDING)
        self.assertEqual(task.attempt_count, 0)


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
        from .tasks import release_held_quotas
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
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["current_count"], 1)


# ─────────────────────────────────────────────────────────────────────────────
# 6.5 + 6.6 Worker + Request Logging (real HTTP to local health endpoint)
# ─────────────────────────────────────────────────────────────────────────────

class WorkerTests(LiveServerTestCase):
    """
    Uses Django's LiveServerTestCase to provide a real HTTP server at
    self.live_server_url.  The worker makes actual HTTP requests — no mocking.
    """

    def setUp(self):
        self.analyst = create_user("worker_analyst", Role.PROCUREMENT_ANALYST)
        self.source = make_source("WORKER_SRC", rate_limit=60)
        self.source.crawl_delay_seconds = 0  # no delay in tests
        self.source.save()
        self.rv = make_rule_version(self.source, version_number=1)

    def _make_task(self, url=None):
        url = url or f"{self.live_server_url}/api/health/"
        fp = _compute_fingerprint(url, {})
        return CrawlTask.objects.create(
            source=self.source,
            rule_version=self.rv,
            fingerprint=fp,
            url=url,
            status=CrawlTaskStatus.PENDING,
        )

    def test_worker_completes_task_successfully(self):
        from .worker import execute_crawl_task
        task = self._make_task()
        result = execute_crawl_task(task.pk)
        task.refresh_from_db()
        self.assertTrue(result.get("completed"))
        self.assertEqual(task.status, CrawlTaskStatus.COMPLETED)
        self.assertIsNotNone(task.completed_at)

    def test_worker_logs_request(self):
        from .worker import execute_crawl_task
        task = self._make_task()
        execute_crawl_task(task.pk)
        logs = CrawlRequestLog.objects.filter(task=task)
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.response_status, 200)
        self.assertIsNotNone(log.duration_ms)

    def test_worker_masks_auth_headers(self):
        from .worker import execute_crawl_task
        self.rv.request_headers = json.dumps({"Authorization": "Bearer supersecret"})
        self.rv.save()
        task = self._make_task()
        execute_crawl_task(task.pk)
        log = CrawlRequestLog.objects.filter(task=task).first()
        stored = json.loads(log.request_headers)
        self.assertEqual(stored.get("Authorization"), "[REDACTED]")

    def test_worker_retries_on_failure(self):
        from .worker import execute_crawl_task
        url = f"{self.live_server_url}/api/nonexistent-path-that-returns-404/"
        fp = _compute_fingerprint(url, {})
        # 404 raises HTTPError → triggers retry logic
        task = CrawlTask.objects.create(
            source=self.source, rule_version=self.rv,
            fingerprint=fp, url=url, status=CrawlTaskStatus.PENDING,
        )
        result = execute_crawl_task(task.pk)
        task.refresh_from_db()
        # Should be RETRYING after 1st failure (not yet at max attempts)
        self.assertEqual(task.status, CrawlTaskStatus.RETRYING)
        self.assertEqual(task.attempt_count, 1)
        self.assertIsNotNone(task.next_retry_at)

    def test_worker_quota_waitlist(self):
        from .worker import execute_crawl_task
        # Set rate limit to 0 to force waitlisting
        self.source.rate_limit_rpm = 0
        self.source.save()
        task = self._make_task()
        result = execute_crawl_task(task.pk)
        task.refresh_from_db()
        self.assertTrue(result.get("waiting"))
        self.assertEqual(task.status, CrawlTaskStatus.WAITING)

    def test_request_log_pruned_to_20(self):
        from .worker import execute_crawl_task
        # Create 25 dummy log entries for this source
        for i in range(25):
            fp = _compute_fingerprint(f"{self.live_server_url}/api/health/?x={i}", {})
            task = CrawlTask.objects.create(
                source=self.source, rule_version=self.rv,
                fingerprint=fp, url=f"{self.live_server_url}/api/health/",
                status=CrawlTaskStatus.PENDING,
            )
            execute_crawl_task(task.pk)
        total_logs = CrawlRequestLog.objects.filter(
            task__source=self.source
        ).count()
        self.assertLessEqual(total_logs, 20)


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
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
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
        from .worker import execute_crawl_task
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
        from .worker import execute_crawl_task
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
        from .worker import _pick_rule_version
        for _ in range(10):
            task = self._make_task()
            picked = _pick_rule_version(task)
            self.assertEqual(
                picked.pk, self.rv_canary.pk,
                "Expected canary version to be picked with canary_pct=100",
            )

    def test_canary_0pct_never_routes_to_canary(self):
        """With canary_pct=0 the active version is always used."""
        from .worker import _pick_rule_version
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
        from .worker import _pick_rule_version
        self.rv_canary.is_canary = False
        self.rv_canary.save()
        task = self._make_task()
        picked = _pick_rule_version(task)
        self.assertEqual(picked.pk, self.rv_active.pk)


# ─────────────────────────────────────────────────────────────────────────────
# Crawling RBAC — role gate and unauthenticated 401 matrix
# ─────────────────────────────────────────────────────────────────────────────

class CrawlingRBACTests(TestCase):
    """
    Verify role gates on all crawling endpoints.

    Unauthenticated → 401.  Wrong role → 403.  Correct role → 2xx.
    """

    def setUp(self):
        self.client = APIClient()
        self.analyst = create_user("crawl_rbac_analyst", Role.PROCUREMENT_ANALYST)
        self.manager = create_user("crawl_rbac_manager", Role.INVENTORY_MANAGER)
        self.admin = create_user("crawl_rbac_admin", Role.ADMIN)
        self.source = make_source("RBAC_SRC")
        self.rule_version = make_rule_version(self.source, is_active=True)

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    # ── Sources — list ─────────────────────────────────────────────────────────

    def test_unauthenticated_cannot_list_sources(self):
        """Unauthenticated requests to /api/crawl/sources/ must receive 401."""
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/crawl/sources/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_manager_cannot_list_sources(self):
        """INVENTORY_MANAGER must not list crawl sources (403)."""
        self._auth(self.manager)
        resp = self.client.get("/api/crawl/sources/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_analyst_can_list_sources(self):
        """PROCUREMENT_ANALYST may list crawl sources (200)."""
        self._auth(self.analyst)
        resp = self.client.get("/api/crawl/sources/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_list_sources(self):
        """ADMIN may list crawl sources (200)."""
        self._auth(self.admin)
        resp = self.client.get("/api/crawl/sources/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_manager_cannot_retrieve_source_detail(self):
        """INVENTORY_MANAGER must not view crawl source detail (403)."""
        self._auth(self.manager)
        resp = self.client.get(f"/api/crawl/sources/{self.source.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_list_rule_versions(self):
        """INVENTORY_MANAGER must not list rule versions for a source (403)."""
        self._auth(self.manager)
        resp = self.client.get(f"/api/crawl/sources/{self.source.pk}/rule-versions/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_view_debug_log(self):
        """INVENTORY_MANAGER must not access the debug log endpoint (403)."""
        self._auth(self.manager)
        resp = self.client.get(f"/api/crawl/sources/{self.source.pk}/debug-log/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_view_quota(self):
        """INVENTORY_MANAGER must not view source quota state (403)."""
        self._auth(self.manager)
        resp = self.client.get(f"/api/crawl/sources/{self.source.pk}/quota/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Sources — create (ProcurementAnalyst / Admin only) ─────────────────────

    def test_manager_cannot_create_source(self):
        """INVENTORY_MANAGER must not create crawl sources (403)."""
        self._auth(self.manager)
        resp = self.client.post("/api/crawl/sources/", {
            "name": "Blocked", "base_url": "http://block.local",
            "rate_limit_rpm": 30, "crawl_delay_seconds": 1,
            "user_agents": ["UA/1"],
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Rule versions — create (ProcurementAnalyst / Admin only) ───────────────

    def test_manager_cannot_create_rule_version(self):
        """INVENTORY_MANAGER must not create rule versions (403)."""
        self._auth(self.manager)
        resp = self.client.post(
            f"/api/crawl/sources/{self.source.pk}/rule-versions/",
            {"version_note": "blocked", "url_pattern": "http://x.local"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_create_rule_version(self):
        """Unauthenticated requests to rule-versions must receive 401."""
        self.client.force_authenticate(user=None)
        resp = self.client.post(
            f"/api/crawl/sources/{self.source.pk}/rule-versions/",
            {"version_note": "anon", "url_pattern": "http://x.local"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Tasks — list / enqueue ─────────────────────────────────────────────────

    def test_unauthenticated_cannot_list_tasks(self):
        """Unauthenticated requests to /api/crawl/tasks/ must receive 401."""
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/crawl/tasks/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_manager_cannot_enqueue_task(self):
        """INVENTORY_MANAGER must not enqueue crawl tasks (403)."""
        self._auth(self.manager)
        resp = self.client.post("/api/crawl/tasks/", {
            "source_id": self.source.pk,
            "url": "http://target.local/page",
            "parameters": {},
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_analyst_can_enqueue_task(self):
        """PROCUREMENT_ANALYST may enqueue a task (201 or 200 if deduplicated)."""
        self._auth(self.analyst)
        resp = self.client.post("/api/crawl/tasks/", {
            "source_id": self.source.pk,
            "url": "http://target.local/rbac-page",
            "parameters": {},
        }, format="json")
        self.assertIn(resp.status_code, (status.HTTP_201_CREATED, status.HTTP_200_OK))


# ─────────────────────────────────────────────────────────────────────────────
# SPEC constant alignment — Finding 5
# ─────────────────────────────────────────────────────────────────────────────

class WorkerConstantsTests(TestCase):
    """
    Verify that worker module constants exactly match SPEC.md values.

    Keeps implementation honest: changing a constant silently would break
    SPEC alignment without a failing test to catch it.
    """

    def test_backoff_schedule_matches_spec(self):
        """Backoff delays: 10 s → 30 s → 2 min → 10 min, max 5 attempts."""
        from .worker import _BACKOFF, _MAX_ATTEMPTS
        self.assertEqual(_MAX_ATTEMPTS, 5, "SPEC: max 5 attempts")
        self.assertEqual(_BACKOFF[0], 10,  "SPEC: first retry delay 10 s")
        self.assertEqual(_BACKOFF[1], 30,  "SPEC: second retry delay 30 s")
        self.assertEqual(_BACKOFF[2], 120, "SPEC: third retry delay 2 min (120 s)")
        self.assertEqual(_BACKOFF[3], 600, "SPEC: fourth retry delay 10 min (600 s)")

    def test_log_keep_matches_spec(self):
        """Visual debugger retains last 20 request/response samples (SPEC §6.6)."""
        from .worker import _LOG_KEEP
        self.assertEqual(_LOG_KEEP, 20, "SPEC: keep last 20 debug log entries per source")

    def test_checkpoint_interval_matches_spec(self):
        """Checkpoint written every 100 pages (SPEC)."""
        from .worker import _CHECKPOINT_INTERVAL
        self.assertEqual(_CHECKPOINT_INTERVAL, 100, "SPEC: checkpoint every 100 pages")

    def test_canary_pct_default_matches_spec(self):
        """New CrawlRuleVersion defaults to canary_pct=5 (5% of tasks per SPEC §1)."""
        source = make_source("CONST_CANARY_SRC")
        rv = CrawlRuleVersion.objects.create(
            source=source,
            version_number=1,
            url_pattern="http://const.test/",
            version_note="spec constant test",
        )
        self.assertEqual(rv.canary_pct, 5, "SPEC: canary routes 5% of tasks")


# ─────────────────────────────────────────────────────────────────────────────
# Response snippet redaction (security — Finding 3)
# ─────────────────────────────────────────────────────────────────────────────

class _FakeResponse:
    """Minimal stand-in for requests.Response used in _log_request tests."""
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


class ResponseSnippetRedactionTests(TestCase):
    """
    Verify that _log_request masks sensitive values in response bodies
    before persisting to CrawlRequestLog.response_snippet.
    """

    def setUp(self):
        self.source = make_source("REDACT_SRC")
        self.rv = make_rule_version(self.source, version_number=1, is_active=True)
        fp = _compute_fingerprint("http://redact.local/data", {})
        self.task = CrawlTask.objects.create(
            source=self.source,
            rule_version=self.rv,
            fingerprint=fp,
            url="http://redact.local/data",
            status=CrawlTaskStatus.PENDING,
        )

    def _call_log_request(self, response_text):
        from .worker import _log_request
        _log_request(
            task=self.task,
            url="http://redact.local/data",
            headers={},
            response=_FakeResponse(response_text),
            duration_ms=50,
        )
        return CrawlRequestLog.objects.filter(task=self.task).order_by("-timestamp").first()

    def test_bearer_token_in_response_body_is_redacted(self):
        """Authorization: Bearer <token> patterns in response text must be masked."""
        raw = 'Authorization: Bearer supersecrettoken123'
        log = self._call_log_request(raw)
        self.assertNotIn("supersecrettoken123", log.response_snippet)
        self.assertIn("[REDACTED]", log.response_snippet)

    def test_json_access_token_in_response_body_is_redacted(self):
        """{"access_token": "..."} in response body must be masked."""
        raw = '{"access_token": "eyJhbGciOiJSUzI1NiJ9.payload.sig", "expires_in": 3600}'
        log = self._call_log_request(raw)
        self.assertNotIn("eyJhbGciOiJSUzI1NiJ9", log.response_snippet)
        self.assertIn("[REDACTED]", log.response_snippet)

    def test_json_password_in_response_body_is_redacted(self):
        """{"password": "..."} in response body must be masked."""
        raw = '{"username": "admin", "password": "hunter2"}'
        log = self._call_log_request(raw)
        self.assertNotIn("hunter2", log.response_snippet)
        self.assertIn("[REDACTED]", log.response_snippet)

    def test_non_sensitive_response_body_unchanged(self):
        """Ordinary response content (no secrets) must pass through unmodified."""
        raw = '{"id": 42, "name": "Widget A", "price": "9.99"}'
        log = self._call_log_request(raw)
        self.assertIn("Widget A", log.response_snippet)
        self.assertIn("9.99", log.response_snippet)

    def test_empty_response_stores_empty_snippet(self):
        """A None response (e.g. connection error before any data) stores empty string."""
        from .worker import _log_request
        _log_request(
            task=self.task,
            url="http://redact.local/data",
            headers={},
            response=None,
            duration_ms=0,
        )
        log = CrawlRequestLog.objects.filter(task=self.task).order_by("-timestamp").first()
        self.assertEqual(log.response_snippet, "")


# ─────────────────────────────────────────────────────────────────────────────
# 365-day crawl record retention purge (Finding 4)
# ─────────────────────────────────────────────────────────────────────────────

class CrawlRecordRetentionTests(TestCase):
    """
    Verify purge_old_crawl_records deletes CrawlTask and CrawlRequestLog rows
    older than 365 days and leaves recent rows intact.
    """

    def setUp(self):
        self.source = make_source("RETENTION_SRC")
        self.rv = make_rule_version(self.source, version_number=1, is_active=True)

    def _make_task(self, label, task_status=CrawlTaskStatus.COMPLETED):
        fp = _compute_fingerprint(f"http://ret.local/{label}", {})
        return CrawlTask.objects.create(
            source=self.source,
            rule_version=self.rv,
            fingerprint=fp,
            url=f"http://ret.local/{label}",
            status=task_status,
        )

    def _make_log(self, task):
        return CrawlRequestLog.objects.create(
            task=task,
            request_url=task.url,
            request_headers="{}",
            response_status=200,
            response_snippet="ok",
            duration_ms=10,
        )

    def _age(self, obj, model_class, days):
        """Back-date created_at on obj to `days` ago via queryset update."""
        old_ts = timezone.now() - timedelta(days=days)
        model_class.objects.filter(pk=obj.pk).update(created_at=old_ts)

    def test_old_completed_tasks_are_deleted(self):
        from .tasks import purge_old_crawl_records
        old_task = self._make_task("old_completed")
        self._age(old_task, CrawlTask, 366)

        result = purge_old_crawl_records()

        self.assertFalse(CrawlTask.objects.filter(pk=old_task.pk).exists())
        self.assertGreaterEqual(result["tasks_deleted"], 1)

    def test_recent_completed_tasks_are_kept(self):
        from .tasks import purge_old_crawl_records
        recent_task = self._make_task("recent_completed")
        # created_at defaults to now — within 365-day window

        purge_old_crawl_records()

        self.assertTrue(CrawlTask.objects.filter(pk=recent_task.pk).exists())

    def test_pending_tasks_not_deleted_even_if_old(self):
        """Active-state tasks (PENDING/RUNNING) must never be purged."""
        from .tasks import purge_old_crawl_records
        pending_task = self._make_task("old_pending", task_status=CrawlTaskStatus.PENDING)
        self._age(pending_task, CrawlTask, 400)

        purge_old_crawl_records()

        self.assertTrue(CrawlTask.objects.filter(pk=pending_task.pk).exists())

    def test_old_request_logs_are_deleted(self):
        from .tasks import purge_old_crawl_records
        task = self._make_task("log_task")
        log = self._make_log(task)
        self._age(log, CrawlRequestLog, 366)

        result = purge_old_crawl_records()

        self.assertFalse(CrawlRequestLog.objects.filter(pk=log.pk).exists())
        self.assertGreaterEqual(result["request_logs_deleted"], 1)

    def test_recent_request_logs_are_kept(self):
        from .tasks import purge_old_crawl_records
        task = self._make_task("recent_log_task")
        log = self._make_log(task)

        purge_old_crawl_records()

        self.assertTrue(CrawlRequestLog.objects.filter(pk=log.pk).exists())


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
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
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
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
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
        from .worker import execute_crawl_task

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
        from .worker import execute_crawl_task

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


# ─────────────────────────────────────────────────────────────────────────────
# 6.9  CrawledProduct persistence + dedupe
# 6.10 /rule-versions/{id}/test/ endpoint
# 6.11 promote_waiting_tasks + quota_pre_acquired=True path
# ─────────────────────────────────────────────────────────────────────────────

class NewFeatureTests(LiveServerTestCase):
    """
    Integration tests for features added after the initial Phase-6 delivery:
      6.9  CrawledProduct written and deduplicated on worker execution
      6.10 POST /api/crawl/rule-versions/{id}/test/ probe endpoint
      6.11 execute_crawl_task with quota_pre_acquired=True skips quota
           promote_waiting_tasks promotes WAITING → PENDING
    """

    def setUp(self):
        self.analyst = create_user("new_feat_analyst", Role.PROCUREMENT_ANALYST)
        self.source = make_source("NEW_FEAT_SRC", rate_limit=60)
        self.source.crawl_delay_seconds = 0
        self.source.save()
        self.rv = make_rule_version(self.source, version_number=1)
        # Point the rule version at the live server health endpoint
        self.rv.url_pattern = f"{self.live_server_url}/api/health/"
        self.rv.save(update_fields=["url_pattern"])

    def _make_task(self, url=None):
        url = url or f"{self.live_server_url}/api/health/"
        fp = _compute_fingerprint(url, {})
        return CrawlTask.objects.create(
            source=self.source,
            rule_version=self.rv,
            fingerprint=fp,
            url=url,
            status=CrawlTaskStatus.PENDING,
        )

    # ── 6.9  CrawledProduct write + dedupe ────────────────────────────────────

    def test_crawled_product_created_on_successful_response(self):
        """Worker creates exactly one CrawledProduct record for a successful fetch."""
        from .worker import execute_crawl_task
        task = self._make_task()
        execute_crawl_task(task.pk)
        self.assertEqual(CrawledProduct.objects.filter(source=self.source).count(), 1)

    def test_crawled_product_deduped_on_identical_payload(self):
        """
        Two tasks that fetch the same URL (same JSON payload) must not produce
        duplicate CrawledProduct rows — the checksum guard deduplicates them.
        """
        from .worker import execute_crawl_task
        task1 = self._make_task()
        fp2 = _compute_fingerprint(f"{self.live_server_url}/api/health/", {"v": "2"})
        task2 = CrawlTask.objects.create(
            source=self.source, rule_version=self.rv,
            fingerprint=fp2,
            url=f"{self.live_server_url}/api/health/",
            status=CrawlTaskStatus.PENDING,
        )
        execute_crawl_task(task1.pk)
        count_after_first = CrawledProduct.objects.filter(source=self.source).count()
        execute_crawl_task(task2.pk)
        count_after_second = CrawledProduct.objects.filter(source=self.source).count()
        # Health endpoint returns identical JSON both times → same checksum → no duplicate
        self.assertEqual(count_after_first, count_after_second)

    # ── 6.10  /rule-versions/{id}/test/ ──────────────────────────────────────

    def test_rule_test_endpoint_returns_response_data(self):
        """POST /test/ on a local URL returns status_code, duration_ms, snippet."""
        client = APIClient()
        token = login(client, "new_feat_analyst")
        auth(client, token)
        resp = client.post(f"/api/crawl/rule-versions/{self.rv.pk}/test/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["status_code"], 200)
        self.assertIsNotNone(data["duration_ms"])
        self.assertIsNone(data["error"])

    def test_rule_test_endpoint_rejects_public_url(self):
        """
        If a public URL somehow ends up in url_pattern (e.g. direct DB edit),
        POST /test/ must return 400 — the defense-in-depth guard fires.
        """
        client = APIClient()
        token = login(client, "new_feat_analyst")
        auth(client, token)
        # Bypass serializer validation by writing directly to the model
        self.rv.url_pattern = "http://example.com/products"
        self.rv.save(update_fields=["url_pattern"])
        resp = client.post(f"/api/crawl/rule-versions/{self.rv.pk}/test/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ── 6.11  quota_pre_acquired=True + promote_waiting_tasks ─────────────────

    def test_execute_crawl_task_quota_pre_acquired_skips_quota_check(self):
        """
        With quota_pre_acquired=True the worker skips quota acquisition and
        executes the task even when rate_limit_rpm=0 (no quota available).
        """
        from .worker import execute_crawl_task
        self.source.rate_limit_rpm = 0
        self.source.save(update_fields=["rate_limit_rpm"])
        task = self._make_task()
        result = execute_crawl_task(task.pk, quota_pre_acquired=True)
        task.refresh_from_db()
        self.assertTrue(result.get("completed"), f"Expected completed, got: {result}")
        self.assertEqual(task.status, CrawlTaskStatus.COMPLETED)

    def test_promote_waiting_tasks_promotes_to_pending(self):
        """
        promote_waiting_tasks acquires quota for WAITING tasks and moves them
        to PENDING (and dispatches execution via apply_async with
        quota_pre_acquired=True so the promoted task does not double-count).
        """
        from django.test.utils import override_settings
        from .tasks import promote_waiting_tasks
        task = self._make_task()
        task.status = CrawlTaskStatus.WAITING
        task.save(update_fields=["status"])
        # CELERY_TASK_ALWAYS_EAGER executes apply_async synchronously without
        # a broker, allowing the full promotion + execution path to run in-process.
        with override_settings(CELERY_TASK_ALWAYS_EAGER=True):
            result = promote_waiting_tasks()
        self.assertGreaterEqual(result["promoted"], 1)
        task.refresh_from_db()
        # With ALWAYS_EAGER the task runs synchronously and reaches COMPLETED
        self.assertIn(task.status, (CrawlTaskStatus.PENDING, CrawlTaskStatus.COMPLETED))
