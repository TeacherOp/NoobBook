#!/usr/bin/env bash
# =============================================================================
# NoobBook Docker Setup — one command to start everything.
#
# Usage:
#   bash docker/setup.sh
#
# What it does:
#   1. Checks prerequisites (Docker, Docker Compose, Python3)
#   2. Generates Supabase secrets (JWT, passwords, tokens)
#   3. Creates .env files from templates
#   4. Cleans up orphaned state from previous runs
#   5. Creates the shared Docker network
#   6. Creates edge functions placeholder (prevents container crash)
#   7. Starts Supabase and waits for it to become healthy
#   8. Creates MinIO storage bucket (for macOS compatibility)
#   9. Builds and starts NoobBook (backend + frontend + migration)
#   10. Waits for database migration
#   11. Prints access URLs
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ---- Step 1: Prerequisites ----
info "Checking prerequisites..."

command -v docker >/dev/null 2>&1 || error "Docker is not installed. See https://docs.docker.com/get-docker/"

# Verify Docker daemon is actually running (not just installed)
if ! docker info >/dev/null 2>&1; then
    error "Docker is installed but not running. Please start Docker Desktop and try again."
fi

# Check for docker compose (v2 plugin or standalone docker-compose)
if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    error "Docker Compose is not installed. See https://docs.docker.com/compose/install/"
fi

# Python3 is required for JWT generation (macOS LibreSSL segfaults with openssl)
command -v python3 >/dev/null 2>&1 || error "Python3 is not installed. Install via: brew install python3"

success "Docker and Docker Compose found ($COMPOSE)"

# Stop any existing NoobBook/Supabase containers so ports are freed before checks.
# This makes setup.sh safe to re-run without manually stopping first.
info "Stopping any existing containers..."
$COMPOSE -f "$ROOT_DIR/docker-compose.yml" down 2>/dev/null || true
$COMPOSE -f "$SCRIPT_DIR/supabase/docker-compose.yml" down 2>/dev/null || true

# Check for port conflicts (now that our own containers are stopped)
check_port() {
    local port="$1" service="$2"
    if lsof -iTCP:"$port" -sTCP:LISTEN -P -n >/dev/null 2>&1; then
        error "Port $port is already in use (needed for $service). Stop the conflicting service and try again."
    fi
}
check_port 80 "NoobBook frontend"
check_port 5001 "NoobBook backend"
check_port 8000 "Supabase API gateway"
check_port 5432 "PostgreSQL"
success "Required ports are available (80, 5001, 8000, 5432)"

# ---- Step 2: Generate secrets ----
generate_password() {
    openssl rand -base64 32 | tr -d '/+=' | head -c 40
}

generate_hex() {
    openssl rand -hex "$1"
}

# Portable in-place env var replacement (works on both macOS and Linux).
# Replaces lines like KEY=anything with KEY=new_value, preserving values
# that contain special characters (=, /, +).
replace_env_var() {
    local file="$1" key="$2" value="$3"
    local tmp="${file}.tmp"
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" == "${key}="* ]]; then
            echo "${key}=${value}"
        else
            echo "$line"
        fi
    done < "$file" > "$tmp"
    mv "$tmp" "$file"
}

generate_jwt() {
    local role="$1"
    local secret="$2"
    # Use Python for JWT generation — macOS LibreSSL's openssl dgst -hmac -binary
    # can segfault (exit 139) on certain versions.
    python3 -c "
import hmac, hashlib, base64, json

def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

header = json.dumps({'alg':'HS256','typ':'JWT'}, separators=(',',':')).encode()
payload = json.dumps({'role':'${role}','iss':'supabase','iat':1641769200,'exp':1799535600}, separators=(',',':')).encode()

h = b64url(header)
p = b64url(payload)
sig = hmac.new('${secret}'.encode(), f'{h}.{p}'.encode(), hashlib.sha256).digest()

print(f'{h}.{p}.{b64url(sig)}')
"
}

# ---- Step 3: Create .env files ----
SUPABASE_ENV="$SCRIPT_DIR/supabase/.env"
NOOBBOOK_ENV="$SCRIPT_DIR/.env"

# If a previous run left a broken/incomplete .env, delete it so we recreate from template
if [ -f "$SUPABASE_ENV" ] && ! grep -q '^POSTGRES_HOST=' "$SUPABASE_ENV"; then
    warn "Supabase .env is incomplete (missing core variables) — deleting to recreate..."
    rm -f "$SUPABASE_ENV"
fi

