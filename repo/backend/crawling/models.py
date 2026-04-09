"""
crawling/models.py — Crawl source configuration, rule versioning,
task queue, request logs, and per-source quota tracking.

Key business rules encoded here:
  - Canary: 5 % of tasks, 30-min window, auto-rollback at > 2 % error rate
  - Retry backoff: 10s → 30s → 2m → 10m (max 5 attempts)
  - Quota deducted before request; auto-release after 15 min
  - Fingerprint: deterministic hash of URL + sorted params + headers
  - Checkpoint: every 100 pages
"""
from django.conf import settings
from django.db import models

from encrypted_model_fields.fields import EncryptedTextField

from core.models import TimeStampedModel


class CrawlTaskStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    WAITING = "WAITING", "Waiting (quota exceeded)"
    RUNNING = "RUNNING", "Running"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    RETRYING = "RETRYING", "Retrying"
    CANCELLED = "CANCELLED", "Cancelled"


# ─────────────────────────────────────────────────────────────────────────────
# Source & Rule Version
# ─────────────────────────────────────────────────────────────────────────────

class CrawlSource(TimeStampedModel):
    """
    A supplier/target website from which data is crawled.

    user_agents — JSON list of user-agent strings to rotate.
    rate_limit_rpm — maximum requests per minute (default 60).
    crawl_delay_seconds — minimum seconds between requests.
    """

    name = models.CharField(max_length=200, unique=True)
    base_url = models.CharField(max_length=500)
    is_active = models.BooleanField(default=True, db_index=True)
    rate_limit_rpm = models.PositiveIntegerField(default=60)
    crawl_delay_seconds = models.PositiveIntegerField(default=1)
    honor_local_crawl_delay = models.BooleanField(
        default=True,
        help_text=(
            "When enabled, the worker respects crawl_delay_seconds from the "
            "local ruleset between page requests (CLAUDE.md §9)."
        ),
    )
    user_agents = models.JSONField(default=list)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="crawl_sources",
    )

    class Meta:
        db_table = "crawling_source"
        ordering = ["name"]

    def __str__(self):
        return self.name


class CrawlRuleVersion(TimeStampedModel):
    """
    Versioned crawl rule for a source.

    Canary fields:
      is_canary         — this version is in canary evaluation
      canary_pct        — percentage of tasks routed to this version (default 5)
      canary_started_at — when the canary window began (30-min window)

    request_headers is encrypted at rest (may contain auth tokens/API keys).
    """

    source = models.ForeignKey(
        CrawlSource, on_delete=models.PROTECT, related_name="rule_versions"
    )
    version_number = models.PositiveIntegerField()
    version_note = models.CharField(max_length=500, blank=True)

    url_pattern = models.CharField(max_length=1000)
    parameters = models.JSONField(default=dict)
    pagination_config = models.JSONField(default=dict)
    request_headers = EncryptedTextField(blank=True, default="")

    is_active = models.BooleanField(default=False, db_index=True)
    is_canary = models.BooleanField(default=False, db_index=True)
    canary_pct = models.PositiveSmallIntegerField(default=5)
    canary_started_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="crawl_rule_versions",
    )

    class Meta:
        db_table = "crawling_rule_version"
        ordering = ["source", "-version_number"]
        unique_together = [("source", "version_number")]

    def __str__(self):
        canary = " [CANARY]" if self.is_canary else ""
        return f"{self.source.name} v{self.version_number}{canary}"


# ─────────────────────────────────────────────────────────────────────────────
# Task queue
# ─────────────────────────────────────────────────────────────────────────────

class CrawlTask(TimeStampedModel):
    """
    A single crawl job — one URL to fetch and process.

    fingerprint — deterministic SHA-256 of (url + sorted params + relevant headers).
                  Duplicate fingerprints are rejected at scheduling time.
    checkpoint_page — last successfully processed page number (resumes from here).
    next_retry_at   — computed by exponential backoff: 10s/30s/2m/10m.
    priority        — lower number = higher priority (0 is highest).
    """

    source = models.ForeignKey(
        CrawlSource, on_delete=models.PROTECT, related_name="tasks"
    )
    rule_version = models.ForeignKey(
        CrawlRuleVersion, on_delete=models.PROTECT, related_name="tasks"
    )
    fingerprint = models.CharField(max_length=64, unique=True, db_index=True)
    url = models.CharField(max_length=2000)
    status = models.CharField(
        max_length=20,
        choices=CrawlTaskStatus.choices,
        default=CrawlTaskStatus.PENDING,
        db_index=True,
    )
    priority = models.SmallIntegerField(default=0, db_index=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True, db_index=True)
    checkpoint_page = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "crawling_task"
        ordering = ["priority", "created_at"]
        indexes = [
            models.Index(fields=["status", "next_retry_at"]),
            models.Index(fields=["source", "status"]),
        ]

    def __str__(self):
        return f"CrawlTask({self.status}) {self.url[:80]}"


# ─────────────────────────────────────────────────────────────────────────────
# Request log
# ─────────────────────────────────────────────────────────────────────────────

class CrawlRequestLog(TimeStampedModel):
    """
    One row per HTTP request made by the crawler.

    request_headers — stored with sensitive values masked (Bearer tokens,
    API keys replaced with [REDACTED]) before writing.
    Keeps the last 20 samples for the visual debugger.
    """

    task = models.ForeignKey(
        CrawlTask, on_delete=models.CASCADE, related_name="request_logs"
    )
    request_url = models.CharField(max_length=2000)
    request_headers = models.TextField(blank=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_snippet = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "crawling_request_log"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"[{self.response_status}] {self.request_url[:60]} ({self.duration_ms}ms)"


# ─────────────────────────────────────────────────────────────────────────────
# Per-source quota
# ─────────────────────────────────────────────────────────────────────────────

class SourceQuota(TimeStampedModel):
    """
    Rate-limit quota tracker for a crawl source.

    One row per source — updated inside a SELECT FOR UPDATE transaction.

    current_count — number of requests issued in the current rpm window.
    window_start  — when the current 60-second window began.
    held_until    — if set, quota is "held" (auto-release after 15 minutes).
    """

    source = models.OneToOneField(
        CrawlSource, on_delete=models.CASCADE, related_name="quota"
    )
    rpm_limit = models.PositiveIntegerField(default=60)
    current_count = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField(null=True, blank=True)
    held_until = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "crawling_source_quota"

    def __str__(self):
        return f"Quota({self.source.name}): {self.current_count}/{self.rpm_limit} rpm"
