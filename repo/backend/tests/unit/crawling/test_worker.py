"""
tests/crawling/test_worker.py — Worker execution tests.

Covers worker task completion, request logging, header masking, retry logic,
quota waitlisting, log pruning, SPEC constant alignment, and response snippet
redaction.
"""
import json

from django.test import LiveServerTestCase, TestCase

from accounts.models import Role, User
from crawling.models import (
    CrawledProduct,
    CrawlRequestLog,
    CrawlRuleVersion,
    CrawlSource,
    CrawlTask,
    CrawlTaskStatus,
)
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
        from crawling.worker import execute_crawl_task
        task = self._make_task()
        result = execute_crawl_task(task.pk)
        task.refresh_from_db()
        self.assertTrue(result.get("completed"))
        self.assertEqual(task.status, CrawlTaskStatus.COMPLETED)
        self.assertIsNotNone(task.completed_at)

    def test_worker_logs_request(self):
        from crawling.worker import execute_crawl_task
        task = self._make_task()
        execute_crawl_task(task.pk)
        logs = CrawlRequestLog.objects.filter(task=task)
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.response_status, 200)
        self.assertIsNotNone(log.duration_ms)

    def test_worker_masks_auth_headers(self):
        from crawling.worker import execute_crawl_task
        self.rv.request_headers = json.dumps({"Authorization": "Bearer supersecret"})
        self.rv.save()
        task = self._make_task()
        execute_crawl_task(task.pk)
        log = CrawlRequestLog.objects.filter(task=task).first()
        stored = json.loads(log.request_headers)
        self.assertEqual(stored.get("Authorization"), "[REDACTED]")

    def test_worker_retries_on_failure(self):
        from crawling.worker import execute_crawl_task
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
        from crawling.worker import execute_crawl_task
        # Set rate limit to 0 to force waitlisting
        self.source.rate_limit_rpm = 0
        self.source.save()
        task = self._make_task()
        result = execute_crawl_task(task.pk)
        task.refresh_from_db()
        self.assertTrue(result.get("waiting"))
        self.assertEqual(task.status, CrawlTaskStatus.WAITING)

    def test_request_log_pruned_to_20(self):
        from crawling.worker import execute_crawl_task
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
        from crawling.worker import _BACKOFF, _MAX_ATTEMPTS
        self.assertEqual(_MAX_ATTEMPTS, 5, "SPEC: max 5 attempts")
        self.assertEqual(_BACKOFF[0], 10,  "SPEC: first retry delay 10 s")
        self.assertEqual(_BACKOFF[1], 30,  "SPEC: second retry delay 30 s")
        self.assertEqual(_BACKOFF[2], 120, "SPEC: third retry delay 2 min (120 s)")
        self.assertEqual(_BACKOFF[3], 600, "SPEC: fourth retry delay 10 min (600 s)")

    def test_log_keep_matches_spec(self):
        """Visual debugger retains last 20 request/response samples (SPEC §6.6)."""
        from crawling.worker import _LOG_KEEP
        self.assertEqual(_LOG_KEEP, 20, "SPEC: keep last 20 debug log entries per source")

    def test_checkpoint_interval_matches_spec(self):
        """Checkpoint written every 100 pages (SPEC)."""
        from crawling.worker import _CHECKPOINT_INTERVAL
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
        from crawling.worker import _log_request
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
        from crawling.worker import _log_request
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
# 6.9 + 6.10 + 6.11 New features (CrawledProduct, test endpoint, promote)
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
        from crawling.worker import execute_crawl_task
        task = self._make_task()
        execute_crawl_task(task.pk)
        self.assertEqual(CrawledProduct.objects.filter(source=self.source).count(), 1)

    def test_crawled_product_deduped_on_identical_payload(self):
        """
        Two tasks that fetch the same URL (same JSON payload) must not produce
        duplicate CrawledProduct rows — the checksum guard deduplicates them.
        """
        from crawling.worker import execute_crawl_task
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
        from rest_framework.test import APIClient
        client = APIClient()
        token = login(client, "new_feat_analyst")
        auth(client, token)
        resp = client.post(f"/api/crawl/rule-versions/{self.rv.pk}/test/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status_code"], 200)
        self.assertIsNotNone(data["duration_ms"])
        self.assertIsNone(data["error"])

    def test_rule_test_endpoint_rejects_public_url(self):
        """
        If a public URL somehow ends up in url_pattern (e.g. direct DB edit),
        POST /test/ must return 400 — the defense-in-depth guard fires.
        """
        from rest_framework.test import APIClient
        client = APIClient()
        token = login(client, "new_feat_analyst")
        auth(client, token)
        # Bypass serializer validation by writing directly to the model
        self.rv.url_pattern = "http://example.com/products"
        self.rv.save(update_fields=["url_pattern"])
        resp = client.post(f"/api/crawl/rule-versions/{self.rv.pk}/test/")
        self.assertEqual(resp.status_code, 400)

    # ── 6.11  quota_pre_acquired=True + promote_waiting_tasks ─────────────────

    def test_execute_crawl_task_quota_pre_acquired_skips_quota_check(self):
        """
        With quota_pre_acquired=True the worker skips quota acquisition and
        executes the task even when rate_limit_rpm=0 (no quota available).
        """
        from crawling.worker import execute_crawl_task
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
        from crawling.tasks import promote_waiting_tasks
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
