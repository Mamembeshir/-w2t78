# SESSION_SUMMARY.md — Warehouse Intelligence & Offline Crawling Operations Platform

## Session Log

---

### Session 1 — Phase 1.1: Repository Structure
**Date:** 2026-04-03
**Phase:** 1.1 Repository Structure
**Status:** Complete

#### What Was Completed
- Created `SPEC.md` — full project specification (offline warehouse + crawling platform)
- Created `CLAUDE.md` — strict project rules, tech stack constraints, and 11 resolved clarifications
- Created `PLAN.md` — detailed 9-phase development plan with 209 individual tasks
- Created top-level directory structure: `backend/`, `frontend/`, `docker/` (with `mysql/` subdir), `scripts/`
- Created root `.gitignore` covering Python/Django, Node/frontend, environment files, Docker volumes, OS and editor artifacts

#### Decisions Made
No new open questions arose in this phase. All 11 clarifications were pre-resolved in `CLAUDE.md` during project setup.

#### Directory Structure Established
```
repo/
├── SPEC.md
├── CLAUDE.md
├── PLAN.md
├── SESSION_SUMMARY.md
├── .gitignore
├── backend/          ← Django 5 project (Phase 1.4)
├── frontend/         ← React 19 + Vite project (Phase 1.5)
├── docker/
│   └── mysql/        ← MySQL init scripts (Phase 1.2)
└── scripts/          ← Utility scripts including run_test.sh (Phase 1.3)
```

#### Files Changed
| File | Action |
|---|---|
| `SPEC.md` | Created |
| `CLAUDE.md` | Created |
| `PLAN.md` | Created + updated (tasks 1.1 marked complete) |
| `.gitignore` | Created |
| `backend/.gitkeep` | Created (placeholder) |
| `frontend/.gitkeep` | Created (placeholder) |
| `docker/.gitkeep` | Created (placeholder) |
| `scripts/.gitkeep` | Created (placeholder) |
| `SESSION_SUMMARY.md` | Created |

#### Next Phase
**Phase 1.2 — Docker Setup**: Write `docker-compose.yml`, MySQL init SQL, backend Dockerfile, frontend Dockerfile, and `.env.example`.

---

### Session 2 — Phase 1.2: Docker Setup
**Date:** 2026-04-03
**Phase:** 1.2 Docker Setup
**Status:** Complete

#### What Was Completed
- `docker-compose.yml` — 6 services: `db` (MySQL 8), `redis` (Redis 7), `backend` (Gunicorn), `worker` (Celery), `beat` (Celery Beat), `frontend` (Vite dev)
- `docker/mysql/init.sh` — shell-based init script (not .sql) to get env var substitution; creates primary DB + test DB, grants user privileges on both
- `backend/Dockerfile` — Python 3.12-slim, installs mysqlclient system deps, copies requirements.txt, runs migrate + gunicorn on CMD
- `frontend/Dockerfile` — Node 20-alpine multi-stage: `dev` (vite dev server), `build` (npm run build), `production` (nginx static serving)
- `frontend/nginx.conf` — SPA fallback, static asset cache headers, gzip enabled
- `docker/.env.example` — all env vars documented: Django, MySQL, Redis, Celery, encryption key, CORS, SMTP/SMS gateway optionals
- Minimal backend stub (`manage.py`, `config/settings.py`, `config/wsgi.py`, `config/urls.py`, `config/celery.py`) to allow containers to start
- Minimal frontend stub (`package.json`, `vite.config.ts`, `tsconfig*.json`, `index.html`, `src/main.tsx`) to allow Vite container to start
- `backend/requirements.txt` — pinned versions for all Phase 2+ dependencies (Django 5.1.4, DRF, Celery, etc.)
- All 6 containers verified running; `GET /api/health/` returns `{"status": "ok"}`

