"""
audit/middleware.py — AuditLogMiddleware

Logs every mutating HTTP request (POST/PUT/PATCH/DELETE) made by an
authenticated user to the AuditLog table.

Captured fields:
  user         — the authenticated request.user
  action       — CREATE | UPDATE | DELETE (derived from HTTP method)
  model_name   — extracted from URL path segment after /api/
  object_id    — path segment after model_name if it looks like an ID
  changes      — parsed + masked request body (JSON) or raw string
  ip_address   — REMOTE_ADDR or first X-Forwarded-For hop

Skipped paths:
  /api/auth/*  — login/logout/refresh are not model mutations
  /api/health/ — health probe
  /admin/*     — Django admin has its own logging

The middleware never raises — any error inside _write_log is swallowed so
that a logging failure cannot break a real request.
"""
import json
import logging

from config.logging_filters import _mask

logger = logging.getLogger(__name__)

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_SKIP_PREFIXES = (
    "/api/auth/",
    "/api/health/",
    "/admin/",
)

_METHOD_TO_ACTION = {
    "POST": "CREATE",
    "PUT": "UPDATE",
    "PATCH": "UPDATE",
    "DELETE": "DELETE",
}


def _get_ip(request):
    """Return the best-available client IP address."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or None


def _parse_path(path: str):
    """
    Extract (model_name, object_id) from a URL path.

    Examples:
      /api/users/          → ("users", "")
      /api/users/5/        → ("users", "5")
      /api/users/5/reset-password/ → ("users", "5")
      /api/warehouses/3/bins/ → ("warehouses", "3")
    """
    parts = [p for p in path.strip("/").split("/") if p]
    # Drop leading "api" segment
    if parts and parts[0] == "api":
        parts = parts[1:]

    model_name = parts[0] if parts else "unknown"
    object_id = ""
    if len(parts) > 1:
        # Use the second segment as object_id if it looks like an ID (numeric or UUID-ish)
        candidate = parts[1]
        if candidate.isdigit() or (len(candidate) == 36 and candidate.count("-") == 4):
            object_id = candidate

    return model_name, object_id


def _parse_body(request):
    """
    Read + mask the request body.  Returns a dict (or {"_raw": "..."} fallback).
    Never raises.
    """
    try:
        raw = request.body.decode("utf-8") if request.body else ""
    except Exception:
        return {}

    if not raw:
        return {}

    masked = _mask(raw)
    try:
        return json.loads(masked)
    except (json.JSONDecodeError, ValueError):
        return {"_raw": masked[:2000]}  # truncate very long non-JSON bodies


class AuditLogMiddleware:
    """
    Process-response middleware — writes to AuditLog after the view returns.
    Registered in settings.MIDDLEWARE after AuthenticationMiddleware so that
    request.user is already resolved.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            if (
                request.method in _MUTATING_METHODS
                and not any(request.path.startswith(p) for p in _SKIP_PREFIXES)
                and hasattr(request, "user")
                and request.user.is_authenticated
                and response.status_code < 500
            ):
                self._write_log(request, response)
        except Exception:
            # Audit logging must never crash the request pipeline
            logger.exception("AuditLogMiddleware: unexpected error writing audit log.")

        return response

    def _write_log(self, request, response):
        from audit.models import AuditLog  # deferred import to avoid circular import at startup

        model_name, object_id = _parse_path(request.path)
        action = _METHOD_TO_ACTION.get(request.method, request.method)
        changes = _parse_body(request)
        ip = _get_ip(request)

        AuditLog._default_manager.create(
            user=request.user,
            action=action,
            model_name=model_name,
            object_id=object_id,
            changes=changes,
            ip_address=ip or None,
        )
