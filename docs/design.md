# System design — Warehouse Intelligence & Offline Crawling Operations Platform

## Purpose

Local-network platform for procurement analysts, inventory managers, and administrators to collect product/supplier data via configurable crawl rules, maintain warehouse inventory, and receive operational notifications without internet connectivity.

## High-level architecture

| Layer | Responsibility |
| --- | --- |
| React SPA (Vite) | Role-based UI, forms, tables, client-side routing |
| Django REST API | Authentication, authorization, business rules, persistence |
| MySQL | System of record for users, warehouses, inventory, crawl metadata, audit |
| Celery + Redis | Background tasks (notifications, scheduled jobs, retention) |

All services run on-prem (e.g. Docker Compose). No external SaaS or CDN dependencies.

## Major domains

1. **Accounts** — JWT auth (access + refresh), user CRUD and password reset for admins, optional self-registration when enabled.
2. **Warehouse** — Warehouses and bins; soft-delete aware listing for navigation and stock placement.
3. **Inventory** — Items, lots/serials where applicable, stock balances, receive/issue/transfer, cycle count workflow with variance handling.
4. **Crawling** — Sources, rule versions, crawl tasks (scheduler/worker integration per product phases).
5. **Notifications** — In-app inbox, subscriptions, outbound queue for local SMTP/SMS gateways, digest scheduling.
6. **Audit** — Administrative audit log for compliance (365-day retention policy per product rules).

## Cross-cutting concerns

- **Security:** Argon2 password hashing; JWT for API access; sensitive fields encrypted at rest where implemented; logs avoid leaking tokens.
- **Permissions:** Role-based (e.g. Admin, Inventory Manager, Procurement Analyst) enforced in DRF permissions on views/viewsets.
- **Consistency:** Inventory movements and quota-style operations use transactions and locking where required by SPEC (see `SPEC.md` and `CLAUDE.md` for numeric thresholds and workflows).
- **Offline operation:** Static assets and API are served from the local deployment; crawl rules and notifications do not call the public internet.

## Frontend design

- Dark, enterprise-oriented layout with touch-friendly targets (see `CLAUDE.md` UI standards).
- Dynamic routes aligned with roles; inventory flows emphasize scanning/entry and clear confirmation steps.
- Error and loading states shared across pages (tables, modals, forms).

## Extensibility

New API areas are mounted under `/api/` (or `/api/<domain>/`) in `config/urls.py`. New UI areas follow the React router and layout shell pattern in `repo/frontend`.
