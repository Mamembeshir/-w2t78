"""
config/security_middleware.py
Injects Content-Security-Policy and other security headers on every response.
Keeps the CSP value in settings.CSP_HEADER so it's easy to audit in one place.
"""
from django.conf import settings


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.csp = getattr(settings, "CSP_HEADER", "default-src 'self'")

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = self.csp
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["Referrer-Policy"] = "same-origin"
        return response
