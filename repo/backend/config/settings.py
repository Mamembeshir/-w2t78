"""
settings.py — Warehouse Intelligence & Offline Crawling Operations Platform
All configuration loaded from environment variables. Zero internet dependencies.
"""
import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────────────────────────────────────
# Core
# ─────────────────────────────────────────────────────────────────────────────
def _get_secret_key() -> str:
    """
    Return DJANGO_SECRET_KEY from the environment.
    Raises ImproperlyConfigured on any non-test startup when the variable is
    absent or empty, preventing accidental token-forgery exposure in deployment.
    Test runs (manage.py test / pytest) use a dedicated test-only placeholder.
    """
    import sys as _sys_early
    _testing_early = "test" in _sys_early.argv or "pytest" in _sys_early.modules

    _PLACEHOLDER_PATTERNS = (
        "change_me", "changeme", "replace_with",
        "your_secret", "secret_key", "example",
        "placeholder", "fixme", "todo",
    )

    value = os.environ.get("DJANGO_SECRET_KEY", "").strip()
    if value:
        if not _testing_early:
            lower = value.lower()
            if any(pat in lower for pat in _PLACEHOLDER_PATTERNS):
                from django.core.exceptions import ImproperlyConfigured
                raise ImproperlyConfigured(
                    "DJANGO_SECRET_KEY contains a placeholder value and must be "
                    "replaced before running in non-test mode. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )
        return value

    # No key provided — decide based on context:
    #   • pytest / manage.py test  → stable test-only string (keeps tests deterministic)
    #   • DEBUG=True (dev / CI)    → ephemeral random key per process (fine for CI,
    #                                acceptable for dev; set a real key in .env for
    #                                stable local sessions)
    #   • DEBUG=False (production) → hard error — never run prod without a real key
    if _testing_early:
        return "test-only-secret-key-not-for-production-do-not-use-outside-ci"
    if os.environ.get("DEBUG", "False") == "True":
        import secrets as _secrets
        return _secrets.token_urlsafe(64)
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY environment variable is not set. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )


SECRET_KEY = _get_secret_key()
DEBUG = os.environ.get("DEBUG", "False") == "True"

# Self-registration for Procurement Analyst role.
# Default OFF — set REGISTRATION_OPEN=true in the environment to enable.
# When disabled the /api/auth/register/ endpoint returns HTTP 403.
REGISTRATION_OPEN = os.environ.get("REGISTRATION_OPEN", "false").lower() == "true"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend,0.0.0.0"
    ).split(",")
    if h.strip()
]

# ─────────────────────────────────────────────────────────────────────────────
# Installed apps
# ─────────────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    # Django built-ins
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",
    # Project apps
    "accounts",
    "warehouse",
    "inventory",
    "crawling",
    "notifications",
    "audit",
]

# ─────────────────────────────────────────────────────────────────────────────
# Custom user model — must be set before first migration
# ─────────────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.security_middleware.SecurityHeadersMiddleware",
    "config.request_id_middleware.RequestIDMiddleware",   # end-to-end request tracing
    "corsheaders.middleware.CorsMiddleware",          # before CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Audit middleware — logs every mutating authenticated request to AuditLog
    "audit.middleware.AuditLogMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# ─────────────────────────────────────────────────────────────────────────────
