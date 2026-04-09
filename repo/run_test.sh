#!/usr/bin/env bash
# =============================================================================
# run_test.sh — Warehouse Intelligence & Offline Crawling Operations Platform
# Starts all services (DB, Redis, backend, worker, beat, frontend) in the
# correct order and waits for each tier to be healthy before proceeding.
#
# Usage:
#   ./run_test.sh            Start all services (default)
#   ./run_test.sh start      Start all services
#   ./run_test.sh stop       Stop all services
#   ./run_test.sh restart    Restart all services
#   ./run_test.sh build      Rebuild all images then start
#   ./run_test.sh logs       Tail logs for all services
#   ./run_test.sh logs <svc> Tail logs for one service (e.g. backend)
#   ./run_test.sh status     Show container status
#   ./run_test.sh test              Run full test suite — backend + frontend (inside Docker)
#   ./run_test.sh test-backend      Run backend tests only (inside Docker)
#   ./run_test.sh test-frontend     Run frontend Vitest suite only (inside Docker)
#   ./run_test.sh shell             Open Django shell inside backend container
# =============================================================================

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m';  GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m';     RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
header()  { echo -e "\n${BOLD}${CYAN}$*${RESET}\n"; }

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"
COMPOSE="docker compose"

# ── Timeouts (seconds) ────────────────────────────────────────────────────────
DB_TIMEOUT=90        # max wait for MySQL to be healthy
BACKEND_TIMEOUT=60   # max wait for /api/health/ to respond
FRONTEND_TIMEOUT=45  # max wait for Vite dev server on port 5173

# ── Derive ports from .env (with defaults matching docker-compose.yml) ────────
load_ports() {
  MYSQL_HOST_PORT=3307
  REDIS_HOST_PORT=6380
  BACKEND_PORT=8000
  FRONTEND_PORT=5173
  if [[ -f "$ENV_FILE" ]]; then
    # Allow .env overrides (not currently set but future-proof)
    MYSQL_HOST_PORT="${MYSQL_HOST_PORT:-3307}"
    REDIS_HOST_PORT="${REDIS_HOST_PORT:-6380}"
  fi
}

# ── Prerequisite checks ───────────────────────────────────────────────────────

# Minimal check — only verifies Docker is available.
# Used by test commands so CI pipelines (which supply secrets via env vars,
# not a .env file) are never blocked by the local-secrets guard.
check_docker() {
  if ! docker info &>/dev/null; then
    error "Docker daemon is not running. Start Docker Desktop or dockerd first."
    exit 1
  fi
  if ! docker compose version &>/dev/null; then
    error "docker compose (v2) not found. Install Docker Desktop >= 3.6 or compose plugin."
    exit 1
  fi
}

# Replace CHANGE_ME placeholders in .env with auto-generated values.
# Called when .env is freshly copied from .env.example (e.g. in CI).
_generate_env_secrets() {
  info "Auto-generating secrets for CHANGE_ME placeholders..."

  # Random password (32 chars, URL-safe)
  _rand_pw() { python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32 | tr -d '/+=' | head -c 32; }

  local django_key
  django_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")

  local fernet_key
  fernet_key=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

  local db_password
  db_password=$(_rand_pw)

  local root_password
  root_password=$(_rand_pw)

  # Replace all CHANGE_ME values
  sed -i.bak "s|DJANGO_SECRET_KEY=CHANGE_ME.*|DJANGO_SECRET_KEY=${django_key}|" "$ENV_FILE"
  sed -i.bak "s|FIELD_ENCRYPTION_KEY=CHANGE_ME.*|FIELD_ENCRYPTION_KEY=${fernet_key}|" "$ENV_FILE"
  sed -i.bak "s|MYSQL_ROOT_PASSWORD=CHANGE_ME.*|MYSQL_ROOT_PASSWORD=${root_password}|" "$ENV_FILE"
  sed -i.bak "s|DB_PASSWORD=CHANGE_ME.*|DB_PASSWORD=${db_password}|" "$ENV_FILE"
  sed -i.bak "s|MYSQL_PASSWORD=CHANGE_ME.*|MYSQL_PASSWORD=${db_password}|" "$ENV_FILE"
  rm -f "${ENV_FILE}.bak"

  success "Secrets generated and written to .env"
}

# Full check — also validates the .env file.
# Used by start/build so the stack is never launched with placeholder secrets.
check_prerequisites() {
  header "Checking prerequisites"
  check_docker
  success "Docker daemon is running"
  success "docker compose $(docker compose version --short) available"

  # .env file
  if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$ENV_EXAMPLE" ]]; then
      warn ".env not found — copying from .env.example and generating secrets"
      cp "$ENV_EXAMPLE" "$ENV_FILE"
      _generate_env_secrets
      warn "Review .env and set real secrets before production use."
    else
      error ".env file missing and no .env.example to copy from."
      exit 1
    fi
  fi
  success ".env file present"

  # Abort if any CHANGE_ME placeholder remains in the active .env
  if grep -qi "CHANGE_ME" "$ENV_FILE" 2>/dev/null; then
    error "One or more CHANGE_ME placeholders remain in .env — replace them before starting the stack."
    error "Generate DJANGO_SECRET_KEY with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    exit 1
  fi
}

