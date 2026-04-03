# Deployment Guide — Warehouse Intelligence Platform

## Prerequisites
- Docker 24+ and Docker Compose v2 installed on the host
- No internet access required — all images and assets are local
- Minimum 2 vCPU, 4 GB RAM recommended

## First-time setup

```bash
# 1. Copy and fill in environment config
cp docker/.env.example .env
# Edit .env: set DB passwords, DJANGO_SECRET_KEY, FIELD_ENCRYPTION_KEY

# 2. Build all images (no internet needed after first pull)
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# 3. Start all services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 4. Verify health
curl http://localhost/api/health/
# Expected: {"status":"ok","db":"ok","redis":"ok"}
```

## Environment variables (required for production)

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | Random 50+ char secret — never reuse between environments |
| `FIELD_ENCRYPTION_KEY` | Fernet key for at-rest field encryption (generate once, store safely) |
| `DB_PASSWORD` / `MYSQL_PASSWORD` | MySQL user password |
| `MYSQL_ROOT_PASSWORD` | MySQL root password |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames (e.g. `warehouse.local,192.168.1.10`) |
| `CORS_ALLOWED_ORIGINS` | Frontend origin (e.g. `http://warehouse.local`) |
| `GUNICORN_WORKERS` | Default `5`; set to `(2 × nproc) + 1` |

Generate the encryption key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Scaling Gunicorn workers

Edit `.env` or `docker-compose.prod.yml`:
```
GUNICORN_WORKERS=9   # for 4-core host: (2×4)+1
```

## Upgrading

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
# Migrations run automatically on backend container start
```

## Backup

```bash
# Database
docker compose exec db mysqldump -u root -p"${MYSQL_ROOT_PASSWORD}" warehouse_db > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T db mysql -u root -p"${MYSQL_ROOT_PASSWORD}" warehouse_db < backup_20260101.sql
```

## Health checks

- Backend: `GET /api/health/` → `{"status":"ok","db":"ok","redis":"ok"}`
- Frontend: `GET /` → 200 (nginx serves index.html)
- MySQL: `docker compose exec db mysqladmin ping -u root`
- Redis: `docker compose exec redis redis-cli ping`
