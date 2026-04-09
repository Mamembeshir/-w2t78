# Warehouse Intelligence & Offline Crawling Operations Platform

## Prerequisites

Before starting for the first time, create a `.env` file with real secret values:

```bash
cp docker/.env.example .env
```

Then edit `.env` and replace every `CHANGE_ME` value. At minimum:

| Variable | How to generate |
|---|---|
| `DJANGO_SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `FIELD_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

Django will refuse to start if either key is missing, a placeholder, or the known dev default.

---

## Start Command

> **Before running:** complete the [Prerequisites](#prerequisites) above — copy `.env.example` to `.env` and replace every `CHANGE_ME` value. Django will refuse to start with a placeholder key.

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

## Testing

All tests run inside Docker containers against a real MySQL database — no mocking.
Services must be running (or the test commands will start the data layer automatically).

### Commands

| Command | What it runs |
|---|---|
| `./run_test.sh test` | Full Django test suite (all apps) |
| `./run_test.sh test-frontend` | Vitest suite inside the frontend container |
| `./run_test.sh test-all` | Backend + frontend suites in sequence |

### Environment assumptions

- A `.env` file must exist at the repo root (copy `.env.example` and fill in real values).
- `DJANGO_SECRET_KEY` and `FIELD_ENCRYPTION_KEY` must be set to valid values — Django will refuse to start without them.
- Tests use the same MySQL instance as the running stack (`--keepdb` is used internally); the DB is not wiped between runs.
- No internet access is required or expected — everything runs on localhost.

### Running a single app's tests

```bash
docker compose exec backend python manage.py test notifications --verbosity=2 --keepdb
docker compose exec backend python manage.py test crawling --verbosity=2 --keepdb
docker compose exec backend python manage.py test accounts --verbosity=2 --keepdb
```

---

## Password Policy

- Minimum **10 characters**
- Cannot be entirely numeric
- Cannot be too similar to your username or email
- Cannot be a commonly used password