# ── Wait helpers ──────────────────────────────────────────────────────────────

# Wait for a container's Docker health check to reach "healthy"
wait_for_docker_health() {
  local service="$1"
  local timeout="$2"
  local container
  container=$(docker compose ps -q "$service" 2>/dev/null | head -1)

  if [[ -z "$container" ]]; then
    error "Container for service '$service' not found."
    return 1
  fi

  info "Waiting for $service to become healthy (up to ${timeout}s)..."
  local elapsed=0
  while true; do
    local health
    health=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "unknown")
    if [[ "$health" == "healthy" ]]; then
      success "$service is healthy"
      return 0
    fi
    if (( elapsed >= timeout )); then
      error "$service did not become healthy within ${timeout}s (last status: $health)"
      docker compose logs --tail=20 "$service"
      return 1
    fi
    sleep 3
    (( elapsed += 3 ))
    echo -ne "  ${YELLOW}...${elapsed}s${RESET}\r"
  done
}

# Wait for MySQL to actually accept queries (beyond the ping healthcheck)
wait_for_mysql() {
  local timeout="$DB_TIMEOUT"
  # First wait for Docker healthcheck
  wait_for_docker_health "db" "$timeout"

  info "Verifying MySQL accepts connections..."
  local elapsed=0
  local db_name
  db_name=$(grep "^DB_NAME=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "warehouse_db")
  local db_user
  db_user=$(grep "^DB_USER=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "warehouse_user")
  local db_pass
  db_pass=$(grep "^DB_PASSWORD=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "")

  while (( elapsed < 30 )); do
    if docker compose exec -T db \
        mysql -u"$db_user" -p"$db_pass" -e "SELECT 1;" "$db_name" &>/dev/null; then
      success "MySQL accepts connections on database '$db_name'"
      return 0
    fi
    sleep 2
    (( elapsed += 2 ))
  done
  warn "MySQL ping succeeded but direct query timed out — continuing anyway."
}

# Wait for HTTP endpoint to return 200
wait_for_http() {
  local label="$1"
  local url="$2"
  local timeout="$3"
  info "Waiting for $label at $url (up to ${timeout}s)..."
  local elapsed=0
  while (( elapsed < timeout )); do
    if curl -sf "$url" -o /dev/null 2>/dev/null; then
      success "$label is responding"
      return 0
    fi
    sleep 2
    (( elapsed += 2 ))
    echo -ne "  ${YELLOW}...${elapsed}s${RESET}\r"
  done
  warn "$label did not respond within ${timeout}s — check logs with: ./run_test.sh logs"
  return 1
}

# Wait for a TCP port to be open
wait_for_port() {
  local label="$1"
  local host="$2"
  local port="$3"
  local timeout="$4"
  info "Waiting for $label on port $port (up to ${timeout}s)..."
  local elapsed=0
  while (( elapsed < timeout )); do
    if nc -z "$host" "$port" &>/dev/null 2>&1; then
      success "$label is listening on port $port"
      return 0
    fi
    sleep 2
    (( elapsed += 2 ))
    echo -ne "  ${YELLOW}...${elapsed}s${RESET}\r"
  done
  warn "$label port $port did not open within ${timeout}s"
  return 1
}

# ── Print service URLs ────────────────────────────────────────────────────────
print_urls() {
  local backend_port="${BACKEND_PORT:-8000}"
  local frontend_port="${FRONTEND_PORT:-5173}"
  local mysql_port="${MYSQL_HOST_PORT:-3307}"
  local redis_port="${REDIS_HOST_PORT:-6380}"

  echo ""
  echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════╗${RESET}"
  echo -e "${BOLD}${GREEN}║   Warehouse Intelligence Platform — All Services Ready   ║${RESET}"
  echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════╝${RESET}"
  echo ""
  echo -e "  ${BOLD}Frontend (React/Vite):${RESET}   ${CYAN}http://localhost:${frontend_port}${RESET}"
  echo -e "  ${BOLD}Backend API:${RESET}            ${CYAN}http://localhost:${backend_port}/api/${RESET}"
  echo -e "  ${BOLD}Django Admin:${RESET}           ${CYAN}http://localhost:${backend_port}/admin/${RESET}"
  echo -e "  ${BOLD}Health Check:${RESET}           ${CYAN}http://localhost:${backend_port}/api/health/${RESET}"
  echo -e "  ${BOLD}MySQL (host):${RESET}           ${CYAN}localhost:${mysql_port}${RESET}  (DB: warehouse_db)"
  echo -e "  ${BOLD}Redis (host):${RESET}           ${CYAN}localhost:${redis_port}${RESET}"
  echo ""
  echo -e "  ${YELLOW}Useful commands:${RESET}"
  echo -e "    ${BOLD}./run_test.sh logs${RESET}           — tail all logs"
  echo -e "    ${BOLD}./run_test.sh logs backend${RESET}   — tail backend only"
  echo -e "    ${BOLD}./run_test.sh status${RESET}         — show container status"
  echo -e "    ${BOLD}./run_test.sh test${RESET}           — run full test suite (backend + frontend)"
  echo -e "    ${BOLD}./run_test.sh stop${RESET}           — stop all services"
  echo ""
}

# ── Core commands ─────────────────────────────────────────────────────────────

cmd_start() {
  load_ports
  check_prerequisites

  header "Phase 1 — Starting database and cache layer"
  $COMPOSE up -d db redis
  wait_for_mysql
  wait_for_docker_health "redis" 30

  header "Phase 2 — Starting application layer"
  $COMPOSE up -d backend worker beat
  wait_for_http "Backend API" "http://localhost:${BACKEND_PORT}/api/health/" "$BACKEND_TIMEOUT"

  header "Phase 3 — Starting frontend"
  $COMPOSE up -d frontend
  wait_for_port "Vite dev server" "localhost" "$FRONTEND_PORT" "$FRONTEND_TIMEOUT"

  print_urls
}

cmd_stop() {
  header "Stopping all services"
  $COMPOSE down
  success "All services stopped."
}

cmd_restart() {
  header "Restarting all services"
  $COMPOSE down
  cmd_start
}

cmd_build() {
  load_ports
  check_prerequisites
  header "Building all Docker images"
  $COMPOSE build
  success "Build complete."
  cmd_start
}

cmd_logs() {
  local service="${1:-}"
  if [[ -n "$service" ]]; then
    $COMPOSE logs -f "$service"
  else
    $COMPOSE logs -f
  fi
}

cmd_status() {
  header "Container status"
  $COMPOSE ps
}

# Run backend tests inside Docker.
# docker compose run respects depends_on, so DB + Redis start automatically.
cmd_test_backend() {
  load_ports
  check_docker
  header "Backend tests — inside Docker (real DB, no mocking)"
  $COMPOSE run --rm backend sh -c "
    export DJANGO_SECRET_KEY=\$(python -c 'import secrets; print(secrets.token_urlsafe(64))') && \
    python manage.py migrate --noinput 2>&1 && \
    python -m pytest tests/ --tb=short -v --no-header 2>&1
  "
}

# Run frontend Vitest suite inside Docker.
# --no-deps skips the backend dependency; Vitest is pure in-memory.
cmd_test_frontend() {
  check_docker
  header "Frontend tests — inside Docker (Vitest)"
  # Build the image directly so node_modules are installed inside the image
  # for the correct platform (Linux). No host volume mounts — fully isolated.
  info "Building frontend test image..."
  docker build \
    --target test \
    --tag warehouse-frontend-test:ci \
    --file "$SCRIPT_DIR/frontend/Dockerfile" \
    "$SCRIPT_DIR/frontend" \
    > /dev/null
  info "Running: vitest run"
  docker run --rm warehouse-frontend-test:ci npm run test
}

# Single command: run both suites entirely inside Docker.
cmd_test() {
  load_ports
  check_docker
  header "Full test suite — backend + frontend (all inside Docker)"

  local backend_exit=0
  local frontend_exit=0

  # ── Backend ────────────────────────────────────────────────────────────────
  echo ""
  info "▶ Backend tests (pytest, real DB)"
  $COMPOSE run --rm backend sh -c "
    export DJANGO_SECRET_KEY=\$(python -c 'import secrets; print(secrets.token_urlsafe(64))') && \
    python manage.py migrate --noinput 2>&1 && \
    python -m pytest tests/ --tb=short -v --no-header 2>&1
  " || backend_exit=$?

  # ── Frontend ───────────────────────────────────────────────────────────────
  echo ""
  info "▶ Frontend tests (Vitest)"
  cmd_test_frontend || frontend_exit=$?

  # ── Summary ────────────────────────────────────────────────────────────────
  echo ""
  if (( backend_exit == 0 && frontend_exit == 0 )); then
    success "All tests passed  (backend ✓   frontend ✓)"
  else
    (( backend_exit  != 0 )) && error "Backend tests FAILED  (exit $backend_exit)"
    (( frontend_exit != 0 )) && error "Frontend tests FAILED  (exit $frontend_exit)"
    return 1
  fi
}

cmd_shell() {
  header "Opening Django shell in backend container"
  $COMPOSE exec backend python manage.py shell
}

# ── Entrypoint ────────────────────────────────────────────────────────────────
main() {
  local cmd="${1:-start}"
  shift || true

  cd "$SCRIPT_DIR"

  case "$cmd" in
    start)          cmd_start ;;
    stop)           cmd_stop ;;
    restart)        cmd_restart ;;
    build)          cmd_build ;;
    logs)           cmd_logs "${1:-}" ;;
    status)         cmd_status ;;
    test)           cmd_test ;;
    test-backend)   cmd_test_backend ;;
    test-frontend)  cmd_test_frontend ;;
    shell)          cmd_shell ;;
    *)
      error "Unknown command: $cmd"
      echo ""
      echo "Usage: $0 [start|stop|restart|build|logs|status|test|test-backend|test-frontend|shell]"
      exit 1
      ;;
  esac
}

main "$@"
