"""
tests/crawling/test_task_scheduler.py — Task scheduler tests.

Covers task enqueue, fingerprint deduplication, filtering, and retry logic.
"""
from django.test import TestCase
from rest_framework import status
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
