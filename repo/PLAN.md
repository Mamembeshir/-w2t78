# PLAN.md — Warehouse Intelligence & Offline Crawling Operations Platform

## Status Legend
- `[ ]` Pending
- `[x]` Complete
- `[-]` In Progress
- `[!]` Blocked

---

## Phase 1: Project Setup + Docker + run_test.sh

### 1.1 Repository Structure
- [x] Create `SPEC.md` with full project specification
- [x] Create `CLAUDE.md` with strict project rules and clarifications
- [x] Create `PLAN.md` (this file)
- [x] Create top-level directory structure: `backend/`, `frontend/`, `docker/`, `scripts/`
- [x] Create root `.gitignore` covering Python, Node, Docker, env files

### 1.2 Docker Setup
- [x] Write `docker-compose.yml` with services: `db` (MySQL 8), `redis`, `backend`, `worker`, `beat`, `frontend`
- [x] Write `docker/mysql/init.sh` for database and user creation (uses env vars; creates primary + test DBs)
- [x] Write `backend/Dockerfile` (Python 3.12, Gunicorn)
- [x] Write `frontend/Dockerfile` (Node 20, multi-stage: dev/build/production)
- [x] Add `docker/.env.example` with all required env vars documented
- [x] Verify all containers start cleanly with `docker compose up` (all 6 running, `/api/health/` → 200)

### 1.3 run_test.sh
- [x] Create `run_test.sh` at repo root
- [x] Script starts DB + Redis + backend + frontend in correct order (3-phase startup)
- [x] Script waits for MySQL readiness before starting Django (Docker healthcheck + query verify)
- [x] Script prints service URLs on startup (frontend, backend, admin, health, MySQL, Redis)
- [x] Make `run_test.sh` executable (`chmod +x`)
- [x] Subcommands: start, stop, restart, build, logs [svc], status, test, shell

### 1.4 Backend Bootstrap
- [x] Initialize Django 5 project inside `backend/` (manage.py, config package)
- [x] Install dependencies: `djangorestframework`, `mysqlclient`, `celery`, `redis`, `argon2-cffi`, `django-encrypted-model-fields` (pinned in requirements.txt)
- [x] Create `requirements.txt` pinned to exact versions
- [x] Configure `settings.py`: MySQL + TEST db, Argon2 hasher, DRF + JWT, CORS, Redis cache, encrypted fields, masked logging
- [x] Add `config/exceptions.py`: standardized `{ code, message, details }` error format
- [x] Add `config/logging_filters.py`: MaskSecretsFilter redacts tokens/keys/passwords in all logs
- [x] Verify `python manage.py migrate` runs cleanly — all migrations [X] including token_blacklist, celery_beat, celery_results

### 1.5 Frontend Bootstrap
- [x] Initialize Vite + React 19 + TypeScript project inside `frontend/`
- [x] Install TailwindCSS and configure `tailwind.config.ts` with dark enterprise theme (surface/primary/accent/status palettes, touch sizing, shadows)
- [x] Install dependencies: `react-router-dom`, `axios`, `@tanstack/react-query`, `@types/node` (pinned in package.json)
- [x] Configure `postcss.config.js` for Tailwind processing
- [x] Create `src/styles/globals.css`: @tailwind directives + base/component/utility layers (scrollbars, tables, cards, badges, inputs)
- [x] Create `src/lib/api.ts`: Axios instance with JWT interceptor, 401 refresh flow, offline error messaging
- [x] Create `src/lib/queryClient.ts`: React Query client tuned for local-network (30s stale, no 4xx retry, no focus refetch)
- [x] Update `vite.config.ts`: `@/` path alias, split vendor chunks, strictPort, Docker-compatible proxy
- [x] Create base `index.html` with no external CDN links (verified CLEAN)
- [x] Verify `vite dev` runs and serves on local network — Vite v6.4.1 ready in 123ms, HTTP 200, Tailwind CSS fully compiled with custom tokens

---

## Phase 2: Backend — Django + MySQL + Core Models

