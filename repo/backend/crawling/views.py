"""
crawling/views.py — Crawl source, rule version, task, and debug API views.
"""
import hashlib
import json

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin, IsProcurementAnalyst

from .models import (
    CrawlRequestLog,
    CrawlRuleVersion,
    CrawlSource,
    CrawlTask,
    CrawlTaskStatus,
    SourceQuota,
)
from .serializers import (
    CrawlRequestLogSerializer,
    CrawlRuleVersionCreateSerializer,
    CrawlRuleVersionSerializer,
    CrawlSourceSerializer,
    CrawlTaskSerializer,
    EnqueueTaskSerializer,
    SourceQuotaSerializer,
)


def _compute_fingerprint(url: str, params: dict, headers: dict | None = None) -> str:
    """SHA-256 of url + sorted params JSON + sorted headers JSON (CLAUDE.md §3).

    'relevant headers' are the request_headers from the active rule version —
    e.g. Authorization, custom API keys — that differentiate crawl requests.
    """
    sorted_params = json.dumps(dict(sorted(params.items())), sort_keys=True)
    sorted_headers = json.dumps(dict(sorted((headers or {}).items())), sort_keys=True)
    raw = f"{url}|{sorted_params}|{sorted_headers}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# 6.1 Crawl Source
# ─────────────────────────────────────────────────────────────────────────────

class CrawlSourceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/crawl/sources/         — list (any authenticated)
    POST /api/crawl/sources/         — create (Procurement Analyst / Admin)
    GET  /api/crawl/sources/{id}/    — detail
    PUT/PATCH                        — update (Procurement Analyst / Admin)
    GET  /api/crawl/sources/{id}/rule-versions/ — list versions
    GET  /api/crawl/sources/{id}/debug-log/     — last 20 request logs
    GET  /api/crawl/sources/{id}/quota/         — current quota state
    """

    serializer_class = CrawlSourceSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        return CrawlSource.objects.all().order_by("name")

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update"):
            return [IsProcurementAnalyst()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["get", "post"], url_path="rule-versions")
    def rule_versions(self, request, pk=None):
        source = self.get_object()

        if request.method == "POST":
            ser = CrawlRuleVersionCreateSerializer(data=request.data)
            ser.is_valid(raise_exception=True)

            last = source.rule_versions.order_by("-version_number").first()
            version_number = (last.version_number + 1) if last else 1

            version = CrawlRuleVersion.objects.create(
                source=source,
                version_number=version_number,
                created_by=request.user,
                **ser.validated_data,
            )
            return Response(CrawlRuleVersionSerializer(version).data, status=status.HTTP_201_CREATED)

        qs = source.rule_versions.order_by("-version_number")
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(CrawlRuleVersionSerializer(page, many=True).data)
        return Response(CrawlRuleVersionSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"], url_path="debug-log")
    def debug_log(self, request, pk=None):
        source = self.get_object()
        task_ids = source.tasks.values_list("id", flat=True)
        logs = (
            CrawlRequestLog.objects.filter(task__in=task_ids)
            .select_related("task")
            .order_by("-timestamp")[:20]
        )
        return Response(CrawlRequestLogSerializer(logs, many=True).data)

    @action(detail=True, methods=["get"], url_path="quota")
    def quota(self, request, pk=None):
        source = self.get_object()
        try:
            q = source.quota
        except SourceQuota.DoesNotExist:
            return Response({"current_count": 0, "rpm_limit": source.rate_limit_rpm})
        return Response(SourceQuotaSerializer(q).data)


# ─────────────────────────────────────────────────────────────────────────────
# 6.2 Rule Version actions
# ─────────────────────────────────────────────────────────────────────────────

class CrawlRuleVersionViewSet(
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/crawl/rule-versions/{id}/          — detail
    POST /api/crawl/rule-versions/{id}/activate/ — set as active
    POST /api/crawl/rule-versions/{id}/canary/   — start canary (5%, 30 min)
    POST /api/crawl/rule-versions/{id}/rollback/ — rollback canary
    """

    serializer_class = CrawlRuleVersionSerializer
    permission_classes = [IsProcurementAnalyst]

    def get_queryset(self):
        return CrawlRuleVersion.objects.all()

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        version = self.get_object()
        source = version.source

        # Deactivate all other versions for this source (including canary)
        source.rule_versions.exclude(pk=version.pk).update(is_active=False, is_canary=False)

        version.is_active = True
        version.is_canary = False
        version.canary_started_at = None
        version.save(update_fields=["is_active", "is_canary", "canary_started_at"])

        return Response(CrawlRuleVersionSerializer(version).data)

    @action(detail=True, methods=["post"], url_path="canary")
    def start_canary(self, request, pk=None):
        version = self.get_object()

        if version.is_active:
            return Response(
                {"code": "already_active", "message": "Cannot canary an already-active version."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if version.is_canary:
            return Response(
                {"code": "already_canary", "message": "This version is already in canary."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ensure there is an active version to fall back to
        active = version.source.rule_versions.filter(is_active=True).first()
        if not active:
            return Response(
                {"code": "no_active_version", "message": "No active version to fall back to."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        version.is_canary = True
        version.canary_started_at = timezone.now()
        version.save(update_fields=["is_canary", "canary_started_at"])

        return Response(CrawlRuleVersionSerializer(version).data)

    @action(detail=True, methods=["post"], url_path="rollback")
    def rollback(self, request, pk=None):
        version = self.get_object()

        if not version.is_canary:
            return Response(
                {"code": "not_canary", "message": "This version is not currently in canary."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .tasks import _rollback_canary
        _rollback_canary(version, reason="manual rollback")

        version.refresh_from_db()
        return Response(CrawlRuleVersionSerializer(version).data)


# ─────────────────────────────────────────────────────────────────────────────
# 6.3 Task Scheduler
# ─────────────────────────────────────────────────────────────────────────────

class CrawlTaskViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/crawl/tasks/       — list (filterable by status, source)
    POST /api/crawl/tasks/       — enqueue a new crawl task
    POST /api/crawl/tasks/{id}/retry/ — retry a FAILED task
    """

    serializer_class = CrawlTaskSerializer
    permission_classes = [IsProcurementAnalyst]

    def get_queryset(self):
        qs = CrawlTask.objects.select_related("source", "rule_version").all()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        source_id = self.request.query_params.get("source_id")
        if source_id:
            qs = qs.filter(source_id=source_id)
        return qs.order_by("priority", "-created_at")

    def create(self, request):
        ser = EnqueueTaskSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        source = get_object_or_404(CrawlSource, pk=d["source_id"], is_active=True)

        # Require an active rule version
        rule_version = source.rule_versions.filter(is_active=True).first()
        if not rule_version:
            return Response(
                {"code": "no_active_rule", "message": "Source has no active rule version."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Include rule-version request_headers in fingerprint (CLAUDE.md §3)
        rule_headers: dict = {}
        if rule_version.request_headers:
            try:
                rule_headers = json.loads(rule_version.request_headers)
            except (json.JSONDecodeError, TypeError):
                pass

        fingerprint = _compute_fingerprint(d["url"], d.get("parameters", {}), rule_headers)

        # Idempotency: return existing task if fingerprint matches
        existing = CrawlTask.objects.filter(fingerprint=fingerprint).first()
        if existing:
            return Response(
                {
                    "deduplicated": True,
                    "task": CrawlTaskSerializer(existing).data,
                },
                status=status.HTTP_200_OK,
            )

        task = CrawlTask.objects.create(
            source=source,
            rule_version=rule_version,
            fingerprint=fingerprint,
            url=d["url"],
            priority=d.get("priority", 0),
            status=CrawlTaskStatus.PENDING,
        )

        # Trigger the worker on the shard queue for this source
        from .worker import execute_crawl_task
        from .routing import crawl_queue_for_source
        execute_crawl_task.apply_async(
            args=[task.pk],
            queue=crawl_queue_for_source(task.source_id),
        )

        return Response(
            {"deduplicated": False, "task": CrawlTaskSerializer(task).data},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        task = get_object_or_404(CrawlTask, pk=pk, status=CrawlTaskStatus.FAILED)
        task.status = CrawlTaskStatus.PENDING
        task.attempt_count = 0
        task.last_error = ""
        task.next_retry_at = None
        task.save(update_fields=["status", "attempt_count", "last_error", "next_retry_at"])

        from .worker import execute_crawl_task
        from .routing import crawl_queue_for_source
        execute_crawl_task.apply_async(
            args=[task.pk],
            queue=crawl_queue_for_source(task.source_id),
        )

        return Response(CrawlTaskSerializer(task).data)
