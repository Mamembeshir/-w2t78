"""
notifications/serializers.py — DRF serializers for the notifications app.
"""
from rest_framework import serializers

from .models import (
    DigestSchedule,
    EventType,
    Notification,
    NotificationSubscription,
    OutboundMessage,
    SystemSettings,
)


class NotificationSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSubscription
        fields = ["id", "event_type", "threshold_value", "is_active", "created_at"]
        read_only_fields = ["id", "is_active", "created_at"]

    def validate_event_type(self, value: str) -> str:
        valid = {choice[0] for choice in EventType.choices}
        if value not in valid:
            raise serializers.ValidationError(
                f"Invalid event_type. Valid choices: {sorted(valid)}"
            )
        return value


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "event_type",
            "title",
            "body",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields


class OutboundMessageSerializer(serializers.ModelSerializer):
    notification_title = serializers.CharField(
        source="notification.title", read_only=True
    )
    notification_event_type = serializers.CharField(
        source="notification.event_type", read_only=True
    )
    user_username = serializers.CharField(
        source="notification.user.username", read_only=True
    )

    class Meta:
        model = OutboundMessage
        fields = [
            "id",
            "notification",
            "notification_title",
            "notification_event_type",
            "user_username",
            "channel",
            "status",
            "queued_at",
            "sent_at",
            "error",
        ]
        read_only_fields = fields


class DigestScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DigestSchedule
        fields = ["id", "send_time", "last_sent_at", "updated_at"]
        read_only_fields = ["id", "last_sent_at", "updated_at"]


class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        fields = ["smtp_host", "smtp_port", "smtp_use_tls", "sms_gateway_url"]

    def validate_smtp_host(self, value: str) -> str:
        """
        Reject SMTP hosts outside the local network.

        Offline-only policy (CLAUDE.md): mail relays must be locally hosted.
        Allowed: empty (unconfigured), localhost, RFC-1918/loopback/link-local
        IPs, unqualified hostnames (no dots), and *.local / *.internal names.
        """
        import ipaddress

        if not value:
            return value

        hostname = value.strip().lower()

        if (
            hostname == "localhost"
            or "." not in hostname
            or hostname.endswith(".local")
            or hostname.endswith(".internal")
        ):
            return value

        try:
            addr = ipaddress.ip_address(hostname)
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                return value
        except ValueError:
            pass

        raise serializers.ValidationError(
            "SMTP host must be a local/private address "
            "(e.g. 192.168.x.x, 10.x.x.x, 172.16-31.x.x, localhost, or an "
            "unqualified internal hostname). External internet addresses are "
            "not permitted by the offline-only policy."
        )

    def validate_sms_gateway_url(self, value: str) -> str:
        """
        Reject URLs pointing outside the local network.

        Offline-only policy (CLAUDE.md): no internet dependency — gateways must
        be locally hosted. Allowed: localhost, RFC-1918 private IPs, link-local
        IPs, unqualified hostnames (no dots), and *.local / *.internal names.
        """
        import ipaddress
        from urllib.parse import urlparse

        if not value:
            return value

        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https"):
            raise serializers.ValidationError(
                "Only http:// and https:// schemes are allowed for the SMS gateway."
            )

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise serializers.ValidationError(
                "SMS gateway URL must include a hostname."
            )

        # Unqualified hostnames (no dots), *.local, *.internal, and localhost
        # are always considered local.
        if (
            hostname == "localhost"
            or "." not in hostname
            or hostname.endswith(".local")
            or hostname.endswith(".internal")
        ):
            return value

        # RFC-1918 / loopback / link-local IP ranges
        try:
            addr = ipaddress.ip_address(hostname)
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                return value
        except ValueError:
            pass  # Not a bare IP — fall through to rejection

        raise serializers.ValidationError(
            "SMS gateway URL must point to a local/private address "
            "(e.g. 192.168.x.x, 10.x.x.x, 172.16-31.x.x, localhost, or an "
            "unqualified internal hostname). External internet addresses are "
            "not permitted by the offline-only policy."
        )