### 2.1 App Structure
- [x] Create Django apps: `accounts`, `warehouse`, `inventory`, `crawling`, `notifications`, `audit`
- [x] Register all apps in `settings.py`
- [x] Create shared `core/` module for base models, encryption helpers, and utilities

### 2.2 Core Base Models
- [x] Create `TimeStampedModel` abstract base (created_at, updated_at)
- [x] Create `SoftDeleteModel` abstract base (deleted_at, is_deleted)
- [x] Create encrypted field wrapper using `django-encrypted-model-fields`
- [x] Write and run initial migration for base setup

### 2.3 User & Role Models (`accounts` app)
- [x] `User` model: username, argon2 password, role, is_active, last_login
- [x] `Role` choices: `ADMIN`, `INVENTORY_MANAGER`, `PROCUREMENT_ANALYST`
- [x] Write migration and verify in Django admin

### 2.4 Warehouse & Bin Models (`warehouse` app)
- [x] `Warehouse`: id, name, code, address, is_active
- [x] `Bin`: id, warehouse FK, code, description, is_active
- [x] Write migration and register in admin

### 2.5 Item & SKU Models (`inventory` app)
- [x] `Item`: id, sku, name, description, unit_of_measure, costing_method (FIFO/MOVING_AVG), safety_stock_qty, is_active
- [x] `ItemLot`: id, item FK, lot_number, expiry_date, received_date
- [x] `ItemSerial`: id, item FK, serial_number, status
- [x] Write migration and register in admin

### 2.6 Inventory Ledger Models (`inventory` app)
- [x] `StockLedger`: id, item FK, warehouse FK, bin FK, lot FK, quantity, unit_cost, costing_method, transaction_type, reference, timestamp
- [x] Transaction types: `RECEIVE`, `ISSUE`, `TRANSFER_OUT`, `TRANSFER_IN`, `CYCLE_COUNT_ADJUST`
- [x] `StockBalance`: id, item FK, warehouse FK, bin FK, quantity_on_hand, quantity_reserved, avg_cost (denormalized, updated on each transaction)
- [x] Write migration

### 2.7 Crawling Models (`crawling` app)
- [x] `CrawlSource`: id, name, base_url, is_active, rate_limit_rpm, crawl_delay_seconds, user_agents (JSON), created_by FK
- [x] `CrawlRuleVersion`: id, source FK, version_number, version_note, url_pattern, parameters (JSON), pagination_config (JSON), request_headers (encrypted JSON), is_active, is_canary, canary_pct, canary_started_at, created_by FK
- [x] `CrawlTask`: id, source FK, rule_version FK, fingerprint (unique), url, status, priority, attempt_count, next_retry_at, checkpoint_page, last_error, created_at, started_at, completed_at
- [x] `CrawlRequestLog`: id, task FK, request_url, request_headers (masked), response_status, response_snippet, duration_ms, timestamp
- [x] `SourceQuota`: id, source FK, rpm_limit, current_count, window_start, held_until (for timeout release)
- [x] Write migrations

### 2.8 Notification Models (`notifications` app)
- [x] `NotificationSubscription`: id, user FK, event_type, threshold_value, is_active
- [x] `Notification`: id, user FK, event_type, title, body, is_read, read_at, created_at
- [x] `OutboundMessage`: id, notification FK, channel (SMTP/SMS), status, queued_at, sent_at, error
- [x] `DigestSchedule`: id, user FK, send_time (default 18:00), last_sent_at
- [x] Write migration

### 2.9 Audit Models (`audit` app)
- [x] `AuditLog`: id, user FK, action, model_name, object_id, changes (JSON), ip_address, timestamp
- [x] Automatic purge: Celery beat task deletes records older than 365 days
- [x] Write migration

---

## Phase 3: Authentication & RBAC

