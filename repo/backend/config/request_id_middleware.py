"""
config/request_id_middleware.py

Attaches a unique request ID to every request for end-to-end tracing (SPEC.md).

- Reads  X-Request-ID from the incoming request (propagated by load-balancers /
  API clients) and reuses it; falls back to a freshly generated UUID4.
- Stores the ID on request.request_id for use in views and logging.
- Echoes it back as X-Request-ID on every response so callers can correlate
  logs without grepping timestamps.
"""
import uuid


HEADER = "X-Request-ID"


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # HTTP headers arrive as HTTP_<UPPER_NAME> in request.META
        request_id = request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        request.request_id = request_id

        response = self.get_response(request)
        response[HEADER] = request_id
        return response