#### Decisions Made
- **init.sh vs init.sql**: Used `.sh` instead of `.sql` for the MySQL init script so environment variables (`$MYSQL_DATABASE`, `$MYSQL_USER`) are substituted at runtime. The test database name is `{DB_NAME}_test`.
- **Added `beat` service**: PLAN.md listed `worker` but Celery Beat (scheduled tasks) is a separate process required for digest notifications, safety stock checks, audit purges, canary monitoring etc. Added `beat` as a 6th service.
- **Host port offsets**: MySQL mapped to `3307` and Redis to `6380` on the host to avoid conflicts with other running Docker containers on this machine. Internal container ports remain standard (`3306`, `6379`).
- **Multi-stage frontend Dockerfile**: `dev` stage uses `vite dev --host 0.0.0.0`; `production` stage uses nginx (for Phase 9.5). docker-compose uses `target: dev` for local development.
- **Minimal stubs**: Created minimal `config/celery.py` stub and added `django_celery_beat`/`django_celery_results` to `INSTALLED_APPS` so beat/worker containers start without errors in this phase.

#### Files Changed
| File | Action |
|---|---|
| `docker-compose.yml` | Created |
| `docker/mysql/init.sh` | Created |
| `docker/.env.example` | Created |
| `backend/Dockerfile` | Created |
| `backend/requirements.txt` | Created (stub, expanded in Phase 1.4) |
| `backend/manage.py` | Created (stub) |
| `backend/config/__init__.py` | Created |
| `backend/config/settings.py` | Created (stub, expanded in Phase 1.4) |
| `backend/config/wsgi.py` | Created |
| `backend/config/urls.py` | Created (health endpoint) |
| `backend/config/celery.py` | Created (stub) |
| `frontend/Dockerfile` | Created |
| `frontend/nginx.conf` | Created |
| `frontend/package.json` | Created (stub, expanded in Phase 1.5) |
| `frontend/vite.config.ts` | Created |
| `frontend/tsconfig*.json` | Created |
| `frontend/index.html` | Created (no CDN links) |
| `frontend/src/main.tsx` | Created (stub) |
| `PLAN.md` | Updated (1.2 tasks marked complete) |

#### Next Phase
**Phase 1.3 — run_test.sh**: Script to start all services, wait for DB readiness, print service URLs.

---

### Session 3 — Phase 1.3: run_test.sh
**Date:** 2026-04-03
**Phase:** 1.3 run_test.sh
**Status:** Complete

#### What Was Completed
- `run_test.sh` created at repo root, executable (`chmod +x`)
- 3-phase ordered startup:
  - Phase 1: `db` + `redis` — waits for Docker healthcheck AND verifies real MySQL query accepts connection
  - Phase 2: `backend` + `worker` + `beat` — waits for `/api/health/` HTTP 200
  - Phase 3: `frontend` — waits for TCP port 5173 open
- Coloured output: cyan INFO, green OK, yellow WARN, red ERROR
- URL banner printed on successful startup (frontend, API, admin, health, MySQL host port, Redis host port)
- Prerequisite checks: Docker daemon, compose v2 installed, `.env` exists (auto-copies from example if missing)
- Subcommands: `start` (default), `stop`, `restart`, `build`, `logs [svc]`, `status`, `test`, `shell`
- Verified: cold-start from zero to all 6 services in ~15 seconds

#### Decisions Made
- **Two-level MySQL wait**: Docker healthcheck (`mysqladmin ping`) is necessary but not sufficient — also verify an actual `SELECT 1` query on `warehouse_db` as the application user, which confirms the init script ran and user grants are in place.
- **3-phase startup**: Separating db/redis → backend/worker/beat → frontend ensures dependency ordering even if `docker compose` health-condition dependencies are modified later.
- **`nc` for frontend port check**: Vite doesn't expose a JSON health endpoint; TCP port check is the most reliable offline-compatible signal.
- **`.env` auto-copy**: If `.env` is missing (e.g. fresh clone), script copies from `docker/.env.example` with a warning — prevents confusing Docker errors for new developers.

#### Files Changed
| File | Action |
|---|---|
| `run_test.sh` | Created |
| `PLAN.md` | Updated (1.3 tasks marked complete) |
| `SESSION_SUMMARY.md` | Updated |

#### Next Phase
**Phase 1.4 — Backend Bootstrap**: Expand Django settings with full configuration (Argon2, DRF, CORS, encrypted fields), verify `python manage.py migrate` runs cleanly.

