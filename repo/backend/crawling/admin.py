from django.contrib import admin

from .models import CrawlRequestLog, CrawlRuleVersion, CrawlSource, CrawlTask, SourceQuota


@admin.register(CrawlSource)
class CrawlSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "base_url", "rate_limit_rpm", "crawl_delay_seconds", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "base_url")


@admin.register(CrawlRuleVersion)
class CrawlRuleVersionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "source", "version_number", "is_active", "is_canary", "canary_pct")
    list_filter = ("is_active", "is_canary", "source")
    search_fields = ("source__name", "url_pattern")
    ordering = ("source", "-version_number")


@admin.register(CrawlTask)
class CrawlTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "status", "priority", "attempt_count", "next_retry_at", "created_at")
    list_filter = ("status", "source")
    search_fields = ("fingerprint", "url")
    ordering = ("priority", "created_at")


@admin.register(CrawlRequestLog)
class CrawlRequestLogAdmin(admin.ModelAdmin):
    list_display = ("task", "request_url", "response_status", "duration_ms", "timestamp")
    list_filter = ("response_status",)
    search_fields = ("request_url",)
    ordering = ("-timestamp",)


@admin.register(SourceQuota)
class SourceQuotaAdmin(admin.ModelAdmin):
    list_display = ("source", "rpm_limit", "current_count", "window_start", "held_until")
