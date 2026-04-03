# CLAUDE.md — Warehouse Intelligence & Offline Crawling Operations Platform

## Read First (Always)
Before every response, read these files in order:
1. `SPEC.md` — full project specification
2. `CLAUDE.md` — this file (rules and clarifications)
3. `PLAN.md` — current implementation plan and progress

---

## Project Overview
**Warehouse Intelligence & Offline Crawling Operations Platform**

A fully offline, local-network-only platform for procurement analysts, inventory managers, and system administrators to collect product/supplier data, maintain accurate inventory, and receive operational notifications — all without any internet dependency.

---

## Tech Stack (Strict — Do Not Deviate)

| Layer | Technology |
|---|---|
| Frontend | React 19 + TypeScript + Vite + TailwindCSS |
| Backend | Django 5 + Django REST Framework |
| Database | MySQL (system of record) |
| Task Queue | Celery + Redis (local) |
| Containerization | Docker + docker-compose |
| Password Hashing | Argon2 |
| UI Style | Premium dark enterprise, touch-friendly |

---

## Strict Development Rules

### Workflow
- **Do ONE small focused task per response.** Never bundle multiple features.
- After completing a task: update `PLAN.md` to reflect progress, then commit with a clear message.
- Always read `SPEC.md`, `CLAUDE.md`, and `PLAN.md` before starting any task.

### Testing
- All API tests must use a **REAL database** and **REAL network calls**.
- **No mocking allowed** — no `unittest.mock`, no `MagicMock`, no patched HTTP calls.
- Maintain `run_test.sh` at the repo root to start frontend + backend + DB in one command.

### UI/UX Standards
- **Premium dark enterprise style**: dark backgrounds, subtle gradients, clean typography.
- Generous spacing and padding — designed for warehouse kiosk and tablet use.
- Large touch-friendly buttons and inputs (minimum 44px tap targets).
- Clear, readable data tables with hover states and row actions.
- Consistent component library — no mixing of ad-hoc styles.
- Mobile/kiosk-first layout considerations on all inventory screens.

### Security
- Passwords hashed with **Argon2** (never bcrypt or PBKDF2).
- Sensitive fields encrypted at rest (see Clarification #8 below).
- Logs must mask tokens and secrets by default.
- No external auth providers — username/password only.
- All audit trails retained for **365 days** with automatic cleanup.

### Offline Constraint
- **Zero internet dependency** — no CDN links, no external API calls, no cloud services.
- All assets served locally; all crawling uses locally defined rules only.
- Notifications delivered in-app and to locally hosted SMTP/SMS gateways only.

### Commits
- Use clear, descriptive commit messages: `feat:`, `fix:`, `chore:`, `docs:`, `test:` prefixes.
- Never commit secrets, `.env` files, or credentials.

---

## Resolved Clarifications

### 1. Crawling Rule Canary Release
New rule versions are applied to **5% of crawl tasks** for a **30-minute window**. If the error rate exceeds **2%** during that window, the system automatically rolls back to the prior version in one click. Canary state is tracked per rule version in the database.

### 2. Safety Stock Alert Flapping Prevention
Safety stock alerts trigger only when available quantity remains below the configured threshold for **10 consecutive minutes**. A persistent sliding-window state machine tracks breach start time; alerts clear only after quantity recovers above threshold.

### 3. Crawling Task Idempotency
Each crawl task generates a **deterministic fingerprint** from: URL + sorted parameters + relevant headers. Tasks with duplicate fingerprints are skipped or deduplicated at scheduling time, not at execution time.

### 4. Quota & Concurrency Control
Quota is **deducted before** the request executes, inside a database transaction with row-level locking. On failure or success, quota is released. Held quotas are automatically released after **15 minutes** to prevent oversubscription. Waitlisted tasks auto-promote within **5 seconds** when capacity frees.

### 5. Inventory Costing Methods
Costing method (**FIFO** or **Moving Average**) is configured **per SKU**. Both methods can coexist across different SKUs in the same warehouse.

### 6. Cycle Count Variance Confirmation
Step-by-step wizard: (1) scan or enter item identifier → (2) system shows expected quantity vs actual counted → (3) if variance exceeds threshold ($500.00), require a reason code and supervisor confirmation before posting.

### 7. Offline Notification Delivery
In-app notifications are **always shown**. Outbound messages are queued for locally hosted SMTP/SMS gateways. If no gateway is present, messages remain queued and are available for manual export. No external provider is ever contacted.

### 8. Sensitive Data Encryption Scope
Encrypt at rest: supplier API keys, supplier passwords, crawl rule secrets, request header values marked as credentials, and any field storing tokens or private keys. Use Django's encrypted field library with a local key stored in environment config.

### 9. Crawler Anti-Bot Strategies
User-agent rotation and crawl delay are **configurable per crawl source**. Each source definition includes: a list of user-agent strings to rotate, a minimum crawl delay (seconds), and whether to honor `Crawl-Delay` from robots.txt equivalents in the local ruleset.

### 10. Audit Trail Retention
Hardcoded **365-day retention** for all audit logs, send logs, and retry records. A scheduled Celery task runs nightly to purge records older than 365 days. Admins cannot override this value through the UI.

### 11. Barcode/RFID Scanning
Support both: (a) **manual keyboard entry** for barcode/RFID identifiers, and (b) **browser-based camera scanning** using QuaggaJS (or equivalent, bundled locally — no CDN). External USB/serial scanners work automatically via keyboard-wedge input into the text field.

---

## Key Business Rules (from SPEC.md)

| Rule | Value |
|---|---|
| Default crawl rate limit | 60 requests/minute per source |
| Visual debugger sample size | Last 20 request/response samples |
| Canary release window | 30 minutes at 5% of tasks |
| Canary rollback threshold | Error rate > 2% |
| Retry backoff schedule | 10s → 30s → 2m → 10m (max 5 attempts) |
| Checkpoint interval | Every 100 pages |
| Quota timeout hold | 15 minutes auto-release |
| Waitlist promotion | Within 5 seconds of capacity freeing |
| Slow-moving stock flag | No issues for 90 days |
| Safety stock flap window | 10 consecutive minutes below threshold |
| Digest notification time | 6:00 PM daily |
| Audit log retention | 365 days |
| Cycle count variance alert | > $500.00 requires confirmation |
