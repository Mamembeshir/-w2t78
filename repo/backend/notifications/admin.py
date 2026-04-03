from django.contrib import admin

from .models import DigestSchedule, Notification, NotificationSubscription, OutboundMessage


@admin.register(NotificationSubscription)
class NotificationSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "event_type", "threshold_value", "is_active")
    list_filter = ("event_type", "is_active")
    search_fields = ("user__username",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "event_type", "title", "is_read", "created_at")
    list_filter = ("event_type", "is_read")
    search_fields = ("user__username", "title")
    ordering = ("-created_at",)


@admin.register(OutboundMessage)
class OutboundMessageAdmin(admin.ModelAdmin):
    list_display = ("notification", "channel", "status", "queued_at", "sent_at")
    list_filter = ("channel", "status")
    ordering = ("-queued_at",)


@admin.register(DigestSchedule)
class DigestScheduleAdmin(admin.ModelAdmin):
    list_display = ("user", "send_time", "last_sent_at")
    search_fields = ("user__username",)
