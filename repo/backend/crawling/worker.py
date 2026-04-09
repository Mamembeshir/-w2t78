"""
crawling/worker.py — Celery task that executes a single crawl task.

Business rules implemented:
  - Canary version selection: 5% random routing (CLAUDE.md §1)
  - User-agent rotation from source.user_agents (CLAUDE.md §9)
  - crawl_delay_seconds honored between page requests (CLAUDE.md §9)
  - Exponential backoff: 10s → 30s → 2m → 10m, max 5 attempts (SPEC)
  - Checkpoint every 100 pages (SPEC)
  - Resume from checkpoint_page on restart (SPEC)
  - Request headers from encrypted CrawlRuleVersion.request_headers
  - Per-request logging to CrawlRequestLog, kept last 20 per source (6.6)
  - Secrets masked in stored headers (CLAUDE.md §8)
  - Extracted product/supplier payload persisted to CrawledProduct (SPEC §1)
"""
import hashlib
import json
import random
import re
import time

import requests as http_requests
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from config.logging_filters import _mask

from .models import (
    CrawledProduct,
    CrawlRequestLog,
    CrawlTask,
    CrawlTaskStatus,
)
from .quota import acquire_quota, release_quota

# Exponential backoff delays in seconds (attempt 1→2→3→4→5)
_BACKOFF = [10, 30, 120, 600, 600]
_MAX_ATTEMPTS = 5
_CHECKPOINT_INTERVAL = 100
_LOG_KEEP = 20
# Maximum raw_text fallback stored when response is not JSON
_RAW_TEXT_MAX = 10_000


def _pick_rule_version(task: CrawlTask):
    """
    Return the rule version to use for this task.

    If a canary version is active for the source, route ~5% of tasks to it.
    Otherwise use the active version.
    """
    source = task.source

    # Check for an active canary
    canary = source.rule_versions.filter(is_canary=True).first()
    if canary and random.random() < (canary.canary_pct / 100.0):
        return canary

    # Use the explicitly assigned rule_version (set at enqueue time)
    return task.rule_version


def _get_headers(rule_version) -> dict:
    """Decrypt and parse request headers from the rule version."""
    if not rule_version.request_headers:
        return {}
    try:
        return json.loads(rule_version.request_headers)
    except (json.JSONDecodeError, TypeError):
        return {}


def _mask_headers(headers: dict) -> str:
    """Return JSON string of headers with sensitive values redacted."""
    masked = {}
    secret_pattern = re.compile(
        r"(authorization|secret|key|token|password|api[_-]?key)",
        re.IGNORECASE,
    )
    for k, v in headers.items():
        if secret_pattern.search(k):
            masked[k] = "[REDACTED]"
        else:
            masked[k] = v
    return json.dumps(masked)


def _log_request(task: CrawlTask, url: str, headers: dict,
                 response, duration_ms: int) -> None:
    """
    Persist one CrawlRequestLog entry and prune to last 20 per source.
    """
    CrawlRequestLog.objects.create(
        task=task,
        request_url=url,
        request_headers=_mask_headers(headers),
        response_status=response.status_code if response else None,
        response_snippet=(_mask(response.text[:500]) if response else ""),
        duration_ms=duration_ms,
    )
    # Keep only the last 20 logs for this source (across all tasks)
    source_task_ids = task.source.tasks.values_list("id", flat=True)
    log_qs = CrawlRequestLog.objects.filter(
        task__in=source_task_ids
    ).order_by("-timestamp")
    keep_ids = list(log_qs.values_list("id", flat=True)[:_LOG_KEEP])
    CrawlRequestLog.objects.filter(
        task__in=source_task_ids
    ).exclude(pk__in=keep_ids).delete()


def _persist_response(task: CrawlTask, url: str, response) -> None:
    """
    Persist extracted product/supplier data from a successful HTTP response.

    Attempts to parse the body as JSON; falls back to a text wrapper dict.
    Idempotent: identical content for the same source (same SHA-256 checksum)
    is not duplicated.
    """
    try:
        payload = response.json()
    except Exception:
        payload = {"raw_text": response.text[:_RAW_TEXT_MAX]}

    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    checksum = hashlib.sha256(canonical.encode()).hexdigest()

    if CrawledProduct.objects.filter(source=task.source, checksum=checksum).exists():
        return

    CrawledProduct.objects.create(
        source=task.source,
        task=task,
        page_url=url,
        raw_payload=payload,
        checksum=checksum,
    )


