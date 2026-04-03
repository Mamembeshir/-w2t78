"""
config/urls.py — root URL configuration
API routes added per phase as apps are built.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.db import connection, OperationalError


def health(request):
    """
    GET /api/health/
    Returns 200 if Django + DB + basic config are healthy.
    Used by run_test.sh to gate service startup.
    """
    db_ok = True
    try:
        connection.ensure_connection()
    except OperationalError:
        db_ok = False

    payload = {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
    }
    status_code = 200 if db_ok else 503
    return JsonResponse(payload, status=status_code)


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
    # path("api/crawl/", include("crawling.urls")),
    # Notifications — Phase 7
    # path("api/notifications/", include("notifications.urls")),
]