### 3.1 Auth API
- [x] `POST /api/auth/login/` — validates credentials, returns JWT access + refresh tokens
- [x] `POST /api/auth/logout/` — blacklists refresh token
- [x] `POST /api/auth/refresh/` — issues new access token
- [x] Use `djangorestframework-simplejwt` with short-lived access tokens (15 min) and longer refresh (8 hours)
- [x] Store refresh tokens server-side for blacklisting

### 3.2 Permission Classes
- [x] Create `IsAdmin`, `IsInventoryManager`, `IsProcurementAnalyst` DRF permission classes
- [x] Create `IsAdminOrReadOnly` for reference data endpoints
- [x] Apply permissions to all views

### 3.3 Audit Middleware
- [x] Write Django middleware that logs every mutating request (POST/PUT/PATCH/DELETE) to `AuditLog`
- [x] Middleware captures: user, action, affected model, changed fields, IP address
- [x] Mask any token/secret values before writing to audit log

### 3.4 User Management API (Admin only)
- [x] `GET /api/users/` — list users
- [x] `POST /api/users/` — create user with role
- [x] `PUT /api/users/{id}/` — update user (role, active status)
- [x] `POST /api/users/{id}/reset-password/` — admin resets password

---

## Phase 4: Frontend Core Layout + Premium UI

### 4.1 Design System
- [x] Define TailwindCSS color palette: dark slate backgrounds, indigo/cyan accents, white text
- [x] Create typography scale in `tailwind.config.ts`
- [x] Create global CSS reset and base styles in `src/styles/globals.css`
- [x] Define spacing and shadow tokens (subtle card shadows, no harsh borders)

### 4.2 Core Layout Components
- [x] `AppShell` — full-screen dark layout with sidebar + main content area
- [x] `Sidebar` — role-aware navigation links, collapsible, active state indicators
- [x] `TopBar` — page title, notification bell with unread count badge, user menu
- [x] `PageWrapper` — consistent padding and max-width container
- [x] `LoadingSpinner` — centered full-page and inline variants

### 4.3 Reusable UI Components
- [x] `Button` — primary, secondary, danger, ghost variants; large touch target (min 44px)
- [x] `Input` — dark-styled text input with label, error state, and helper text
- [x] `Select` — styled dropdown matching dark theme
- [x] `DataTable` — sortable columns, row hover, pagination controls, empty state
- [x] `Badge` — status badges (success, warning, error, info, neutral)
- [x] `Modal` — accessible dialog with backdrop, close button, focus trap
- [x] `Card` — content container with subtle shadow and border
- [x] `Toast` — top-right notification toasts (success/error/warning)

### 4.4 Routing & Auth Shell
- [x] Set up `react-router-dom` with lazy-loaded route components
- [x] Create `ProtectedRoute` wrapper that checks JWT and role
- [x] Create `LoginPage` — full-screen dark login form, no external assets
- [x] Redirect unauthenticated users to `/login`
- [x] Redirect authenticated users to role-appropriate dashboard

### 4.5 Role-Based Navigation
- [x] Inventory Manager nav: Dashboard, Receive Stock, Issue Stock, Transfer, Cycle Count, Inventory Search
- [x] Procurement Analyst nav: Dashboard, Crawl Sources, Rule Configuration, Task Monitor, Request Debugger
- [x] Admin nav: All of the above + User Management, Audit Log, System Settings
- [x] Hide nav items not permitted for current role

### 4.6 Dashboard Pages (Skeleton)
- [x] `InventoryDashboard` — stock summary cards, recent transactions table, safety stock alerts list
- [x] `CrawlingDashboard` — active tasks count, source health indicators, recent errors
- [x] `AdminDashboard` — user count, system status, recent audit entries

---

## Phase 5: Inventory Operations

### 5.1 Warehouse & Bin API
- [x] `GET /api/warehouses/` — list warehouses
- [x] `POST /api/warehouses/` — create warehouse (Admin)
- [x] `GET /api/warehouses/{id}/bins/` — list bins for warehouse
- [x] `POST /api/warehouses/{id}/bins/` — create bin (Admin)