# If .env is missing but DB data directory exists from a previous run, the new
# generated password won't match the existing database. Wipe the orphaned DB
# data so Postgres re-initializes with the new credentials.
DB_DATA_DIR="$SCRIPT_DIR/supabase/volumes/db/data"
if [ ! -f "$SUPABASE_ENV" ] && [ -d "$DB_DATA_DIR" ] && [ "$(ls -A "$DB_DATA_DIR" 2>/dev/null)" ]; then
    warn "Found orphaned DB data without matching .env — removing stale DB volume..."
    $COMPOSE -f "$SCRIPT_DIR/supabase/docker-compose.yml" down --remove-orphans 2>/dev/null || true
    rm -rf "$DB_DATA_DIR"
    success "Stale DB data removed — fresh database will be created"
fi

# Generate Supabase secrets if .env doesn't exist yet
if [ ! -f "$SUPABASE_ENV" ]; then
    info "Generating Supabase secrets..."
    POSTGRES_PASSWORD=$(generate_password)
    JWT_SECRET=$(generate_hex 32)
    SECRET_KEY_BASE=$(generate_hex 48)
    VAULT_ENC_KEY=$(generate_hex 16)
    PG_META_CRYPTO_KEY=$(generate_hex 16)
    DASHBOARD_PASSWORD=$(generate_password)
    LOGFLARE_PUBLIC=$(generate_hex 24)
    LOGFLARE_PRIVATE=$(generate_hex 24)
    POOLER_TENANT_ID=$(generate_hex 8)

    ANON_KEY=$(generate_jwt "anon" "$JWT_SECRET")
    SERVICE_ROLE_KEY=$(generate_jwt "service_role" "$JWT_SECRET")

    # Write Supabase .env from template with generated values
    cp "$SCRIPT_DIR/supabase/.env.example" "$SUPABASE_ENV"

    # Replace placeholder values with generated secrets (portable across macOS and Linux)
    replace_env_var "$SUPABASE_ENV" "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD"
    replace_env_var "$SUPABASE_ENV" "JWT_SECRET" "$JWT_SECRET"
    replace_env_var "$SUPABASE_ENV" "ANON_KEY" "$ANON_KEY"
    replace_env_var "$SUPABASE_ENV" "SERVICE_ROLE_KEY" "$SERVICE_ROLE_KEY"
    replace_env_var "$SUPABASE_ENV" "DASHBOARD_PASSWORD" "$DASHBOARD_PASSWORD"
    replace_env_var "$SUPABASE_ENV" "SECRET_KEY_BASE" "$SECRET_KEY_BASE"
    replace_env_var "$SUPABASE_ENV" "VAULT_ENC_KEY" "$VAULT_ENC_KEY"
    replace_env_var "$SUPABASE_ENV" "PG_META_CRYPTO_KEY" "$PG_META_CRYPTO_KEY"
    replace_env_var "$SUPABASE_ENV" "LOGFLARE_PUBLIC_ACCESS_TOKEN" "$LOGFLARE_PUBLIC"
    replace_env_var "$SUPABASE_ENV" "LOGFLARE_PRIVATE_ACCESS_TOKEN" "$LOGFLARE_PRIVATE"
    replace_env_var "$SUPABASE_ENV" "POOLER_TENANT_ID" "$POOLER_TENANT_ID"

    success "Supabase .env created with generated secrets"
else
    info "Supabase .env already exists, reading existing values..."
    # shellcheck disable=SC1090
    source "$SUPABASE_ENV"
    # If a previous run crashed (e.g. LibreSSL segfault) the file may exist
    # but JWT keys may be missing or still hold placeholder values.
    JWT_SECRET="${JWT_SECRET:-$(generate_hex 32)}"
    POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(generate_password)}"
    if [ -z "${ANON_KEY:-}" ] || [[ "${ANON_KEY}" == *"supabase-demo"* ]]; then
        warn "ANON_KEY missing or placeholder — regenerating JWT keys..."
        ANON_KEY=$(generate_jwt "anon" "$JWT_SECRET")
        SERVICE_ROLE_KEY=$(generate_jwt "service_role" "$JWT_SECRET")
        replace_env_var "$SUPABASE_ENV" "JWT_SECRET" "$JWT_SECRET"
        replace_env_var "$SUPABASE_ENV" "ANON_KEY" "$ANON_KEY"
        replace_env_var "$SUPABASE_ENV" "SERVICE_ROLE_KEY" "$SERVICE_ROLE_KEY"
        success "JWT keys regenerated"
    else
        SERVICE_ROLE_KEY="${SERVICE_ROLE_KEY}"
    fi