# Templates
# ─────────────────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Database — MySQL 8, utf8mb4, strict mode
# TEST.NAME points to the pre-created warehouse_db_test database
# (created by docker/mysql/init.sh)
# ─────────────────────────────────────────────────────────────────────────────
_DB_NAME = os.environ.get("DB_NAME", "warehouse_db")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": _DB_NAME,
        "USER": os.environ.get("DB_USER", "warehouse_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "warehouse_pass"),
        "HOST": os.environ.get("DB_HOST", "db"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "CONN_MAX_AGE": 60,
        "TEST": {
            # Uses the pre-created _test database (see docker/mysql/init.sh)
            # Avoids needing CREATE DATABASE privilege in CI/tests
            "NAME": _DB_NAME + "_test",
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_unicode_ci",
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Cache — Redis (local only, no external)
# During `manage.py test` or pytest runs, use DummyCache so throttle counters
# never accumulate across test methods (avoids 429 failures in test suites).
# ─────────────────────────────────────────────────────────────────────────────
import sys as _sys
_TESTING = "test" in _sys.argv or "pytest" in _sys.modules

CACHES = {
    "default": {
        "BACKEND": (
            "django.core.cache.backends.dummy.DummyCache"
            if _TESTING
            else "django.core.cache.backends.redis.RedisCache"
        ),
        "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/0"),
        "OPTIONS": {
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
        },
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Password hashing — Argon2 primary (NEVER bcrypt or PBKDF2 as primary)
# Per CLAUDE.md security rules
# ─────────────────────────────────────────────────────────────────────────────
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    # Fallback only — for any pre-existing PBKDF2 hashes during migration
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─────────────────────────────────────────────────────────────────────────────
# Django REST Framework
# ─────────────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "config.exceptions.custom_exception_handler",
    # Throttle authenticated API calls and protect the login endpoint
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "200/hour",
        "user": "2000/hour",
        # Named scopes
        "login":    "5/minute",
        "register": "3/hour",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# JWT — short-lived access tokens, 8h refresh, blacklist on rotation
# ─────────────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=8),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

# ─────────────────────────────────────────────────────────────────────────────
# CORS — local frontend only; no external origins ever allowed
# ─────────────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False  # explicit: never wildcard

# ─────────────────────────────────────────────────────────────────────────────
# Field encryption at rest (django-encrypted-model-fields)
# Covers: supplier credentials, crawl rule secrets, API keys, tokens
# Generate key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# ─────────────────────────────────────────────────────────────────────────────
# Dev/CI fallback — a valid Fernet key used when FIELD_ENCRYPTION_KEY is not
# set or is set to a placeholder.  Never use this value in production.
_DEV_FERNET_KEY = "yJ7SB6N0BHk2PUlnL_6W2cmTQVbbtB83dr9JOwbr5l0="


def _resolve_encryption_key() -> str:
    """Return a valid Fernet key.

    In test runs, falls back to the embedded dev key so CI requires no secrets.
    In production, raises ImproperlyConfigured when:
      - FIELD_ENCRYPTION_KEY is absent or malformed
      - the value is the publicly known dev key (_DEV_FERNET_KEY)
      - the value begins with "CHANGE_ME" (copied from .env.example verbatim)
    """
    from cryptography.fernet import Fernet
    candidate = os.environ.get("FIELD_ENCRYPTION_KEY", "").strip()

    # A candidate is usable only when it is non-empty, not a placeholder, and
    # not the publicly known dev fallback key.
    is_usable = (
        candidate
        and not candidate.upper().startswith("CHANGE_ME")
        and candidate != _DEV_FERNET_KEY
    )

    if is_usable:
        try:
            Fernet(candidate)   # raises ValueError if key is malformed
            return candidate
        except Exception:
            pass

    # Test runner or DEBUG=True (dev / CI without .env) → use dev fallback key
    if _TESTING or os.environ.get("DEBUG", "False") == "True":
        return _DEV_FERNET_KEY

    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        "FIELD_ENCRYPTION_KEY is not set, is a placeholder (CHANGE_ME…), or uses "
        "the publicly known dev key. Generate a real key with: "
        "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )


FIELD_ENCRYPTION_KEY = _resolve_encryption_key()

# ─────────────────────────────────────────────────────────────────────────────
# Celery — local Redis broker/backend only
# ─────────────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
# Digest fires at 18:00 local wall-clock (SPEC: "6:00 PM").
# Mirrors TIME_ZONE so beat schedule fires at 18:00 local time, not 18:00 UTC.
# TIME_ZONE is defined in the Internationalisation section below; we read from
# os.environ directly here so Celery config stays in one block.
CELERY_TIMEZONE = os.environ.get("TIME_ZONE", "UTC")
CELERY_ENABLE_UTC = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Named queues — worker subscribes to all; beat fires into appropriate queues.
# crawling.execute_crawl_task is NOT routed here — it is dispatched with an
# explicit queue=crawl.<shard> by the caller (see crawling/routing.py).
# Beat tasks (monitor_canary_versions, release_held_quotas, promote_waiting_tasks)
# land on crawl.0 as a stable default; they are lightweight and source-agnostic.
CELERY_TASK_ROUTES = {
    "crawling.monitor_canary_versions": {"queue": "crawl.0"},
    "crawling.release_held_quotas": {"queue": "crawl.0"},
    "crawling.promote_waiting_tasks": {"queue": "crawl.0"},
    "inventory.*": {"queue": "inventory"},
    "notifications.*": {"queue": "notifications"},
    "audit.purge_old_audit_logs": {"queue": "notifications"},
    "crawling.purge_old_crawl_records": {"queue": "crawl.0"},
}

# Periodic task schedule — stored in DB via django_celery_beat DatabaseScheduler
from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    # Nightly audit purge at 02:00 UTC — removes rows older than 365 days
    "purge-old-audit-logs": {
        "task": "audit.purge_old_audit_logs",
        "schedule": crontab(hour=2, minute=0),
    },
    # Nightly notification/outbound purge at 02:10 UTC — 365-day retention
    "purge-old-notification-records": {
        "task": "notifications.purge_old_notification_records",
        "schedule": crontab(hour=2, minute=10),
    },
    # Nightly crawl task/log purge at 02:20 UTC — 365-day retention
    "purge-old-crawl-records": {
        "task": "crawling.purge_old_crawl_records",
        "schedule": crontab(hour=2, minute=20),
    },
    # Daily slow-moving stock detection at 01:00 UTC
    "flag-slow-moving-items": {
        "task": "inventory.flag_slow_moving_items",
        "schedule": crontab(hour=1, minute=0),
    },
    # Safety stock breach check — every minute
    "check-safety-stock": {
        "task": "inventory.check_safety_stock",
        "schedule": 60.0,  # seconds
    },
    # Canary monitoring — every minute
    "monitor-canary-versions": {
        "task": "crawling.monitor_canary_versions",
        "schedule": 60.0,
    },
    # Release held quotas — every 15 minutes
    "release-held-quotas": {
        "task": "crawling.release_held_quotas",
        "schedule": crontab(minute="*/15"),
    },
    # Waitlist promotion — every 5 seconds
    "promote-waiting-tasks": {
        "task": "crawling.promote_waiting_tasks",
        "schedule": 5.0,
    },
    # Digest dispatcher — runs every minute and sends to users whose send_time matches now
    "send-daily-digests": {
        "task": "notifications.send_daily_digests",
        "schedule": 60.0,
    },
    # Retry queued outbound messages every 5 minutes
    "send-outbound-queued": {
        "task": "notifications.send_outbound_queued",
        "schedule": crontab(minute="*/5"),
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Optional local gateways — offline-only; no external providers
# Left blank = in-app only (messages queued, manually exportable)
# ─────────────────────────────────────────────────────────────────────────────
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "25"))
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "False") == "True"
SMS_GATEWAY_URL = os.environ.get("SMS_GATEWAY_URL", "")

# ─────────────────────────────────────────────────────────────────────────────
# Internationalisation
# ─────────────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
# Operators can set TIME_ZONE in the environment (.env) to match their site's
# wall-clock.  Default UTC keeps behaviour deterministic in CI/CD pipelines.
# Digest send_time comparisons use localtime() so this value matters.
TIME_ZONE = os.environ.get("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# ─────────────────────────────────────────────────────────────────────────────
# Static files
# ─────────────────────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─────────────────────────────────────────────────────────────────────────────
# Security hardening
# ─────────────────────────────────────────────────────────────────────────────
# Refresh tokens stored in HttpOnly + Secure cookies (set by auth views)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = False  # CSRF token must be readable by JS
CSRF_COOKIE_SECURE = not DEBUG

# CSP: block all external sources — fully offline platform
# 'unsafe-inline' allowed for Tailwind-injected styles; no external URLs ever
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_BROWSER_XSS_FILTER = True

# Content-Security-Policy header via middleware response header
# Applied by a lightweight middleware below; avoids django-csp dependency
CSP_HEADER = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none';"
)

# ─────────────────────────────────────────────────────────────────────────────
# Logging — secrets/tokens masked before any log line is written
# ─────────────────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "mask_secrets": {
            "()": "config.logging_filters.MaskSecretsFilter",
        },
    },
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "filters": ["mask_secrets"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