### 5.2 Item & SKU API
- [x] `GET /api/items/` — list/search items with filters (SKU, name, costing method)
- [x] `POST /api/items/` — create item (Admin/Inventory Manager)
- [x] `GET /api/items/{id}/` — item detail with current stock balances
- [x] `PUT /api/items/{id}/` — update item
- [x] `GET /api/items/{id}/lots/` — list lots for item
- [x] `GET /api/items/{id}/serials/` — list serials for item
- [x] `GET /api/items/{id}/ledger/` — full ledger history for item

### 5.3 Receive Stock API
- [x] `POST /api/inventory/receive/` — receive stock: item, warehouse, bin, lot, quantity, unit_cost
- [x] Update `StockBalance` within same transaction (atomic)
- [x] Moving average cost updated on each receipt using weighted average formula
- [x] Return updated balance in response

### 5.4 Issue Stock API
- [x] `POST /api/inventory/issue/` — issue stock: item, warehouse, bin, lot, quantity, work_order_ref
- [x] FIFO: consume oldest lot first (auto); Moving Average: deduct at current avg cost
- [x] Validate sufficient on-hand quantity before issuing
- [x] Update `StockBalance` atomically

### 5.5 Transfer API
- [x] `POST /api/inventory/transfer/` — transfer: item, from_warehouse, from_bin, to_warehouse, to_bin, quantity
- [x] Creates paired `TRANSFER_OUT` + `TRANSFER_IN` ledger entries atomically
- [x] Validates source has sufficient stock

### 5.6 Cycle Count API
- [x] `POST /api/inventory/cycle-count/start/` — start a count session for item + location
- [x] `POST /api/inventory/cycle-count/{id}/submit/` — submit actual count quantity
- [x] If variance > $500.00: return `variance_confirmation_required: true` with expected vs actual
- [x] `POST /api/inventory/cycle-count/{id}/confirm/` — confirm with reason_code + supervisor note
- [x] Post `CYCLE_COUNT_ADJUST` ledger entry after confirmation

### 5.7 Stock Balance & Costing
- [x] `GET /api/inventory/balances/` — balances with filters (warehouse, item, below safety stock)
- [x] FIFO cost engine: calculate cost of goods issued from oldest lots (`inventory/costing.py`)
- [x] Moving average engine: recalculate avg cost on every receipt
- [x] Slow-moving detection: Celery task daily flags items with no issues in 90 days

### 5.8 Safety Stock Alert Engine
- [x] Celery beat task runs every minute checking `StockBalance` vs `Item.safety_stock_qty`
- [x] Records breach start time in `SafetyStockBreachState` model per item+warehouse
- [x] After 10 consecutive minutes below threshold: fires `SafetyStockBreach` notification
- [x] Clears alert state when quantity recovers above threshold

### 5.9 Frontend — Receive Stock Screen
- [x] Barcode/RFID input field (keyboard-wedge compatible, large, prominent)
- [x] Live SKU search with dropdown suggestions
- [x] Form: item lookup by scan/entry, warehouse selector, bin selector, lot input, quantity, unit cost
- [x] Submit → show success with updated balance; error states clearly displayed

### 5.10 Frontend — Issue Stock Screen
- [x] Scan/enter item identifier
- [x] Work order reference input
- [x] Show available lots in FIFO order with quantities
- [x] Quantity input with real-time validation against available stock
- [x] Submit → show deducted lots and updated balance

### 5.11 Frontend — Transfer Screen
- [x] Source: warehouse + bin selectors with available quantity display
- [x] Destination: warehouse + bin selectors
- [x] Item + quantity form
- [x] Confirmation modal before submit

### 5.12 Frontend — Cycle Count Screen
- [x] Step 1: scan/enter item + select location
- [x] Step 2: expected qty hidden until user enters actual (bias prevention)
- [x] Step 3: reveal variance with color coding (green = match, amber = small, red = large)
- [x] Step 4 (if > $500): supervisor confirmation with reason code dropdown + notes

