"""
notifications/views.py — Notification inbox, subscriptions, and outbound API.

Routes (all prefixed /api/notifications/):
  GET  subscriptions/           — list my subscriptions
  POST subscriptions/           — subscribe to an event type
  DELETE subscriptions/{id}/   — unsubscribe

  GET  inbox/                  — paginated list (filters: unread, event_type, date_from)
  GET  unread-count/           — integer count for bell badge
  POST {id}/read/              — mark one notification as read
  POST read-all/               — mark all as read

  GET  outbound/queued/        — admin only: list QUEUED outbound messages
  GET  digest/                 — my digest schedule
  PATCH digest/                — update send_time or toggle
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdmin

from .models import (
    DigestSchedule,
    Notification,
    NotificationSubscription,
    OutboundMessage,
    OutboundStatus,
    SystemSettings,
)
from .serializers import (
    DigestScheduleSerializer,
    NotificationSerializer,
    NotificationSubscriptionSerializer,
    OutboundMessageSerializer,
    SystemSettingsSerializer,
)


# ─────────────────────────────────────────────────────────────────────────────
# 7.2 Subscriptions
# ─────────────────────────────────────────────────────────────────────────────

class SubscriptionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/notifications/subscriptions/         — list mine
    POST /api/notifications/subscriptions/         — subscribe
    DELETE /api/notifications/subscriptions/{id}/  — unsubscribe
    """

    serializer_class = NotificationSubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return NotificationSubscription.objects.filter(
            user=self.request.user
        ).order_by("event_type")

    def perform_create(self, serializer):
        # Upsert: if inactive subscription exists, re-activate
        existing = NotificationSubscription.objects.filter(
            user=self.request.user,
            event_type=serializer.validated_data["event_type"],
        ).first()

        if existing:
            existing.is_active = True
            existing.threshold_value = serializer.validated_data.get("threshold_value")
            existing.save(update_fields=["is_active", "threshold_value", "updated_at"])
            # Raise a non-error response by returning early after raising
            raise _SubscriptionExists(existing)

        serializer.save(user=self.request.user, is_active=True)

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            self.perform_create(ser)
        except _SubscriptionExists as e:
            return Response(
                NotificationSubscriptionSerializer(e.instance).data,
                status=status.HTTP_200_OK,
            )
        headers = self.get_success_headers(ser.data)
        return Response(ser.data, status=status.HTTP_201_CREATED, headers=headers)


class _SubscriptionExists(Exception):
    def __init__(self, instance):
        self.instance = instance


# ─────────────────────────────────────────────────────────────────────────────
# 7.3 Inbox
# ─────────────────────────────────────────────────────────────────────────────

class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/notifications/inbox/        — paginated list (filters below)
    GET  /api/notifications/unread-count/ — badge count
    POST /api/notifications/{id}/read/    — mark as read
    POST /api/notifications/read-all/     — mark all as read
    """

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)

        # Filter: unread only
        unread = self.request.query_params.get("unread")
        if unread in ("1", "true", "True"):
            qs = qs.filter(is_read=False)

        # Filter: event_type
        event_type = self.request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)

        # Filter: date_from (ISO 8601)
        date_from = self.request.query_params.get("date_from")
        if date_from:
            try:
                from django.utils.dateparse import parse_datetime
                dt = parse_datetime(date_from)
                if dt:
                    qs = qs.filter(created_at__gte=dt)
            except ValueError:
                pass

        return qs.order_by("-created_at")

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        return Response({"unread_count": count})

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        n = self.get_object()
        if not n.is_read:
            n.is_read = True
            n.read_at = timezone.now()
            n.save(update_fields=["is_read", "read_at"])
        return Response(NotificationSerializer(n).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request):
        now = timezone.now()
        updated = Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True, read_at=now)
        return Response({"marked_read": updated})


# ─────────────────────────────────────────────────────────────────────────────
# 7.5 Outbound (admin)
# ─────────────────────────────────────────────────────────────────────────────

class OutboundQueuedView(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/notifications/outbound/queued/ — Admin: list queued outbound messages.
    GET /api/notifications/outbound/queued/{id}/ — detail
    """

    serializer_class = OutboundMessageSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return OutboundMessage.objects.filter(
            status=OutboundStatus.QUEUED
        ).select_related("notification__user").order_by("-queued_at")


# ─────────────────────────────────────────────────────────────────────────────
# 7.7 Digest schedule
# ─────────────────────────────────────────────────────────────────────────────

@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def digest_schedule(request):
    """
    GET  /api/notifications/digest/   — get my digest schedule
    PATCH /api/notifications/digest/  — update send_time
    """
    schedule, _ = DigestSchedule.objects.get_or_create(user=request.user)

    if request.method == "PATCH":
        ser = DigestScheduleSerializer(schedule, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    return Response(DigestScheduleSerializer(schedule).data)


# ─────────────────────────────────────────────────────────────────────────────
# System Settings (admin-only)
# ─────────────────────────────────────────────────────────────────────────────

@api_view(["GET", "PATCH"])
@permission_classes([IsAdmin])
def system_settings(request):
    """
    GET   /api/settings/   — retrieve current gateway configuration
    PATCH /api/settings/   — update smtp/sms settings
    """
    settings_obj = SystemSettings.get()

    if request.method == "PATCH":
        ser = SystemSettingsSerializer(settings_obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    return Response(SystemSettingsSerializer(settings_obj).data)


@api_view(["POST"])
@permission_classes([IsAdmin])
def test_smtp(request):
    """
    POST /api/settings/test-smtp/
    Opens a real SMTP connection to the configured host and closes it.
    Returns 200 on success, 400 with {message} on failure.
    """
    s = SystemSettings.get()
    if not s.smtp_host:
        return Response({"message": "SMTP host is not configured."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        from django.core.mail.backends.smtp import EmailBackend
        backend = EmailBackend(
            host=s.smtp_host,
            port=s.smtp_port,
            use_tls=s.smtp_use_tls,
            fail_silently=False,
            timeout=10,
        )
        backend.open()
        backend.close()
        return Response({"message": "SMTP connection succeeded."})
    except Exception as exc:
        logger.warning("SMTP connectivity test failed for host %r: %s", s.smtp_host, exc)
        return Response(
            {"message": "SMTP connection failed. Check server logs for details."},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
@permission_classes([IsAdmin])
def test_sms(request):
    """
    POST /api/settings/test-sms/
    Sends a test POST to the configured SMS gateway URL.
    Returns 200 on success, 400 with {message} on failure.
    """
    s = SystemSettings.get()
    if not s.sms_gateway_url:
        return Response({"message": "SMS gateway URL is not configured."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        import requests as http_requests
        resp = http_requests.post(
            s.sms_gateway_url,
            json={"to": "test", "message": "Gateway connectivity test"},
            timeout=10,
        )
        resp.raise_for_status()
        return Response({"message": "SMS gateway test succeeded."})
    except Exception as exc:
        logger.warning("SMS gateway connectivity test failed for url %r: %s", s.sms_gateway_url, exc)
        return Response(
            {"message": "SMS gateway connection failed. Check server logs for details."},
            status=status.HTTP_400_BAD_REQUEST,
        )
