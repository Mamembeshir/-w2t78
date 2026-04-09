"""
tests/crawling/test_retention.py — Crawl record retention/purge tests.

Verifies purge_old_crawl_records deletes CrawlTask and CrawlRequestLog rows
older than 365 days and leaves recent rows intact.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from crawling.models import (
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
        from crawling.tasks import purge_old_crawl_records
        old_task = self._make_task("old_completed")
        self._age(old_task, CrawlTask, 366)

        result = purge_old_crawl_records()

        self.assertFalse(CrawlTask.objects.filter(pk=old_task.pk).exists())
        self.assertGreaterEqual(result["tasks_deleted"], 1)

    def test_recent_completed_tasks_are_kept(self):
        from crawling.tasks import purge_old_crawl_records
        recent_task = self._make_task("recent_completed")
        # created_at defaults to now — within 365-day window

        purge_old_crawl_records()

        self.assertTrue(CrawlTask.objects.filter(pk=recent_task.pk).exists())

    def test_pending_tasks_not_deleted_even_if_old(self):
        """Active-state tasks (PENDING/RUNNING) must never be purged."""
        from crawling.tasks import purge_old_crawl_records
        pending_task = self._make_task("old_pending", task_status=CrawlTaskStatus.PENDING)
        self._age(pending_task, CrawlTask, 400)

        purge_old_crawl_records()

        self.assertTrue(CrawlTask.objects.filter(pk=pending_task.pk).exists())

    def test_old_request_logs_are_deleted(self):
        from crawling.tasks import purge_old_crawl_records
        task = self._make_task("log_task")
        log = self._make_log(task)
        self._age(log, CrawlRequestLog, 366)

        result = purge_old_crawl_records()

        self.assertFalse(CrawlRequestLog.objects.filter(pk=log.pk).exists())
        self.assertGreaterEqual(result["request_logs_deleted"], 1)

    def test_recent_request_logs_are_kept(self):
        from crawling.tasks import purge_old_crawl_records
        task = self._make_task("recent_log_task")
        log = self._make_log(task)

        purge_old_crawl_records()

        self.assertTrue(CrawlRequestLog.objects.filter(pk=log.pk).exists())