### 5.13 Frontend — Inventory Search Screen
- [x] Search by SKU, name
- [x] Results table: item, on-hand qty, costing method, slow-moving flag
- [x] Row drill-down to full ledger history modal

---

## Phase 6: Crawling Engine & Rule Management

### 6.1 Crawl Source API
- [x] `GET /api/crawl/sources/` — list sources
- [x] `POST /api/crawl/sources/` — create source (Procurement Analyst)
- [x] `PUT /api/crawl/sources/{id}/` — update source
- [x] `GET /api/crawl/sources/{id}/rule-versions/` — list rule versions

### 6.2 Crawl Rule Version API
- [x] `POST /api/crawl/sources/{id}/rule-versions/` — create new version (requires version_note)
- [x] `GET /api/crawl/rule-versions/{id}/` — rule version detail
- [x] `POST /api/crawl/rule-versions/{id}/activate/` — set as active version
- [x] `POST /api/crawl/rule-versions/{id}/canary/` — start canary release (5%, 30 min)
- [x] `POST /api/crawl/rule-versions/{id}/rollback/` — rollback to prior version
- [x] Rollback available in one click if canary error rate > 2%

### 6.3 Crawl Task Scheduler
- [x] `POST /api/crawl/tasks/` — enqueue a crawl task for a source
- [x] Generate deterministic fingerprint: SHA-256(url + sorted_params + selected_headers)
- [x] Reject duplicate fingerprints (return existing task id)
- [x] Assign priority from source config; shard tasks by source for worker affinity

### 6.4 Quota & Concurrency Engine
- [x] On task pickup: `SELECT ... FOR UPDATE` on `SourceQuota` row
- [x] Check current_count < rpm_limit within window; if exceeded → waitlist task
- [x] Deduct quota count within same transaction before releasing lock
- [x] Celery beat task every 15 min: release held quotas past `held_until`
- [x] Waitlist promotion: poll every 5 seconds for tasks in WAITING status with available quota

### 6.5 Crawl Worker
- [x] Celery worker consumes tasks from priority queue
- [x] Applies active rule version (or canary version for 5% of tasks)
- [x] Rotates user-agent from source's configured list
- [x] Honors source crawl_delay between requests
- [x] On failure: exponential backoff (10s, 30s, 2m, 10m), max 5 attempts
- [x] Persists checkpoint every 100 pages to `CrawlTask.checkpoint_page`
- [x] On worker restart: resumes from last checkpoint

### 6.6 Request Logging & Debugger
- [x] Log every request/response to `CrawlRequestLog` (keep last 20 per source)
- [x] Mask Authorization headers and any header containing `secret`, `key`, `token`, `password`
- [x] `GET /api/crawl/sources/{id}/debug-log/` — return last 20 samples

### 6.7 Canary Monitoring
- [x] Celery beat task every minute: calculate error rate for active canary versions
- [x] If error_rate > 2% within canary window: auto-trigger rollback + fire notification
- [x] After 30 minutes with error_rate ≤ 2%: promote canary to full active version
- [x] Record canary outcome in `CrawlRuleVersion`

### 6.8 Frontend — Crawl Source Configuration Center
- [x] Source list with status indicators (active, paused, error)
- [x] Source detail form: base URL, rate limit, crawl delay
- [x] Rule version list with version notes, status (active/canary/archived), created date

### 6.9 Frontend — Rule Version Editor
- [x] Version note required field before save
- [x] "Start Canary" button → canary started with 5%/30min window
- [x] "Rollback" button (red, shown only when canary is active)
- [x] Canary error rate displayed per version

### 6.10 Frontend — Visual Request Debugger
- [x] List of last 20 request/response samples for selected source
- [x] Columns: timestamp, URL, status code, duration (ms), response snippet
- [x] Expand row to see full (masked) headers
- [x] Auto-refresh every 10 seconds while panel is open

### 6.11 Frontend — Task Monitor
- [x] Live task list with status filters (pending, running, waiting, failed, complete)
- [x] Per-task detail: source, URL, attempt count
- [x] Retry button for failed tasks
- [x] Enqueue task form

