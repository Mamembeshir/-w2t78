"""
tests/crawling/test_task_api.py — CrawlTask API tests.

Covers GET /api/crawl/tasks/ (list) and GET /api/crawl/tasks/{id}/ (detail),
retry action, authentication guards, and RBAC.
"""
import hashlib

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Role, User
from crawling.models import CrawlRuleVersion, CrawlSource, CrawlTask, CrawlTaskStatus


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


def make_source(name="TaskSource"):
    return CrawlSource.objects.create(
        name=name,
        base_url="http://example.local",
        rate_limit_rpm=60,
        crawl_delay_seconds=0,
        user_agents=["TestAgent/1.0"],
    )


def make_rule_version(source, version_number=1):
    return CrawlRuleVersion.objects.create(
        source=source,
        version_number=version_number,
        version_note="Test version",
        url_pattern="http://example.local/products",
        parameters={},
        pagination_config={},
        is_active=True,
    )


def make_task(source, rule_version, url="http://example.local/page/1", task_status=CrawlTaskStatus.PENDING):
    fingerprint = hashlib.sha256(url.encode()).hexdigest()
    return CrawlTask.objects.create(
        source=source,
        rule_version=rule_version,
        fingerprint=fingerprint,
        url=url,
        status=task_status,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6.3 Task API
# ─────────────────────────────────────────────────────────────────────────────

class CrawlTaskListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.analyst = create_user("task_analyst", Role.PROCUREMENT_ANALYST)
        self.inv = create_user("task_inv", Role.INVENTORY_MANAGER)
        self.token = login(self.client, "task_analyst")
        self.inv_token = login(self.client, "task_inv")
        self.src = make_source("TaskSrc")
        self.rv = make_rule_version(self.src)

    def test_list_tasks_authenticated(self):
        make_task(self.src, self.rv, url="http://example.local/p1")
        auth(self.client, self.token)
        resp = self.client.get("/api/crawl/tasks/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.json()["count"], 1)

    def test_list_tasks_unauthenticated(self):
        resp = self.client.get("/api/crawl/tasks/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_tasks_inventory_manager_forbidden(self):
        auth(self.client, self.inv_token)
        resp = self.client.get("/api/crawl/tasks/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_tasks_filter_by_status(self):
        make_task(self.src, self.rv, url="http://example.local/p2", task_status=CrawlTaskStatus.PENDING)
        make_task(self.src, self.rv, url="http://example.local/p3", task_status=CrawlTaskStatus.COMPLETED)
        auth(self.client, self.token)
        resp = self.client.get("/api/crawl/tasks/?status=PENDING")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for t in resp.json()["results"]:
            self.assertEqual(t["status"], "PENDING")

    def test_list_shows_task_fields(self):
        make_task(self.src, self.rv, url="http://example.local/p4")
        auth(self.client, self.token)
        resp = self.client.get("/api/crawl/tasks/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        task = resp.json()["results"][0]
        self.assertIn("url", task)
        self.assertIn("status", task)
        self.assertIn("source", task)


class CrawlTaskDetailTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.analyst = create_user("taskdet_analyst", Role.PROCUREMENT_ANALYST)
        self.inv = create_user("taskdet_inv", Role.INVENTORY_MANAGER)
        self.token = login(self.client, "taskdet_analyst")
        self.inv_token = login(self.client, "taskdet_inv")
        self.src = make_source("DetailSrc")
        self.rv = make_rule_version(self.src)

    def test_retrieve_task_detail(self):
        task = make_task(self.src, self.rv, url="http://example.local/detail/1")
        auth(self.client, self.token)
        resp = self.client.get(f"/api/crawl/tasks/{task.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["url"], "http://example.local/detail/1")
        self.assertEqual(data["status"], CrawlTaskStatus.PENDING)

    def test_retrieve_task_detail_unauthenticated(self):
        task = make_task(self.src, self.rv, url="http://example.local/detail/2")
        resp = self.client.get(f"/api/crawl/tasks/{task.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_task_detail_inventory_manager_forbidden(self):
        task = make_task(self.src, self.rv, url="http://example.local/detail/3")
        auth(self.client, self.inv_token)
        resp = self.client.get(f"/api/crawl/tasks/{task.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_nonexistent_task_404(self):
        auth(self.client, self.token)
        resp = self.client.get("/api/crawl/tasks/99999/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_task_detail_shows_source_and_rule_version(self):
        task = make_task(self.src, self.rv, url="http://example.local/detail/4")
        auth(self.client, self.token)
        resp = self.client.get(f"/api/crawl/tasks/{task.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn("source", data)
        self.assertIn("rule_version", data)
        self.assertIn("attempt_count", data)

    def test_retry_failed_task(self):
        task = make_task(
            self.src, self.rv,
            url="http://example.local/retry/1",
            task_status=CrawlTaskStatus.FAILED,
        )
        auth(self.client, self.token)
        resp = self.client.post(f"/api/crawl/tasks/{task.pk}/retry/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        self.assertEqual(task.status, CrawlTaskStatus.PENDING)

    def test_retry_non_failed_task_returns_404(self):
        # The view uses get_object_or_404(..., status=FAILED), so a COMPLETED
        # task is treated as "not found" for the retry endpoint.
        task = make_task(
            self.src, self.rv,
            url="http://example.local/retry/2",
            task_status=CrawlTaskStatus.COMPLETED,
        )
        auth(self.client, self.token)
        resp = self.client.post(f"/api/crawl/tasks/{task.pk}/retry/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