fi

# Same guard for NoobBook .env
if [ -f "$NOOBBOOK_ENV" ] && ! grep -q '^SUPABASE_URL=' "$NOOBBOOK_ENV"; then
    warn "NoobBook .env is incomplete — deleting to recreate..."
    rm -f "$NOOBBOOK_ENV"
fi

# Create NoobBook .env if it doesn't exist
if [ ! -f "$NOOBBOOK_ENV" ]; then
    # Bootstrap-admin precondition (fresh-deploy only).
    # Refusing to proceed without explicit operator intent here closes
    # the "first signup wins admin" race. If you're running this on a
    # box where you've already pre-seeded an admin user some other way,
    # just put the same email/password in the shell env and the same
    # values land in the .env on this run.
    if [ -z "${NOOBBOOK_BOOTSTRAP_ADMIN_EMAIL:-}" ] || [ -z "${NOOBBOOK_BOOTSTRAP_ADMIN_PASSWORD:-}" ]; then
        error "Fresh deploy detected (no docker/.env yet). Set NOOBBOOK_BOOTSTRAP_ADMIN_EMAIL and NOOBBOOK_BOOTSTRAP_ADMIN_PASSWORD in your shell env before running setup.sh. Example:
  export NOOBBOOK_BOOTSTRAP_ADMIN_EMAIL='you@example.com'
  export NOOBBOOK_BOOTSTRAP_ADMIN_PASSWORD='\$(openssl rand -base64 24)'
  bash docker/setup.sh"
    fi

    info "Creating NoobBook .env from template..."
    cp "$SCRIPT_DIR/.env.example" "$NOOBBOOK_ENV"

    # Persist the bootstrap admin into the .env so subsequent
    # container restarts can call bootstrap_admin_from_env() without
    # depending on the operator's shell.
    replace_env_var "$NOOBBOOK_ENV" "NOOBBOOK_BOOTSTRAP_ADMIN_EMAIL" "$NOOBBOOK_BOOTSTRAP_ADMIN_EMAIL"
    replace_env_var "$NOOBBOOK_ENV" "NOOBBOOK_BOOTSTRAP_ADMIN_PASSWORD" "$NOOBBOOK_BOOTSTRAP_ADMIN_PASSWORD"

    # Source Supabase env to get generated keys
    # shellcheck disable=SC1090
    source "$SUPABASE_ENV"

    replace_env_var "$NOOBBOOK_ENV" "SUPABASE_ANON_KEY" "$ANON_KEY"
    replace_env_var "$NOOBBOOK_ENV" "SUPABASE_SERVICE_KEY" "$SERVICE_ROLE_KEY"
    replace_env_var "$NOOBBOOK_ENV" "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD"
    # JWT_SECRET so the backend verifies user JWTs locally (no Kong roundtrip).
    replace_env_var "$NOOBBOOK_ENV" "JWT_SECRET" "$JWT_SECRET"
    replace_env_var "$NOOBBOOK_ENV" "SECRET_KEY" "$(generate_password)"

    success "NoobBook .env created"

    # Prompt for API keys if they're empty
    # shellcheck disable=SC1090
    source "$NOOBBOOK_ENV"
    if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
        warn "ANTHROPIC_API_KEY is not set in docker/.env"
        warn "Edit docker/.env and add your API keys before the app will work."
    fi
else
    info "NoobBook .env already exists, syncing Supabase keys..."
    # shellcheck disable=SC1090
    source "$SUPABASE_ENV"
    # Always sync Supabase-managed keys (user API keys are never touched)
    replace_env_var "$NOOBBOOK_ENV" "SUPABASE_ANON_KEY" "$ANON_KEY"
    replace_env_var "$NOOBBOOK_ENV" "SUPABASE_SERVICE_KEY" "$SERVICE_ROLE_KEY"
    replace_env_var "$NOOBBOOK_ENV" "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD"
    # JWT_SECRET so the backend can verify JWTs locally (eliminates the
    # /auth/v1/user roundtrip on every API request — was the dominant
    # latency contributor on dashboard loads).
    replace_env_var "$NOOBBOOK_ENV" "JWT_SECRET" "$JWT_SECRET"
    success "Supabase keys synced from supabase/.env"
fi

# ---- Step 4: Create Docker network ----
if ! docker network inspect noobbook-network >/dev/null 2>&1; then
    info "Creating Docker network: noobbook-network"
    docker network create noobbook-network
    success "Network created"