---

## Phase 7: Notifications & Inbox

### 7.1 Notification Event System
- [x] Define event types: `SAFETY_STOCK_BREACH`, `SAFETY_STOCK_RECOVERED`, `CYCLE_COUNT_VARIANCE`, `CRAWL_TASK_FAILED`, `CANARY_ROLLBACK`, `SLOW_MOVING_STOCK`, `DIGEST`, `SYSTEM`
- [x] Event dispatcher: accepts event_type + payload, fans out to all matching subscriptions
- [x] Create `Notification` records for each subscribed user

### 7.2 Subscription API
- [x] `GET /api/notifications/subscriptions/` — list user's subscriptions
- [x] `POST /api/notifications/subscriptions/` — subscribe to event type with optional threshold (upsert: reactivates inactive)
- [x] `DELETE /api/notifications/subscriptions/{id}/` — unsubscribe

### 7.3 Notification Inbox API
- [x] `GET /api/notifications/inbox/` — paginated list with filters (unread, event_type, date range)
- [x] `POST /api/notifications/inbox/{id}/read/` — mark as read (records read_at)
- [x] `POST /api/notifications/inbox/read-all/` — mark all as read
- [x] `GET /api/notifications/inbox/unread-count/` — for badge display

### 7.4 Digest Scheduler
- [x] Celery beat task at 18:00 daily: aggregate unread notifications per user
- [x] Create a single digest `Notification` summarizing the day's events
- [x] Queue digest for outbound delivery if gateway is configured

### 7.5 Outbound Gateway Integration
- [x] Check for locally configured SMTP host in settings; if present, send email via local relay
- [x] Check for locally configured SMS gateway URL; if present, POST to local endpoint
- [x] If neither present: leave `OutboundMessage` in QUEUED status
- [x] `GET /api/notifications/outbound/queued/` — Admin can view and manually export queued messages

### 7.6 Frontend — Notification Inbox
- [x] Bell icon in TopBar with live unread count badge (polling every 30 seconds)
- [x] Full inbox page: filter by event type, read/unread
- [x] Notification row: event type badge, title, body preview, timestamp, read indicator (unread dot)
- [x] Click → expand full body + mark as read
- [x] "Mark all read" button

### 7.7 Frontend — Subscription Settings
- [x] List current subscriptions with event type and threshold value
- [x] Add subscription form: event type dropdown, optional threshold input
- [x] Remove subscription button per row
- [x] Digest schedule update: current send_time display + time input to change it

---

## Phase 8: Testing (Real DB + Real API Calls)

### 8.1 Backend Test Infrastructure
- [ ] Configure `pytest` + `pytest-django` using a dedicated test MySQL database
- [ ] Create `conftest.py` with real DB setup/teardown fixtures (no mocking)
- [ ] All test client calls use Django's `APIClient` against real views and real DB
- [ ] Seed fixture data via factory functions (not fixtures files) for isolation

### 8.2 Auth Tests
- [ ] Test login with valid credentials → JWT returned
- [ ] Test login with invalid credentials → 401
- [ ] Test token refresh flow
- [ ] Test role-based access: Inventory Manager cannot access crawl config endpoints

### 8.3 Inventory Tests
- [ ] Test receive stock → ledger entry created, balance updated
- [ ] Test FIFO issue → oldest lot consumed first
- [ ] Test moving-average cost recalculation on receive
- [ ] Test transfer → paired ledger entries, balances updated atomically
- [ ] Test cycle count variance < $500 → no confirmation required
- [ ] Test cycle count variance > $500 → confirmation step enforced
- [ ] Test safety stock breach detection after 10 consecutive minutes

### 8.4 Crawling Tests
- [ ] Test fingerprint deduplication → second enqueue returns existing task
- [ ] Test quota deduction within transaction → concurrent workers don't exceed rpm_limit
- [ ] Test exponential backoff scheduling on task failure
- [ ] Test checkpoint persistence → worker restarts resume from checkpoint_page
- [ ] Test canary: 5% of tasks use new version, 95% use active version
- [ ] Test auto-rollback when canary error rate > 2%

