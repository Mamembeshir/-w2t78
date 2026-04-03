"""
accounts/views.py — Auth endpoints and user management API.

Endpoints
---------
POST /api/auth/login/               — returns JWT access + refresh + user object
POST /api/auth/logout/              — blacklists the supplied refresh token
POST /api/auth/refresh/             — issues new access token (simplejwt default)
GET  /api/auth/me/                  — returns current authenticated user
GET  /api/users/                    — list all users (Admin only)
POST /api/users/                    — create user (Admin only)
GET  /api/users/{id}/               — retrieve user (Admin only)
PUT  /api/users/{id}/               — update role/active (Admin only, no password)
PATCH /api/users/{id}/              — partial update (Admin only)
POST /api/users/{id}/reset-password/— reset user password (Admin only)
"""
import logging

from django.contrib.auth import authenticate
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .permissions import IsAdmin
from .serializers import PasswordResetSerializer, UserSerializer

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Auth views
# ─────────────────────────────────────────────────────────────────────────────

class LoginView(APIView):
    """
    POST /api/auth/login/

    Body: { "username": "...", "password": "..." }
    Returns: { "access": "...", "refresh": "...", "user": { id, username, role } }

    Rate-limited to 5 attempts per minute per IP (ScopedRateThrottle: "login").
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")

        if not username or not password:
            raise AuthenticationFailed("username and password are required.")

        user = authenticate(request, username=username, password=password)
        if user is None:
            raise AuthenticationFailed("Invalid credentials.")
        if not user.is_active:
            raise AuthenticationFailed("This account is disabled.")

        refresh = RefreshToken.for_user(user)

        logger.info("User '%s' logged in successfully.", username)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.pk,
                    "username": user.username,
                    "role": user.role,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
            }
        )


class LogoutView(APIView):
    """
    POST /api/auth/logout/

    Body: { "refresh": "<refresh_token>" }
    Blacklists the supplied refresh token.  Returns 204 on success or if
    the token is already blacklisted / invalid (idempotent).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        token_str = request.data.get("refresh", "")
        if token_str:
            try:
                token = RefreshToken(token_str)
                token.blacklist()
                logger.info("Refresh token blacklisted for user '%s'.", request.user.username)
            except TokenError:
                # Token already blacklisted, expired, or malformed — treat as success
                pass

        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """
    GET /api/auth/me/

    Returns the currently authenticated user's profile.
    Useful for the frontend to restore session state after a page reload.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "id": user.pk,
                "username": user.username,
                "role": user.role,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_active": user.is_active,
                "last_login": user.last_login,
                "date_joined": user.date_joined,
            }
        )


# ─────────────────────────────────────────────────────────────────────────────
# User management (Admin only)
# ─────────────────────────────────────────────────────────────────────────────

class UserViewSet(viewsets.ModelViewSet):
    """
    Admin-only CRUD for user accounts.

    DELETE is intentionally disabled — deactivate via PATCH is_active=false.
    """

    permission_classes = [IsAdmin]
    serializer_class = UserSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        return User.objects.all().order_by("username")

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        """
        POST /api/users/{id}/reset-password/
        Body: { "password": "<new_password>" }
        Admin only.  Validates against AUTH_PASSWORD_VALIDATORS.
        """
        user = self.get_object()
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_password = serializer.validated_data["password"]
        user.set_password(new_password)
        user.save(update_fields=["password"])

        logger.info(
            "Admin '%s' reset password for user '%s'.",
            request.user.username,
            user.username,
        )
        return Response({"detail": "Password updated successfully."})
