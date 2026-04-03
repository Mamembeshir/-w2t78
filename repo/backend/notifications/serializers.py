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