### 8.5 Notification Tests
- [ ] Test event dispatch → notifications created for all subscribed users
- [ ] Test unsubscribed users do not receive notifications
- [ ] Test read receipt: read_at timestamp set on mark-as-read
- [ ] Test digest aggregation creates single notification per user
- [ ] Test outbound message queued when no gateway configured

### 8.6 End-to-End Flow Tests
- [ ] Full receive → issue → balance check flow
- [ ] Crawl task enqueue → worker execute → request logged → debug log visible
- [ ] Canary release → error threshold exceeded → rollback triggered → notification sent

---

## Phase 9: Polish & Offline Validation

### 9.1 Offline Asset Audit
- [ ] Audit all HTML/JS/CSS for any external URL references (CDN, fonts, APIs)
- [ ] Bundle QuaggaJS locally in `frontend/src/vendor/`
- [ ] Verify all fonts are self-hosted or system fonts only
- [ ] Confirm `vite build` output has zero external dependencies

### 9.2 Performance & UX Polish
- [ ] Add loading skeletons to all data tables while fetching
- [ ] Add empty states with helpful guidance text (no bare blank screens)
- [ ] Debounce search inputs (300ms) to avoid excessive API calls
- [ ] Add optimistic UI updates on inventory mutations
- [ ] Ensure all modals are keyboard-accessible and have proper focus management

### 9.3 Error Handling
- [ ] Global Axios error interceptor → maps error codes to user-friendly messages
- [ ] Standardized DRF error response format: `{ code, message, details }`
- [ ] Network error detection: show "Offline — retrying…" banner if API unreachable
- [ ] Form validation errors displayed inline below each field

### 9.4 Security Hardening
- [ ] Confirm all sensitive DB fields are encrypted (spot-check with raw MySQL query)
- [ ] Confirm logs/audit trail shows `[REDACTED]` for token/secret fields
- [ ] Set `HttpOnly` + `Secure` cookie flags for refresh tokens
- [ ] Add `Content-Security-Policy` header blocking all external sources
- [ ] Review all endpoints for missing permission checks

### 9.5 Docker Production Readiness
- [ ] Add `nginx` service to `docker-compose.yml` as reverse proxy for frontend + backend
- [ ] Configure Gunicorn worker count (2 × CPU cores + 1)
- [ ] Set `DEBUG=False` in production compose profile
- [ ] Add healthcheck endpoints: `GET /api/health/` → `{ status: "ok", db: "ok", redis: "ok" }`
- [ ] Document deployment steps in `scripts/deploy.md`

### 9.6 Final Validation Checklist
- [ ] Disconnect test machine from internet; confirm all features work on local network only
- [ ] Verify `run_test.sh` starts all services from cold state in under 60 seconds
- [ ] Confirm no console errors in browser dev tools on any screen
- [ ] Confirm all role-based nav restrictions work correctly
- [ ] Load test crawl queue with 1000 tasks; verify quota and concurrency hold

---

## Progress Summary

| Phase | Status | Tasks Done | Tasks Total |
|---|---|---|---|
| Phase 1: Setup + Docker | [x] Complete | 34 | 34 |
| Phase 2: Backend Models | [ ] Pending | 0 | 29 |
| Phase 3: Auth & RBAC | [ ] Pending | 0 | 11 |
| Phase 4: Frontend Core | [ ] Pending | 0 | 22 |
| Phase 5: Inventory Ops | [ ] Pending | 0 | 36 |
| Phase 6: Crawling Engine | [x] Complete | 33 | 33 |
| Phase 7: Notifications | [x] Complete | 21 | 21 |
| Phase 8: Testing | [ ] Pending | 0 | 21 |
| Phase 9: Polish | [ ] Pending | 0 | 20 |
| **Total** | | **34** | **228** |
