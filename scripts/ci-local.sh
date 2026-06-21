#!/usr/bin/env bash
# =============================================================================
# ci-local.sh — EXACT mirror of .github/workflows/build.yml
#
# Runs every step the CI build runs, in the same order, with the same commands,
# against the same Docker image. If this passes locally, the remote build passes.
#
# WHAT THIS DOES (mirrors build.yml lines 45-101 exactly):
#   1. Start pgvector/pgvector:pg16 postgres container
#   2. cargo fmt --all -- --check
#   3. cargo clippy --all-targets --all-features -- -D warnings
#   4. psql -f scripts/init-db.sql
#   5. psql -f scripts/migrations/*.sql (all, sorted)
#   6. cargo test -p gateway --lib                    (with TEST_DATABASE_URL + AUTH_JWT_SECRET)
#   7. cargo test -p gateway --test schema_compatibility_test  (same env)
#   8. cargo test -p harness
#   9. cargo build --release
#  10. docker build -f rust/gateway/Dockerfile .
#
# WHAT THIS DOES NOT TEST:
#   - The deploy job (self-hosted VPS) — only your VPS can verify that
#
# Usage:  bash scripts/ci-local.sh
# =============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PG_CONTAINER="ci-local-pg"
PG_PORT="15432"
DB_URL="postgresql://postgres:postgres@localhost:${PG_PORT}/autoniix_test"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
pass()  { echo -e "${GREEN}✅  $1${NC}"; }
fail()  { echo -e "\n${RED}❌  FAILED: $1${NC}\n"; exit 1; }
step()  { echo -e "\n${YELLOW}▶  $1${NC}"; }

# Prerequisite checks — fail fast if anything missing
command -v docker >/dev/null || fail "docker not installed"
command -v cargo  >/dev/null || fail "cargo not installed"
docker info >/dev/null 2>&1 || fail "docker daemon not running"

cleanup() { docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# ─── 1. Start postgres (same image as CI) ────────────────────────────────────
step "[1/10] Start pgvector/pgvector:pg16"
cleanup
docker run -d --name "$PG_CONTAINER" \
    -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=autoniix_test \
    -p "${PG_PORT}:5432" pgvector/pgvector:pg16 >/dev/null
for i in $(seq 1 60); do
    docker exec "$PG_CONTAINER" pg_isready -U postgres >/dev/null 2>&1 && break
    sleep 1
done
docker exec "$PG_CONTAINER" pg_isready -U postgres >/dev/null 2>&1 \
    || fail "Postgres did not become ready in 60s"
pass "Postgres ready"

# ─── 2. cargo fmt ────────────────────────────────────────────────────────────
step "[2/10] cargo fmt --all -- --check"
(cd "$ROOT/rust" && cargo fmt --all -- --check) || fail "cargo fmt"
pass "cargo fmt clean"

# ─── 3. cargo clippy ─────────────────────────────────────────────────────────
step "[3/10] cargo clippy --all-targets --all-features -- -D warnings"
(cd "$ROOT/rust" && cargo clippy --all-targets --all-features -- -D warnings) || fail "cargo clippy"
pass "cargo clippy clean"

# ─── 4. Apply init-db.sql ────────────────────────────────────────────────────
step "[4/10] Apply scripts/init-db.sql"
docker exec -i "$PG_CONTAINER" psql -U postgres -d autoniix_test -v ON_ERROR_STOP=1 \
    < "$ROOT/scripts/init-db.sql" >/dev/null \
    || fail "init-db.sql"
pass "Base schema applied"

# ─── 5. Apply incremental migrations ─────────────────────────────────────────
step "[5/10] Apply scripts/migrations/*.sql"
for f in $(ls "$ROOT/scripts/migrations/"*.sql | sort); do
    docker exec -i "$PG_CONTAINER" psql -U postgres -d autoniix_test -v ON_ERROR_STOP=1 \
        < "$f" >/dev/null \
        || fail "Migration: $(basename "$f")"
done
pass "All migrations applied"

# ─── 6. Unit tests ───────────────────────────────────────────────────────────
step "[6/10] cargo test -p gateway --lib"
(cd "$ROOT/rust" && \
    TEST_DATABASE_URL="$DB_URL" \
    AUTH_JWT_SECRET="test-jwt-secret-for-ci" \
    cargo test -p gateway --lib) || fail "gateway unit tests"
pass "gateway unit tests pass"

# ─── 7. Schema compatibility tests ───────────────────────────────────────────
step "[7/10] cargo test -p gateway --test schema_compatibility_test"
(cd "$ROOT/rust" && \
    TEST_DATABASE_URL="$DB_URL" \
    AUTH_JWT_SECRET="test-jwt-secret-for-ci" \
    cargo test -p gateway --test schema_compatibility_test) || fail "schema compat tests"
pass "schema compat tests pass"

# ─── 8. Harness tests ────────────────────────────────────────────────────────
step "[8/10] cargo test -p harness"
(cd "$ROOT/rust" && cargo test -p harness) || fail "harness tests"
pass "harness tests pass"

# ─── 9. Release build ────────────────────────────────────────────────────────
step "[9/10] cargo build --release"
(cd "$ROOT/rust" && cargo build --release) || fail "cargo build --release"
pass "release binary built"

# ─── 10. Docker build (matches docker/build-push-action) ─────────────────────
step "[10/10] docker build -f rust/gateway/Dockerfile ."
(cd "$ROOT" && docker build -f rust/gateway/Dockerfile -t autoniix/gateway:ci-local . >/dev/null 2>&1) \
    || fail "docker build (run manually for full log: docker build -f rust/gateway/Dockerfile .)"
pass "docker image built"

# ─── Done ────────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
echo -e "${GREEN}✅  ALL CI CHECKS PASSED — safe to push to main${NC}"
echo "══════════════════════════════════════════════════════"
echo ""
echo "Note: The 'deploy' job runs on your self-hosted VPS and cannot be"
echo "tested locally. Verify the VPS runner is online before pushing."