---

### Session 4 — Phase 1.4: Backend Bootstrap
**Date:** 2026-04-03
**Phase:** 1.4 Backend Bootstrap
**Status:** Complete

#### What Was Completed
- `config/settings.py` fully expanded (stub → production-ready):
  - **Argon2** as primary password hasher (PBKDF2 as legacy fallback only)
  - **DRF** with JWT authentication, IsAuthenticated default, PageNumberPagination (50/page)
  - **JWT**: 15-min access tokens, 8h refresh, rotate+blacklist on rotation
  - **CORS**: `CORS_ALLOWED_ORIGINS` from env, `CORS_ALLOW_ALL_ORIGINS = False` (explicit)
  - **Redis cache** on `redis://redis:6379/0`
  - **FIELD_ENCRYPTION_KEY** wired from env for `django-encrypted-model-fields`
  - **TEST database**: `warehouse_db_test` (pre-created by init.sh, avoids needing CREATE privilege)
  - **Masked logging**: `MaskSecretsFilter` applied to console handler — no secret reaches stdout
  - **Celery** task routes: crawl/inventory/notifications queues pre-defined
  - **Optional SMTP/SMS gateways**: env vars wired, empty = in-app only
- `config/exceptions.py`: custom DRF exception handler → `{ code, message, details }`
- `config/logging_filters.py`: `MaskSecretsFilter` with 3-pattern regex covering Auth headers, JSON values, query-string/env var secrets
- `config/urls.py`: health endpoint upgraded — checks real DB connection, returns `{ status, db }`
- `python manage.py migrate` verified: all 50+ migrations applied cleanly (`[X]` on every migration)
- Argon2 verified active: `argon2$argon2id$v=19...` prefix confirmed
- Logging masking verified: Bearer tokens, passwords, API keys, FIELD_ENCRYPTION_KEY all → `[REDACTED]`

#### Decisions Made
- **TEST db via `TEST.NAME` key**: Used `DATABASES["default"]["TEST"]["NAME"] = "warehouse_db_test"` rather than a separate `"test"` alias. This is Django's canonical approach and lets `./manage.py test` use the pre-created test DB without needing CREATE DATABASE privilege on the MySQL user.
- **PBKDF2 as fallback**: Kept PBKDF2 second in `PASSWORD_HASHERS` only to handle any pre-existing hashes if the user switches from another system — Django transparently re-hashes on next login. Argon2 is always used for new passwords.
- **3-pattern masking order**: JSON-specific pattern runs before general key=value pattern to avoid consuming trailing commas/quotes. Verified correct output.
- **`CORS_ALLOW_ALL_ORIGINS = False` explicit**: Belt-and-suspenders — even if `CORS_ALLOWED_ORIGINS` is misconfigured, wildcard is never active.

#### Files Changed
| File | Action |
|---|---|
| `backend/config/settings.py` | Fully rewritten (stub → production) |
| `backend/config/exceptions.py` | Created |
| `backend/config/logging_filters.py` | Created |
| `backend/config/urls.py` | Updated (health checks real DB) |
| `PLAN.md` | Updated (1.4 tasks marked complete) |

#### Next Phase
**Phase 1.5 — Frontend Bootstrap**: Full TailwindCSS dark theme config, React Router, Axios, React Query, verified `vite dev` on local network.

---

### Session 5 — Phase 1.5: Frontend Bootstrap
**Date:** 2026-04-03
**Phase:** 1.5 Frontend Bootstrap
**Status:** Complete ✓ (Phase 1 fully complete)

#### What Was Completed
- `tailwind.config.ts` — full dark enterprise design system:
  - `surface` palette (900→500): page bg, cards, borders, muted
  - `primary` (indigo) + `accent` (cyan) full 9-shade scales
  - `success/warning/danger/info` status colours
  - `text.primary/secondary/muted/disabled` hierarchy
  - `minHeight.touch = 44px`, `minHeight.touch-lg = 52px` (CLAUDE.md requirement)
  - Custom shadows (card, card-md, card-lg, glow-primary/accent/danger)
  - `z-index` layers: sidebar(40), topbar(50), modal(60), toast(70), tooltip(80)
  - Inter + JetBrains Mono font stacks (system fallbacks — no CDN)
