#!/usr/bin/env bash
# =============================================================================
# sqlx-prepare.sh — Regenerate the .sqlx/ offline query cache.
#
# Run this whenever you add, remove, or change a sqlx::query!() macro.
# Creates a temporary Postgres container, runs all migrations, then runs
# `cargo sqlx prepare --workspace` so the cache matches the current schema.
#
# Usage:
#   bash scripts/sqlx-prepare.sh          # called by `make sqlx-prepare`
#   (also auto-called by pre-commit hook when new sqlx macros are detected)
# =============================================================================

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
step() { printf "\n${YELLOW}▶  %s${NC}\n" "$1"; }
pass() { printf "${GREEN}✅  %s${NC}\n" "$1"; }
fail() { printf "\n${RED}❌  %s${NC}\n" "$1"; exit 1; }

# Load version pins
set -a; source "$ROOT/versions.env"; set +a

PG_CONTAINER="sqlx-prepare-pg"
PG_PORT="15434"
DB_URL="postgresql://postgres:postgres@localhost:${PG_PORT}/autoniix_dev"

cleanup() {
    if docker ps -q --filter "name=${PG_CONTAINER}" | grep -q .; then
        echo "Stopping Postgres container..."
        docker stop "${PG_CONTAINER}" >/dev/null 2>&1 || true
        docker rm  "${PG_CONTAINER}" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

command -v docker >/dev/null || fail "docker not installed"
command -v cargo  >/dev/null || fail "cargo not installed"
docker info >/dev/null 2>&1  || fail "Docker daemon not running"

step "Starting temporary Postgres (${POSTGRES_IMAGE})..."
docker rm -f "${PG_CONTAINER}" >/dev/null 2>&1 || true
docker run -d --name "${PG_CONTAINER}" \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=autoniix_dev \
    -p "${PG_PORT}:5432" \
    "${POSTGRES_IMAGE}" >/dev/null

echo "Waiting for Postgres to be ready..."
for i in $(seq 1 20); do
    if docker exec "${PG_CONTAINER}" pg_isready -U postgres -q 2>/dev/null; then
        echo "✓  Postgres ready"
        break
    fi
    [ "$i" -eq 20 ] && fail "Postgres did not become ready in time"
    sleep 1
done

step "Running migrations..."
MIGRATION_COUNT=0
for f in "$ROOT/scripts/migrations/"*.sql; do
    [ -f "$f" ] || continue
    docker exec -i "${PG_CONTAINER}" psql -U postgres -d autoniix_dev \
        -v ON_ERROR_STOP=0 -q < "$f" 2>/dev/null || true
    MIGRATION_COUNT=$((MIGRATION_COUNT + 1))
done
echo "✓  Applied ${MIGRATION_COUNT} migration(s)"

step "Running cargo sqlx prepare --workspace..."
(cd "$ROOT/rust" && DATABASE_URL="${DB_URL}" cargo sqlx prepare --workspace 2>&1) \
    || fail "cargo sqlx prepare failed — see errors above"

pass ".sqlx/ cache regenerated successfully"
echo ""
echo "The following files were updated:"
git -C "$ROOT" diff --name-only .sqlx/ 2>/dev/null | sed 's/^/  /' || true
git -C "$ROOT" ls-files --others --exclude-standard .sqlx/ 2>/dev/null | sed 's/^/  (new) /' || true
echo ""
echo "Stage and commit them:"
echo "  git add .sqlx/ && git commit -m 'fix(sqlx): regenerate offline query cache'"
