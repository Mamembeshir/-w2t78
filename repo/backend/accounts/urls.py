"""
accounts/urls.py — URL patterns for auth and user management.

Mounted at /api/ by config/urls.py, giving:
  POST /api/auth/login/
  POST /api/auth/logout/
  POST /api/auth/refresh/
  GET  /api/auth/me/
  GET  /api/users/
  POST /api/users/
  GET  /api/users/{id}/
  PUT  /api/users/{id}/
  PATCH /api/users/{id}/
  POST /api/users/{id}/reset-password/
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, LogoutView, MeView, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    # ── Auth ─────────────────────────────────────────────────────────────────
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    # ── Users (Admin only) ───────────────────────────────────────────────────
    path("", include(router.urls)),
]
