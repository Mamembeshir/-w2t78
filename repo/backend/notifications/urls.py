"""
notifications/urls.py — URL configuration for the notifications app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    NotificationViewSet,
    OutboundQueuedView,
    SubscriptionViewSet,
    digest_schedule,
)

router = DefaultRouter()
router.register(r"subscriptions", SubscriptionViewSet, basename="notification-subscription")
router.register(r"inbox", NotificationViewSet, basename="notification-inbox")
router.register(r"outbound/queued", OutboundQueuedView, basename="notification-outbound")

urlpatterns = [
    path("", include(router.urls)),
    path("digest/", digest_schedule, name="notification-digest"),
]
