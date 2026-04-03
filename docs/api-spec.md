# HTTP API specification

**Base URL (local dev):** `http://localhost:8000`  
**API prefix:** `/api/` (unless noted)

Unless stated otherwise, endpoints expect JSON bodies and return JSON. Authenticated routes use **JWT**: send header `Authorization: Bearer <access_token>`.

---

## Health

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/api/health/` | No | Liveness: DB + Redis status (`status`, `db`, `redis`). |

---

## Authentication & users

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| POST | `/api/auth/login/` | No | Body: `username`, `password`. Returns `access`, `refresh`, `user`. Rate limited. |
| POST | `/api/auth/logout/` | Yes | Blacklist refresh token (body per SimpleJWT). |
| POST | `/api/auth/refresh/` | No | Refresh access token (SimpleJWT). |
| GET | `/api/auth/me/` | Yes | Current user profile. |
| POST | `/api/auth/register/` | No* | Optional registration when enabled via env; role fixed server-side. |

\* Behavior controlled by backend configuration (`REGISTRATION_OPEN`).

### User management (Admin)

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/api/users/` | Admin | List users. |
| POST | `/api/users/` | Admin | Create user. |
| GET | `/api/users/{id}/` | Admin | User detail. |
| PUT / PATCH | `/api/users/{id}/` | Admin | Update user (no end-user password in standard update; see reset). |
| POST | `/api/users/{id}/reset-password/` | Admin | Admin-initiated password reset. |

---

## Warehouses & bins

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/api/warehouses/` | Yes | List warehouses. |
| POST | `/api/warehouses/` | Admin | Create warehouse. |
| GET | `/api/warehouses/{id}/` | Yes | Warehouse detail. |
| PUT / PATCH | `/api/warehouses/{id}/` | Admin | Update warehouse. |
| GET | `/api/warehouses/{warehouse_pk}/bins/` | Yes | List bins for warehouse. |
| POST | `/api/warehouses/{warehouse_pk}/bins/` | Admin | Create bin. |
| GET | `/api/warehouses/{warehouse_pk}/bins/{id}/` | Yes | Bin detail. |
| PUT / PATCH | `/api/warehouses/{warehouse_pk}/bins/{id}/` | Admin | Update bin. |

---

## Inventory

### Items & balances

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/api/items/` | Yes | List/search items. |
| POST | `/api/items/` | Admin / Inv. Manager | Create item. |
| GET | `/api/items/{id}/` | Yes | Item detail. |
| PUT / PATCH | `/api/items/{id}/` | Admin / Inv. Manager | Update item. |
| GET | `/api/inventory/balances/` | Yes | Stock balances query. |

### Movements & cycle count

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| POST | `/api/inventory/receive/` | Inv. Manager | Receive stock into a bin. |
| POST | `/api/inventory/issue/` | Inv. Manager | Issue stock. |
| POST | `/api/inventory/transfer/` | Inv. Manager | Transfer between locations. |
| POST | `/api/inventory/cycle-count/start/` | Inv. Manager | Start cycle count session. |
| POST | `/api/inventory/cycle-count/{id}/submit/` | Inv. Manager | Submit counts / variance. |
| POST | `/api/inventory/cycle-count/{id}/confirm/` | Inv. Manager | Confirm when variance rules require it. |

Exact JSON fields match DRF serializers in `repo/backend/inventory/serializers.py` (source of truth for required keys and validation).

---

## Crawling

Prefix: `/api/crawl/`

| Resource | Router base | Typical operations |
| --- | --- | --- |
| Sources | `/api/crawl/sources/` | list, create, retrieve, update (ViewSet) |
| Rule versions | `/api/crawl/rule-versions/` | list, create, retrieve, update (ViewSet) |
| Tasks | `/api/crawl/tasks/` | list, create, retrieve, update + custom actions as implemented |

Refer to `repo/backend/crawling/views.py` for actions, filters, and permissions.

---

## Notifications

Prefix: `/api/notifications/`

| Resource | Router base | Description |
| --- | --- | --- |
| Subscriptions | `/subscriptions/` | Notification subscriptions CRUD. |
| Inbox | `/inbox/` | In-app notifications. |
| Outbound queue | `/outbound/queued/` | Queued outbound messages for local gateways. |

| Method | Path | Description |
| --- | --- | --- |
| GET/POST (etc.) | `/api/notifications/digest/` | Digest schedule endpoint (see `notifications/urls.py`). |

---

## Audit

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/api/audit/` | Admin (typical) | Audit log listing/query. |

---

## Errors

DRF returns standard HTTP status codes (`400`, `401`, `403`, `404`, `429`, `503`, etc.) with JSON error bodies (`detail`, field errors, or `message` depending on exception class). Health returns `503` when dependencies are unhealthy.

## Versioning

No URL version prefix in current deployment; contract is defined by the Django app and serializers in the repo at a given commit.
