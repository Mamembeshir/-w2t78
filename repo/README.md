# Warehouse Intelligence & Offline Crawling Operations Platform

A full-stack warehouse management system covering inventory control, procurement crawling, notification subscriptions, and role-based administration.

## Architecture & Tech Stack

* **Frontend:** React 18, TypeScript, TailwindCSS, React Query, Vite
* **Backend:** Python, Django, Django REST Framework, Celery
* **Database:** MySQL 8, Redis
* **Containerization:** Docker & Docker Compose (Required)

## Project Structure

```text
.
├── backend/                # Django application, Celery workers, Dockerfile
│   └── tests/
│       ├── api/            # API-level tests (real HTTP, real DB, JWT auth)
│       └── unit/           # Pure unit tests (models, services, tasks)
├── frontend/               # React/Vite application, Dockerfile
│   └── tests/
│       ├── unit/           # Vitest component/hook/page tests
│       └── e2e/            # Playwright end-to-end tests + playwright.config.ts
├── .env.example            # Example environment variables
├── docker-compose.yml      # Multi-container orchestration
├── run_tests.sh            # Standardized test execution script
└── README.md               # Project documentation
```

## Prerequisites

To ensure a consistent environment, this project is designed to run entirely within containers. You must have the following installed:

* [Docker](https://docs.docker.com/get-docker/)
* [Docker Compose](https://docs.docker.com/compose/install/)

## Running the Application

1. **Copy and configure the environment file:**
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` and replace every `CHANGE_ME` value. At minimum:

   | Variable | How to generate |
   |---|---|
   | `DJANGO_SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
   | `FIELD_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

   Django will refuse to start if either key is missing or set to a placeholder.

2. **Build and start containers:**
   ```bash
   docker-compose up --build -d
   ```
   All services start automatically. On first boot, migrations run and seed accounts are created.

3. **Access the app:**
   * Frontend: `http://localhost:5173`
   * Backend API: `http://localhost:8000/api`
   * API Health: `http://localhost:8000/api/health/`

4. **Stop the application:**
   ```bash
   docker-compose down -v
   ```

## Testing

All unit, integration, and E2E tests are executed via a single, standardized shell script. This script automatically handles container orchestration for the test environment.

Make sure the script is executable, then run it:

```bash
chmod +x run_tests.sh
./run_tests.sh
```

*Note: The `run_tests.sh` script outputs a standard exit code (`0` for success, non-zero for failure) to integrate smoothly with CI/CD validators.*

## Seeded Credentials

The database is pre-seeded with the following test users on startup. Use these credentials to verify authentication and role-based access controls.

| Role | Username | Password | Notes |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `Wh@reH0use!` | Full access to all system modules and user management. |
| **Inventory Manager** | `inv_manager` | `St0ck!Ctrl99` | Manages stock, warehouses, bins, and cycle counts. |
| **Procurement Analyst** | `analyst` | `Pr0cur3!Analy` | Manages crawl sources, rule versions, and tasks. |
