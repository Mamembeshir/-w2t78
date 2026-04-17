#!/usr/bin/env bash
# =============================================================================
# run_tests.sh — Warehouse Intelligence & Offline Crawling Operations Platform
# Default: run the full test suite (backend → frontend → E2E).
# Use `start` to bring up services without running tests.
#
# Usage:
#   ./run_tests.sh           Run full test suite (default)
#   ./run_tests.sh start            Start all services only (no tests)
#   ./run_tests.sh stop             Stop all services
#   ./run_tests.sh restart          Restart all services
#   ./run_tests.sh build            Rebuild all images then start
#   ./run_tests.sh logs             Tail logs for all services
#   ./run_tests.sh logs <svc>       Tail logs for one service (e.g. backend)
#   ./run_tests.sh status           Show container status
#   ./run_tests.sh test             Run full test suite — backend + frontend + E2E (inside Docker)
#   ./run_tests.sh test-backend     Run backend tests only (inside Docker)
#   ./run_tests.sh test-frontend    Run frontend Vitest suite only (inside Docker)
#   ./run_tests.sh test-e2e         Run Playwright E2E suite (containerized)
#   ./run_tests.sh shell            Open Django shell inside backend container
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
# Uses Python to do the replacement — avoids sed portability issues.
_generate_env_secrets() {
  info "Auto-generating secrets for CHANGE_ME placeholders..."

  python3 -c "
import secrets, base64, os, re, sys

env_path = sys.argv[1]

# Generate app-level secrets (unique per environment)
# DB credentials use the same defaults as docker-compose.yml so that
# MySQL (which only reads passwords on first init) stays in sync.
replacements = {
    'DJANGO_SECRET_KEY': secrets.token_urlsafe(64),
    'FIELD_ENCRYPTION_KEY': base64.urlsafe_b64encode(os.urandom(32)).decode(),
    'MYSQL_ROOT_PASSWORD': 'dev_root_pw',
    'DB_PASSWORD': 'warehouse_pass',
    'MYSQL_PASSWORD': 'warehouse_pass',
}

with open(env_path, 'r') as f:
    content = f.read()

for key, value in replacements.items():
    content = re.sub(
        rf'^({re.escape(key)})\s*=\s*CHANGE_ME.*$',
        rf'\1={value}',
        content,
        flags=re.MULTILINE,
    )

with open(env_path, 'w') as f:
    f.write(content)
" "$ENV_FILE"

  success "Secrets generated and written to .env"
}

