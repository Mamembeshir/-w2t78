"""
config/urls.py — root URL configuration
API routes added per phase as apps are built.
"""
import os

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.db import connection, OperationalError


def health(request):
    """
    GET /api/health/
    Returns 200 if Django + DB + Redis are healthy.
    Used by run_test.sh to gate service startup.
    Checks Redis via a direct redis-py ping (not the application cache layer)
    so the result is not affected by the DummyCache backend used in tests.
    """
    db_ok = True
    try:
        connection.ensure_connection()
    except OperationalError:
        db_ok = False

    redis_ok = True
    try:
        import redis as _redis
        _r = _redis.from_url(
            os.environ.get("REDIS_URL", "redis://redis:6379/0"),
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        redis_ok = _r.ping()
    except Exception:
        redis_ok = False

    all_ok = db_ok and redis_ok
    payload = {
        "status": "ok" if all_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
    }
    return JsonResponse(payload, status=200 if all_ok else 503)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    # Auth + User management (Phase 3)
    path("api/", include("accounts.urls")),
    # Warehouse — Phase 5
    path("api/", include("warehouse.urls")),
    # Inventory — Phase 5
    path("api/", include("inventory.urls")),
    # Crawling — Phase 6
    path("api/crawl/", include("crawling.urls")),
    # Notifications — Phase 7
    path("api/notifications/", include("notifications.urls")),
    # Audit log — Phase 9
    path("api/", include("audit.urls")),
]
