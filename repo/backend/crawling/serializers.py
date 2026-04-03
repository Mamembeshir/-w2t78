"""
crawling/serializers.py — Crawl source, rule version, task, and log serializers.
"""
import json

from rest_framework import serializers

from .models import (
    CrawlRequestLog,
    CrawlRuleVersion,
    CrawlSource,
    CrawlTask,
    CrawlTaskStatus,
    SourceQuota,
)


# ─────────────────────────────────────────────────────────────────────────────
# Source
# ─────────────────────────────────────────────────────────────────────────────

class CrawlSourceSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True, allow_null=True)
    active_rule_version = serializers.SerializerMethodField()

    class Meta:
        model = CrawlSource
        fields = [
            "id", "name", "base_url", "is_active",
            "rate_limit_rpm", "crawl_delay_seconds", "user_agents",
            "created_by", "created_by_username",
            "active_rule_version",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_by_username", "active_rule_version",
                            "created_at", "updated_at"]

    def get_active_rule_version(self, obj) -> int | None:
        rv = obj.rule_versions.filter(is_active=True).first()
        return rv.pk if rv else None


# ─────────────────────────────────────────────────────────────────────────────
# Rule Version
# ─────────────────────────────────────────────────────────────────────────────

class CrawlRuleVersionSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True, allow_null=True)
    # request_headers is encrypted — never expose raw value; return masked summary
    request_headers_masked = serializers.SerializerMethodField()
    canary_error_rate = serializers.SerializerMethodField()

    class Meta:
        model = CrawlRuleVersion
        fields = [
            "id", "source", "version_number", "version_note",
            "url_pattern", "parameters", "pagination_config",
            "request_headers",   # write-only in create/update
            "request_headers_masked",
            "is_active", "is_canary", "canary_pct", "canary_started_at",
            "created_by", "created_by_username",
            "canary_error_rate",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "version_number", "is_active", "is_canary",
            "canary_pct", "canary_started_at",
            "created_by", "created_by_username",
            "request_headers_masked", "canary_error_rate",
            "created_at", "updated_at",
        ]
        extra_kwargs = {
            "request_headers": {"write_only": True, "required": False},
            "version_note": {"required": True},
        }

    def get_request_headers_masked(self, obj) -> dict:
        """Return header keys with masked values for display."""
        if not obj.request_headers:
            return {}
        try:
            headers = json.loads(obj.request_headers)
            return {k: "[REDACTED]" for k in headers}
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_canary_error_rate(self, obj) -> float | None:
        """Current error rate for canary versions."""
        if not obj.is_canary:
            return None
        total = obj.tasks.filter(
            status__in=[CrawlTaskStatus.COMPLETED, CrawlTaskStatus.FAILED]
        ).count()
        if total == 0:
            return 0.0
        failed = obj.tasks.filter(status=CrawlTaskStatus.FAILED).count()
        return round(failed / total * 100, 2)


class CrawlRuleVersionCreateSerializer(serializers.ModelSerializer):
    """Used only on POST — version_note is required, source comes from URL."""

    class Meta:
        model = CrawlRuleVersion
        fields = [
            "version_note", "url_pattern", "parameters",
            "pagination_config", "request_headers",
        ]
        extra_kwargs = {
            "version_note": {"required": True},
            "request_headers": {"required": False},
        }

    def validate_request_headers(self, value):
        """Ensure request_headers is either empty or valid JSON representing a flat dict."""
        if not value:
            return value
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            raise serializers.ValidationError(
                "request_headers must be a valid JSON object (e.g. {\"Authorization\": \"Bearer token\"})."
            )
        if not isinstance(parsed, dict):
            raise serializers.ValidationError("request_headers must be a JSON object, not an array or scalar.")
        for k, v in parsed.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise serializers.ValidationError("request_headers keys and values must all be strings.")
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Task
# ─────────────────────────────────────────────────────────────────────────────

class CrawlTaskSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source="source.name", read_only=True)
    rule_version_number = serializers.IntegerField(source="rule_version.version_number", read_only=True)

    class Meta:
        model = CrawlTask
        fields = [
            "id", "source", "source_name", "rule_version", "rule_version_number",
            "fingerprint", "url", "status", "priority",
            "attempt_count", "next_retry_at", "checkpoint_page",
            "last_error", "started_at", "completed_at",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "fingerprint", "status", "attempt_count", "next_retry_at",
            "checkpoint_page", "last_error", "started_at", "completed_at",
            "source_name", "rule_version_number",
            "created_at", "updated_at",
        ]


class EnqueueTaskSerializer(serializers.Serializer):
    source_id = serializers.IntegerField()
    url = serializers.URLField(max_length=2000)
    parameters = serializers.DictField(child=serializers.CharField(), required=False, default=dict)
    priority = serializers.IntegerField(default=0, min_value=-10, max_value=10)


# ─────────────────────────────────────────────────────────────────────────────
# Request Log
# ─────────────────────────────────────────────────────────────────────────────

class CrawlRequestLogSerializer(serializers.ModelSerializer):
    task_url = serializers.CharField(source="task.url", read_only=True)
    source_name = serializers.CharField(source="task.source.name", read_only=True)

    class Meta:
        model = CrawlRequestLog
        fields = [
            "id", "task", "task_url", "source_name",
            "request_url", "request_headers",
            "response_status", "response_snippet", "duration_ms",
            "timestamp",
        ]
        read_only_fields = fields


# ─────────────────────────────────────────────────────────────────────────────
# Quota
# ─────────────────────────────────────────────────────────────────────────────

class SourceQuotaSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source="source.name", read_only=True)
    utilization_pct = serializers.SerializerMethodField()

    class Meta:
        model = SourceQuota
        fields = [
            "id", "source", "source_name", "rpm_limit", "current_count",
            "window_start", "held_until", "utilization_pct",
        ]
        read_only_fields = fields

    def get_utilization_pct(self, obj) -> float:
        if obj.rpm_limit == 0:
            return 0.0
        return round(obj.current_count / obj.rpm_limit * 100, 1)