- `postcss.config.js` — tailwindcss + autoprefixer
- `src/styles/globals.css` — full base/component/utility layers:
  - Dark scrollbars, focus rings, typography defaults, table styles
  - `.card`, `.card-sm`, `.badge-{success/warning/danger/info/neutral}`, `.divider`, `.section-title`, `.glass`
  - Autofill dark override (`-webkit-box-shadow` trick)
- `src/lib/api.ts` — Axios instance:
  - JWT Bearer token on every request (from localStorage)
  - 401 → token refresh flow with pending-request queue (no duplicate refresh)
  - Network error → clear "Cannot reach server" offline message
  - `setTokens()`, `clearTokens()`, `hasToken()` helpers
- `src/lib/queryClient.ts` — React Query: 30s stale, no 4xx retry, no focus refetch (kiosk-safe)
- `vite.config.ts` — `@/` alias → `src/`, vendor chunk splitting, strictPort, Docker proxy
- `package.json` — added `@types/node` for path alias in vite.config
- `src/main.tsx` — wires CSS + QueryClientProvider, bootstrap placeholder page using real Tailwind classes
- `index.html` — verified CLEAN (zero external URLs)
- Verified: Vite v6.4.1 ready in 123ms, HTTP 200, Tailwind compiles all custom tokens correctly

#### Decisions Made
- **No CDN fonts** — Inter and JetBrains Mono listed in font stacks with system fallbacks. Actual font files will be self-hosted in Phase 4 when the full UI is built.
- **`minHeight.touch = 44px` enforced at CSS layer** — base `input/textarea/select` get `min-height: 2.75rem` in globals.css, meaning all form elements meet the tap-target requirement automatically.
- **React Query `refetchOnWindowFocus: false`** — warehouse kiosk screens must not trigger API calls when a barcode scanner focus-events the window.
- **Pending refresh queue** — the 401 interceptor uses a queue so multiple simultaneous expired-token requests don't cause multiple refresh calls. All pending requests replay once the new token arrives.

#### Files Changed
| File | Action |
|---|---|
| `frontend/tailwind.config.ts` | Created |
| `frontend/postcss.config.js` | Created |
| `frontend/src/styles/globals.css` | Created |
| `frontend/src/lib/api.ts` | Created |
| `frontend/src/lib/queryClient.ts` | Created |
| `frontend/src/main.tsx` | Updated |
| `frontend/vite.config.ts` | Updated |
| `frontend/package.json` | Updated (added @types/node) |
| `PLAN.md` | Updated (Phase 1 marked complete) |

#### Phase 1 Complete 🎉
All 34 tasks across 1.1–1.5 are done. The full stack runs via `./run_test.sh start`.

#### Next Phase
**Phase 2 — Backend: Django + MySQL + Core Models**: Django apps, abstract base models, all domain models (User/Role, Warehouse/Bin, Item/Lot/Serial, StockLedger/Balance, CrawlSource/RuleVersion/Task, Notifications, AuditLog).

---

### Session 6 — Phase 2: Backend Core Models
**Date:** 2026-04-03
**Phase:** 2.1–2.9 Backend — Django + MySQL + Core Models
**Status:** Complete ✓