def _schedule_retry(task: CrawlTask, error: str) -> None:
    """Schedule the next retry or mark as permanently FAILED."""
    from datetime import timedelta

    from config.logging_filters import _mask

    attempt = task.attempt_count + 1
    task.attempt_count = attempt
    task.last_error = _mask(error)[:2000]

    if attempt >= _MAX_ATTEMPTS:
        task.status = CrawlTaskStatus.FAILED
        task.save(update_fields=["attempt_count", "last_error", "status"])
        # Fire notification
        _notify_max_retries(task)
        return

    delay_seconds = _BACKOFF[min(attempt - 1, len(_BACKOFF) - 1)]
    task.next_retry_at = timezone.now() + timedelta(seconds=delay_seconds)
    task.status = CrawlTaskStatus.RETRYING
    task.save(update_fields=["attempt_count", "last_error", "status", "next_retry_at"])

    # Re-schedule the Celery task on the same source shard
    from .routing import crawl_queue_for_source
    execute_crawl_task.apply_async(
        args=[task.pk],
        countdown=delay_seconds,
        queue=crawl_queue_for_source(task.source_id),
    )


def _notify_max_retries(task: CrawlTask) -> None:
    """Create an in-app notification when a task exhausts all retries."""
    try:
        from notifications.models import EventType, Notification, NotificationSubscription
        subscriptions = NotificationSubscription.objects.filter(
            event_type=EventType.CRAWL_TASK_FAILED,
            is_active=True,
        ).select_related("user")
        for sub in subscriptions:
            Notification.objects.create(
                user=sub.user,
                event_type=EventType.CRAWL_TASK_FAILED,
                title=f"Crawl task failed: {task.source.name}",
                body=(
                    f"Task #{task.pk} for source '{task.source.name}' exhausted "
                    f"{_MAX_ATTEMPTS} attempts.\n"
                    f"Last error: {task.last_error[:300]}"
                ),
            )
    except Exception:
        pass  # Never let notification failure break the worker


@shared_task(name="crawling.execute_crawl_task")
def execute_crawl_task(task_id: int, quota_pre_acquired: bool = False) -> dict:
    """
    Execute a single crawl task.

    Flow:
      1. Load task (skip if already COMPLETED/CANCELLED)
      2. Acquire quota — skipped when quota_pre_acquired=True (set by
         promote_waiting_tasks to avoid double-counting the slot it already
         claimed during waitlist promotion)
      3. Pick rule version (canary or active)
      4. Execute HTTP requests (with page loop + checkpoint)
      5. Release quota
      6. Mark COMPLETED or schedule retry on failure
    """
    try:
        task = CrawlTask.objects.select_related("source", "rule_version").get(pk=task_id)
    except CrawlTask.DoesNotExist:
        return {"error": f"Task {task_id} not found"}

    if task.status in (CrawlTaskStatus.COMPLETED, CrawlTaskStatus.CANCELLED):
        return {"skipped": True, "status": task.status}

    source = task.source

    # ── Quota check ───────────────────────────────────────────────────────────
    if not quota_pre_acquired:
        if not acquire_quota(source):
            task.status = CrawlTaskStatus.WAITING
            task.save(update_fields=["status"])
            return {"waiting": True, "reason": "quota_exceeded"}

    try:
        return _do_execute(task)
    finally:
        release_quota(source)


def _do_execute(task: CrawlTask) -> dict:
    """Inner execution — quota already acquired."""
    source = task.source
    rule_version = _pick_rule_version(task)
    headers = _get_headers(rule_version)

    # User-agent rotation
    user_agents = source.user_agents or []
    if user_agents:
        headers["User-Agent"] = random.choice(user_agents)

    # Pagination config
    pagination = rule_version.pagination_config or {}
    p_type = pagination.get("type", "single")
    page_param = pagination.get("param", "page")
    start_page = max(task.checkpoint_page, pagination.get("start", 1))
    max_pages = pagination.get("max_pages", 1) if p_type == "page_number" else 1

    # Mark as RUNNING
    task.status = CrawlTaskStatus.RUNNING
    task.started_at = timezone.now()
    task.save(update_fields=["status", "started_at"])

    base_params = dict(rule_version.parameters or {})

    for page in range(start_page, start_page + max_pages):
        page_params = dict(base_params)
        if p_type == "page_number":
            page_params[page_param] = page

        url = task.url
        start_time = time.time()
        response = None

        # Honor crawl delay from local ruleset between requests (CLAUDE.md §9)
        if source.honor_local_crawl_delay and source.crawl_delay_seconds > 0 and page > start_page:
            time.sleep(source.crawl_delay_seconds)

        try:
            response = http_requests.get(
                url,
                params=page_params,
                headers=headers,
                timeout=30,
                allow_redirects=True,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            _log_request(task, url, headers, response, duration_ms)
            response.raise_for_status()
            _persist_response(task, url, response)

        except http_requests.RequestException as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            _log_request(task, url, headers, response, duration_ms)
            _schedule_retry(task, str(exc))
            return {"failed": True, "error": str(exc)}

        # Checkpoint every 100 pages
        if (page - start_page + 1) % _CHECKPOINT_INTERVAL == 0:
            task.checkpoint_page = page
            task.save(update_fields=["checkpoint_page"])

    # All pages processed — mark complete
    task.status = CrawlTaskStatus.COMPLETED
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "completed_at"])

    return {"completed": True, "pages_processed": max_pages}
