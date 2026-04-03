# Warehouse Intelligence & Offline Crawling Operations Platform

## Start Command

```bash
docker compose up --build
```

All services start automatically. On first boot, migrations run and seed accounts are created.

---

## Service Addresses

| Service | Address |
|---|---|
| Frontend (UI) | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Health | http://localhost:8000/api/health/ |
| MySQL | localhost:3307 |
| Redis | localhost:6380 |

---

## Verification

1. Open http://localhost:8000/api/health/ — expect `{"status": "ok", "db": "ok", "redis": "ok"}`
2. Open http://localhost:5173 — the login page loads
3. Sign in with any seeded account below

---

## Seeded Accounts

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `Wh@reH0use!` |
| Inventory Manager | `inv_manager` | `St0ck!Ctrl99` |
| Procurement Analyst | `analyst` | `Pr0cur3!Analy` |

### Creating Additional Accounts

Use the **Admin → User Management** UI (sign in as `admin`) to create accounts for any role.

Self-registration via `POST /api/auth/register/` is **disabled by default**.
To enable it, set the environment variable before starting:

```bash
REGISTRATION_OPEN=true docker compose up --build
```

When enabled, the endpoint only creates `PROCUREMENT_ANALYST` accounts — role is fixed server-side and cannot be changed by the caller.

---

## Password Policy

- Minimum **10 characters**
- Cannot be entirely numeric
- Cannot be too similar to your username or email
- Cannot be a commonly used password