#### What Was Completed
- `core/__init__.py`, `core/managers.py` — `ActiveManager` (excludes soft-deleted) + `AllObjectsManager`
- `core/models.py` — `TimeStampedModel` (created_at/updated_at) and `SoftDeleteModel` (deleted_at, soft `.delete()`, `.restore()`, `.hard_delete()`)
- `accounts/models.py` — custom `User(AbstractUser)` with `Role` TextChoices: ADMIN / INVENTORY_MANAGER / PROCUREMENT_ANALYST; `AUTH_USER_MODEL = "accounts.User"` added to settings
- `warehouse/models.py` — `Warehouse` (code unique, soft-deletable) + `Bin` (warehouse FK, code, unique_together)
- `inventory/models.py` — `Item` (SKU, costing method FIFO/MOVING_AVG, safety_stock_qty), `ItemLot`, `ItemSerial` (with SerialStatus choices), `StockLedger` (immutable transaction rows, 5 transaction types, composite indexes), `StockBalance` (denormalised on-hand + reserved + avg_cost)
- `crawling/models.py` — `CrawlSource`, `CrawlRuleVersion` (canary fields, `EncryptedTextField` for request_headers), `CrawlTask` (fingerprint unique, exponential backoff fields, checkpoint_page), `CrawlRequestLog`, `SourceQuota` (held_until for 15-min auto-release)
- `notifications/models.py` — `NotificationSubscription`, `Notification`, `OutboundMessage` (SMTP/SMS, QUEUED/SENT/FAILED), `DigestSchedule` (18:00 default)
- `audit/models.py` — `AuditLog` (immutable: `.save()` raises if pk set, `.delete()` raises), + `purge_old_audit_logs` Celery task (nightly at 02:00, deletes rows > 365 days via queryset bulk delete)
- All 6 `admin.py` files registered with list_display, search, filters; `AuditLogAdmin` is fully read-only with no add/change/delete permissions
- `settings.py` updated: all 6 apps uncommented in `INSTALLED_APPS`; `AUTH_USER_MODEL`; `CELERY_BEAT_SCHEDULE` with nightly purge job
- DB volume reset (required for custom User model), `makemigrations` generated 0001_initial for all 6 apps, `migrate` applied all 65+ migrations cleanly
- Verified: 36 tables in `warehouse_db`, `/api/health/` → `{"status":"ok","db":"ok"}`

#### Decisions Made
- **DB volume reset**: `AUTH_USER_MODEL` must be set before any migration. Volume was dropped and recreated from init.sh — no data loss since no production data yet.
- **`SoftDeleteModel.delete()` overrides only the instance method**: `QuerySet.delete()` (used in the purge task) issues SQL directly via Collector and does NOT invoke the instance `.delete()` — so the purge task safely bypasses the immutability guard on `AuditLog`.
- **`EncryptedTextField` on `request_headers`**: Per CLAUDE.md §8, crawl rule secrets/headers encrypted at rest. Stored as a single encrypted text blob (JSON-serialised by the caller).
- **`crontab` import in settings.py**: Celery's `crontab` imported at module level in `settings.py` for `CELERY_BEAT_SCHEDULE`. Import guarded by the fact that `celery` is already a dependency; no circular import since celery is not imported by Django before apps load.
- **`AuditLog` immutability**: `save()` raises `NotImplementedError` on updates (pk is set); `delete()` raises on instance delete. Django admin is fully read-only (no add/change/delete permissions).

#### Files Changed
| File | Action |
|---|---|
| `backend/core/__init__.py` | Created |
| `backend/core/managers.py` | Created |
| `backend/core/models.py` | Created |
| `backend/accounts/models.py` | Written |
| `backend/accounts/admin.py` | Written |
| `backend/warehouse/models.py` | Written |
| `backend/warehouse/admin.py` | Written |
| `backend/inventory/models.py` | Written |
| `backend/inventory/admin.py` | Written |
| `backend/crawling/models.py` | Written |
| `backend/crawling/admin.py` | Written |
| `backend/notifications/models.py` | Written |
| `backend/notifications/admin.py` | Written |
| `backend/audit/models.py` | Written |
| `backend/audit/admin.py` | Written |
| `backend/config/settings.py` | Updated (INSTALLED_APPS, AUTH_USER_MODEL, CELERY_BEAT_SCHEDULE) |
| `backend/*/migrations/0001_initial.py` | Generated (6 files) |
| `PLAN.md` | Updated (Phase 2 marked complete) |

#### Phase 2 Complete
All 27 tasks across 2.1–2.9 done. 36 tables in warehouse_db, health endpoint OK.

#### Next Phase
**Phase 3 — Authentication & RBAC**: JWT login/logout/refresh endpoints, IsAdmin/IsInventoryManager/IsProcurementAnalyst permission classes, audit middleware, user management API.

---