else
    info "Docker network noobbook-network already exists"
fi

# ---- Step 5: Create edge functions placeholder ----
# This prevents the edge-functions container from crashing on startup
FUNCTIONS_DIR="$SCRIPT_DIR/supabase/volumes/functions/main"
if [ ! -f "$FUNCTIONS_DIR/index.ts" ]; then
    info "Creating edge functions placeholder..."
    mkdir -p "$FUNCTIONS_DIR"
    cat > "$FUNCTIONS_DIR/index.ts" << 'EOF'
// Placeholder edge function - not used by NoobBook
// This file exists to prevent the edge-functions container from crashing

Deno.serve(() => new Response("Edge Functions not used by NoobBook"));
EOF
    success "Edge functions placeholder created"
fi

# ---- Step 6: Start Supabase ----
info "Starting Supabase services..."
$COMPOSE -f "$SCRIPT_DIR/supabase/docker-compose.yml" --env-file "$SUPABASE_ENV" up -d

# ---- Step 7: Wait for Kong health ----
info "Waiting for Supabase API gateway (Kong) to become healthy..."
TIMEOUT=120
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    if docker exec supabase-kong kong health >/dev/null 2>&1; then
        success "Supabase is healthy"
        break
    fi
    sleep 3
    ELAPSED=$((ELAPSED + 3))
    printf "."
done
echo ""

if [ $ELAPSED -ge $TIMEOUT ]; then
    error "Supabase did not become healthy within ${TIMEOUT}s. Check: docker logs supabase-kong"
fi

# ---- Step 8: Create MinIO storage bucket ----
# macOS Docker doesn't support xattr, so we use MinIO for S3-compatible storage
info "Creating MinIO storage bucket..."
sleep 5  # Wait for MinIO to be fully ready
MINIO_USER=$(grep -m1 '^MINIO_ROOT_USER=' "$SUPABASE_ENV" 2>/dev/null | cut -d= -f2- || true)
MINIO_USER="${MINIO_USER:-supabase}"
MINIO_PASS=$(grep -m1 '^MINIO_ROOT_PASSWORD=' "$SUPABASE_ENV" 2>/dev/null | cut -d= -f2- || true)
MINIO_PASS="${MINIO_PASS:-supabase123}"
if docker exec supabase-minio mc alias set local http://localhost:9000 "$MINIO_USER" "$MINIO_PASS" >/dev/null 2>&1; then
    docker exec supabase-minio mc mb local/storage --ignore-existing >/dev/null 2>&1
    success "MinIO storage bucket ready"
else
    warn "Could not configure MinIO - storage may not work correctly"
fi

# ---- Step 9: Build and start NoobBook ----
info "Building and starting NoobBook (this may take a few minutes on first run)..."
$COMPOSE -f "$ROOT_DIR/docker-compose.yml" --env-file "$NOOBBOOK_ENV" up -d --build

# ---- Step 10: Wait for migration ----
info "Waiting for database migration to complete..."
TIMEOUT=90
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    # The migrate container is a one-shot: it runs and exits
    STATUS=$(docker inspect -f '{{.State.Status}}' noobbook-migrate 2>/dev/null || echo "unknown")
    if [ "$STATUS" = "exited" ]; then
        EXIT_CODE=$(docker inspect -f '{{.State.ExitCode}}' noobbook-migrate 2>/dev/null || echo "1")
        if [ "$EXIT_CODE" = "0" ]; then
            success "Database migration complete"
        else
            warn "Migration exited with code $EXIT_CODE — check: docker logs noobbook-migrate"
        fi
        break
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    printf "."
done
echo ""

if [ $ELAPSED -ge $TIMEOUT ]; then
    warn "Migration still running after ${TIMEOUT}s — check: docker logs noobbook-migrate"
fi

# ---- Step 11: Print summary ----
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  NoobBook is running!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "  App:              ${CYAN}http://localhost${NC}"
echo -e "  Supabase Studio:  ${CYAN}http://localhost:8000${NC}"
echo -e "  MinIO Console:    ${CYAN}http://localhost:9001${NC}"
echo ""
echo -e "  Stop:   ${YELLOW}bash docker/stop.sh${NC}"
echo -e "  Reset:  ${YELLOW}bash docker/reset.sh${NC}"
echo ""
if grep -q '^ANTHROPIC_API_KEY=$' "$NOOBBOOK_ENV" 2>/dev/null; then
    echo -e "${YELLOW}  Remember to add your API keys to docker/.env${NC}"
    echo ""
fi
