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
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "insecure-dev-key-replace-before-any-real-use",
)
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
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
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
FIELD_ENCRYPTION_KEY = os.environ.get("FIELD_ENCRYPTION_KEY", "")

# Warn loudly if the encryption key is missing outside of test runs.
# Encrypted fields (supplier credentials, crawl rule secrets) will silently
# produce corrupted ciphertext when the key is empty or invalid.
if not _TESTING and not FIELD_ENCRYPTION_KEY:
    import warnings
    warnings.warn(
        "FIELD_ENCRYPTION_KEY is not set. Encrypted model fields (supplier credentials, "
        "crawl rule request_headers) will not be protected at rest. "
        "Set FIELD_ENCRYPTION_KEY in your environment before running in production.",
        RuntimeWarning,
        stacklevel=2,
    )

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
}

# Periodic task schedule — stored in DB via django_celery_beat DatabaseScheduler
from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    # Nightly audit purge at 02:00 UTC — removes rows older than 365 days
    "purge-old-audit-logs": {
        "task": "audit.purge_old_audit_logs",
        "schedule": crontab(hour=2, minute=0),
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
TIME_ZONE = "UTC"
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
