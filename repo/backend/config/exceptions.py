"""
config/exceptions.py
Standardized DRF error response format: { code, message, details }
All API errors go through this handler so clients get a consistent shape.
"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

# Map HTTP status → short error code string
_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    429: "too_many_requests",
    500: "internal_server_error",
}


def custom_exception_handler(exc, context):
    """
    Returns JSON in the shape:
      { "code": "...", "message": "...", "details": {...} }
    """
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception — Django will return 500
        logger.exception("Unhandled exception in %s", context.get("view"))
        return Response(
            {
                "code": "internal_server_error",
                "message": "An unexpected error occurred.",
                "details": {},
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    http_code = _STATUS_CODES.get(response.status_code, "error")

    # Flatten DRF's varied error structures into a consistent shape
    data = response.data
    if isinstance(data, list):
        message = "; ".join(str(e) for e in data)
        details = {}
    elif isinstance(data, dict):
        # Try to pull a top-level message
        message = (
            data.get("detail")
            or data.get("message")
            or _STATUS_CODES.get(response.status_code, "Error")
        )
        if hasattr(message, "code"):
            # ErrorDetail object
            message = str(message)
        details = {k: v for k, v in data.items() if k not in ("detail", "message")}
    else:
        message = str(data)
        details = {}

    response.data = {
        "code": http_code,
        "message": message,
        "details": details,
    }
    return response