# Full check — also validates the .env file.
# Used by start/build so the stack is never launched with placeholder secrets.
check_prerequisites() {
  header "Checking prerequisites"
  check_docker
  success "Docker daemon is running"
  success "docker compose $(docker compose version --short) available"

  # .env file (ensure_env already ran in main, so this is a safety check)
  if [[ ! -f "$ENV_FILE" ]]; then
    error ".env file missing and no .env.example to copy from."
    exit 1
  fi
  success ".env file present"

  # Abort if any CHANGE_ME placeholder remains in a non-comment line
  if grep -v '^\s*#' "$ENV_FILE" 2>/dev/null | grep -qi "CHANGE_ME"; then
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
  warn "$label did not respond within ${timeout}s — check logs with: ./run_tests.sh logs"
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
  echo -e "    ${BOLD}./run_tests.sh logs${RESET}           — tail all logs"
  echo -e "    ${BOLD}./run_tests.sh logs backend${RESET}   — tail backend only"
  echo -e "    ${BOLD}./run_tests.sh status${RESET}         — show container status"
  echo -e "    ${BOLD}./run_tests.sh test${RESET}           — run full test suite (backend + frontend + E2E)"
  echo -e "    ${BOLD}./run_tests.sh test-e2e${RESET}       — run Playwright E2E only"
  echo -e "    ${BOLD}./run_tests.sh stop${RESET}           — stop all services"
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
# Reuses the cached image if it already exists and the Dockerfile + src haven't
# changed (detected via a checksum of the build context inputs).
cmd_test_frontend() {
  check_docker
  header "Frontend tests — inside Docker (Vitest)"

  local image_tag="warehouse-frontend-test:ci"
  local checksum_file="$SCRIPT_DIR/.frontend-test-image.sha"

  # Compute a checksum over build inputs AND test source files.
  # Changing a test file triggers a rebuild so the image always has the
  # latest tests baked in (the volume mount is a belt-and-suspenders backup).
  local current_sha
  current_sha=$(find "$SCRIPT_DIR/frontend" \
    -name "Dockerfile" -o -name "package.json" -o -name "package-lock.json" \
    -o -name "*.test.ts" -o -name "*.test.tsx" -o -name "vitest.config.ts" \
    | sort | xargs sha256sum 2>/dev/null | sha256sum | cut -c1-16)

  local cached_sha=""
  [[ -f "$checksum_file" ]] && cached_sha=$(cat "$checksum_file")

  # Check if image exists in Docker
  local image_exists=false
  docker image inspect "$image_tag" &>/dev/null && image_exists=true

  if [[ "$image_exists" == "true" && "$current_sha" == "$cached_sha" ]]; then
    info "Reusing cached frontend test image ($image_tag) — build inputs unchanged."
  else
    info "Building frontend test image (inputs changed or image missing)..."
    docker build \
      --target test \
      --tag "$image_tag" \
      --file "$SCRIPT_DIR/frontend/Dockerfile" \
      "$SCRIPT_DIR/frontend" \
      > /dev/null
    echo "$current_sha" > "$checksum_file"
    success "Frontend test image built and cached."
  fi

  info "Running: vitest run"
  # Mount both src and tests so that edits to either are picked up immediately
  # without needing a full image rebuild.
  docker run --rm \
    -v "$SCRIPT_DIR/frontend/src:/app/src:ro" \
    -v "$SCRIPT_DIR/frontend/tests:/app/tests:ro" \
    "$image_tag" npm run test
}

# Single command: run all suites — backend, frontend, and E2E.
# Pass --no-e2e to skip the E2E suite (e.g. in environments without a browser).
cmd_test() {
  load_ports
  check_docker
  header "Full test suite — backend + frontend + E2E"

  local run_e2e=true
  for arg in "$@"; do [[ "$arg" == "--no-e2e" ]] && run_e2e=false; done

  local backend_exit=0
  local frontend_exit=0
  local e2e_exit=0

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

  # ── E2E ────────────────────────────────────────────────────────────────────
  if [[ "$run_e2e" == "true" ]]; then
    echo ""
    info "▶ E2E tests (Playwright)"
    # Stack must be running; start it if not already up
    if ! curl -sf "http://localhost:${BACKEND_PORT:-8000}/api/health/" -o /dev/null 2>/dev/null; then
      info "Stack not running — starting services for E2E..."
      cmd_start
    fi
    cmd_test_e2e || e2e_exit=$?
  fi

  # ── Summary ────────────────────────────────────────────────────────────────
  echo ""
  if (( backend_exit == 0 && frontend_exit == 0 && e2e_exit == 0 )); then
    success "All tests passed  (backend ✓   frontend ✓   e2e ✓)"
  else
    (( backend_exit  != 0 )) && error "Backend tests FAILED  (exit $backend_exit)"
    (( frontend_exit != 0 )) && error "Frontend tests FAILED  (exit $frontend_exit)"
    (( e2e_exit      != 0 )) && error "E2E tests FAILED  (exit $e2e_exit)"
    return 1
  fi
}

# Run Playwright E2E suite inside a Docker container against the live stack.
# Requires the stack to be running (./run_tests.sh start) or called after cmd_start.
# Uses the official Playwright Docker image — no local browser/npm install needed.
cmd_test_e2e() {
  header "E2E tests — Playwright (containerized, full-stack, real browser)"

  local e2e_dir="$SCRIPT_DIR/frontend/tests/e2e"
  local image_tag="warehouse-e2e:ci"

  info "Building E2E test image (--target e2e from frontend/Dockerfile)..."
  docker build --quiet \
    --target e2e \
    --tag "$image_tag" \
    --file "$SCRIPT_DIR/frontend/Dockerfile" \
    "$SCRIPT_DIR/frontend"
  success "E2E image ready."

  # Reach the host stack from inside the container.
  # --add-host=host.docker.internal:host-gateway works on Linux and is a no-op
  # on macOS/Windows Docker Desktop where the alias is provided automatically.
  local frontend_url="http://host.docker.internal:${FRONTEND_PORT:-5173}"

  local api_url="http://host.docker.internal:${BACKEND_PORT:-8000}"

  info "Running Playwright tests (frontend=$frontend_url  api=$api_url)..."
  docker run --rm \
    --add-host=host.docker.internal:host-gateway \
    -e FRONTEND_URL="$frontend_url" \
    -e API_URL="$api_url" \
    -v "$e2e_dir/playwright-report:/e2e/playwright-report" \
    -v "$e2e_dir/test-results:/e2e/test-results" \
    "$image_tag" "$@"
}

cmd_shell() {
  header "Opening Django shell in backend container"
  $COMPOSE exec backend python manage.py shell
}

# ── Ensure .env exists ────────────────────────────────────────────────────────
# Called at the very top of main() — before any Docker commands — so that
# docker compose up always sees a valid .env and MySQL initialises with the
# correct passwords on first boot.
ensure_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "$ENV_EXAMPLE" ]]; then
      warn ".env not found — copying from .env.example and generating secrets"
      cp "$ENV_EXAMPLE" "$ENV_FILE"
      _generate_env_secrets
    fi
  fi
}

# ── Entrypoint ────────────────────────────────────────────────────────────────
main() {
  local cmd="${1:-test}"
  shift || true

  cd "$SCRIPT_DIR"
  ensure_env

  case "$cmd" in
    start)          cmd_start ;;
    stop)           cmd_stop ;;
    restart)        cmd_restart ;;
    build)          cmd_build ;;
    logs)           cmd_logs "${1:-}" ;;
    status)         cmd_status ;;
    test)           cmd_test "$@" ;;
    test-backend)   cmd_test_backend ;;
    test-frontend)  cmd_test_frontend ;;
    test-e2e)       cmd_test_e2e "$@" ;;
    shell)          cmd_shell ;;
    *)
      error "Unknown command: $cmd"
      echo ""
      echo "Usage: $0 [test|start|stop|restart|build|logs|status|test-backend|test-frontend|test-e2e|shell]"
      exit 1
      ;;
  esac
}

main "$@"
