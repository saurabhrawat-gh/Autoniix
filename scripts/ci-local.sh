#!/usr/bin/env bash
# =============================================================================
# ci-local.sh — Full local CI simulation.
#
# Runs EVERY check from every workflow that was ever in this repo:
#   - DB: pgvector postgres, init-db.sql, all migrations
#   - Rust: fmt, clippy, unit tests, schema tests, harness tests, release build
#   - Python: ruff lint, mypy type-check, pytest (non-integration)
#   - Node/Next.js: tsc type-check, eslint
#   - Go: go build, go vet
#   - Proto: buf lint (if buf installed)
#
# Usage:
#   bash scripts/ci-local.sh              # run everything
#   bash scripts/ci-local.sh --rust       # rust only
#   bash scripts/ci-local.sh --python     # python only
#   bash scripts/ci-local.sh --node       # node only
#   bash scripts/ci-local.sh --go         # go only
#   bash scripts/ci-local.sh --db         # db migrations only
#   bash scripts/ci-local.sh --proto      # proto lint only
#
# Requirements (install missing ones before running):
#   - docker          (postgres container)
#   - cargo           (rust)
#   - psql            (brew install libpq && brew link libpq --force)
#   - python3 / pip   (python checks)
#   - node / pnpm     (node checks)
#   - go              (go checks)
#   - buf             (proto checks — optional, skipped if missing)
# =============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PG_CONTAINER="ci-local-pg"
PG_PORT="15432"
DB_URL="postgresql://postgres:postgres@localhost:${PG_PORT}/autoniix_test"

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
pass()  { echo -e "\n${GREEN}✅  $1${NC}\n"; }
fail()  { echo -e "\n${RED}❌  FAILED: $1${NC}\n"; exit 1; }
skip()  { echo -e "\n${YELLOW}⏭️   SKIPPED: $1${NC}\n"; }
step()  { echo -e "\n──────────────────────────────────────────\n▶  $1\n──────────────────────────────────────────"; }
header(){ echo -e "\n${YELLOW}╔══════════════════════════════════════════╗\n║  $1\n╚══════════════════════════════════════════╝${NC}"; }

# ── Argument parsing ──────────────────────────────────────────────────────────
RUN_ALL=true
RUN_DB=false; RUN_RUST=false; RUN_PYTHON=false; RUN_NODE=false; RUN_GO=false; RUN_PROTO=false

for arg in "$@"; do
    case "$arg" in
        --db)     RUN_ALL=false; RUN_DB=true ;;
        --rust)   RUN_ALL=false; RUN_RUST=true ;;
        --python) RUN_ALL=false; RUN_PYTHON=true ;;
        --node)   RUN_ALL=false; RUN_NODE=true ;;
        --go)     RUN_ALL=false; RUN_GO=true ;;
        --proto)  RUN_ALL=false; RUN_PROTO=true ;;
    esac
done

if $RUN_ALL; then
    RUN_DB=true; RUN_RUST=true; RUN_PYTHON=true; RUN_NODE=true; RUN_GO=true; RUN_PROTO=true
fi

FAILED_STEPS=()
soft_fail() { FAILED_STEPS+=("$1"); echo -e "\n${RED}❌  $1${NC}\n"; }

# ── Postgres lifecycle ────────────────────────────────────────────────────────
pg_start() {
    step "Starting pgvector/pgvector:pg16 (exact CI image)"
    docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
    docker run -d \
        --name "$PG_CONTAINER" \
        -e POSTGRES_USER=postgres \
        -e POSTGRES_PASSWORD=postgres \
        -e POSTGRES_DB=autoniix_test \
        -p "${PG_PORT}:5432" \
        pgvector/pgvector:pg16 >/dev/null

    echo "Waiting for postgres..."
    for i in $(seq 1 60); do
        docker exec "$PG_CONTAINER" pg_isready -U postgres >/dev/null 2>&1 && break
        sleep 1
    done
    docker exec "$PG_CONTAINER" pg_isready -U postgres >/dev/null 2>&1 \
        || fail "Postgres did not become ready in 60s"
    pass "Postgres ready on port $PG_PORT"
}

pg_stop() {
    docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
}

# ── Cleanup on exit ───────────────────────────────────────────────────────────
trap pg_stop EXIT

# =============================================================================
# BLOCK 1 — DATABASE MIGRATIONS
# =============================================================================
if $RUN_DB; then
    header "DATABASE — init-db.sql + migrations"
    pg_start

    step "Applying base schema: scripts/init-db.sql"
    docker exec -i "$PG_CONTAINER" psql -U postgres -d autoniix_test \
        -v ON_ERROR_STOP=1 < "$ROOT/scripts/init-db.sql" \
        || fail "init-db.sql failed"
    pass "Base schema applied"

    step "Applying incremental migrations: scripts/migrations/*.sql"
    HAD_MIGRATION_ERROR=false
    for f in $(ls "$ROOT/scripts/migrations/"*.sql | sort); do
        echo "  → $(basename "$f")"
        docker exec -i "$PG_CONTAINER" psql -U postgres -d autoniix_test \
            -v ON_ERROR_STOP=1 < "$f" \
            || { soft_fail "Migration failed: $(basename "$f")"; HAD_MIGRATION_ERROR=true; break; }
    done
    $HAD_MIGRATION_ERROR || pass "All migrations applied cleanly"
fi

# =============================================================================
# BLOCK 2 — RUST
# =============================================================================
if $RUN_RUST; then
    header "RUST — fmt + clippy + tests + release build"

    # Start DB if not already running (needed for tests)
    if ! docker ps --format '{{.Names}}' | grep -q "^${PG_CONTAINER}$"; then
        pg_start
        step "Applying schemas for Rust tests"
        docker exec -i "$PG_CONTAINER" psql -U postgres -d autoniix_test \
            -v ON_ERROR_STOP=1 < "$ROOT/scripts/init-db.sql" >/dev/null
        for f in $(ls "$ROOT/scripts/migrations/"*.sql | sort); do
            docker exec -i "$PG_CONTAINER" psql -U postgres -d autoniix_test \
                -v ON_ERROR_STOP=1 < "$f" >/dev/null
        done
    fi

    step "cargo fmt --check"
    (cd "$ROOT/rust" && cargo fmt --all -- --check) \
        || fail "cargo fmt failed — fix with: cd rust && cargo fmt --all"
    pass "cargo fmt clean"

    step "cargo clippy -- -D warnings"
    (cd "$ROOT/rust" && cargo clippy --all-targets --all-features -- -D warnings) \
        || fail "cargo clippy failed"
    pass "cargo clippy clean"

    step "cargo test -p gateway --lib  (unit tests)"
    (cd "$ROOT/rust" && \
        TEST_DATABASE_URL="$DB_URL" \
        AUTH_JWT_SECRET="test-jwt-secret-for-ci" \
        cargo test -p gateway --lib 2>&1) \
        || fail "Rust unit tests failed"
    pass "Rust unit tests passed"

    step "cargo test -p gateway --test schema_compatibility_test"
    (cd "$ROOT/rust" && \
        TEST_DATABASE_URL="$DB_URL" \
        AUTH_JWT_SECRET="test-jwt-secret-for-ci" \
        cargo test -p gateway --test schema_compatibility_test 2>&1) \
        || fail "Schema compatibility tests failed"
    pass "Schema compatibility tests passed"

    step "cargo test -p harness  (harness tests)"
    (cd "$ROOT/rust" && cargo test -p harness 2>&1) \
        || fail "Harness tests failed"
    pass "Harness tests passed"

    step "cargo build --release"
    (cd "$ROOT/rust" && cargo build --release 2>&1) \
        || fail "Rust release build failed"
    pass "Rust release build succeeded"
fi

# =============================================================================
# BLOCK 3 — PYTHON
# =============================================================================
if $RUN_PYTHON; then
    header "PYTHON — ruff lint + mypy + pytest"

    if ! command -v python3 &>/dev/null; then
        skip "python3 not found — install Python 3.11+"
    else
        # Use virtualenv if present, else system python
        PY="python3"
        PIP="pip3"
        if [ -f "$ROOT/.venv/bin/python" ]; then
            PY="$ROOT/.venv/bin/python"
            PIP="$ROOT/.venv/bin/pip"
        fi

        step "Checking Python dependencies (ruff, mypy, pytest)"
        $PIP install --quiet ruff mypy pytest pytest-asyncio 2>&1 | tail -3

        step "ruff check src/ tests/ scripts/ (Python lint)"
        (cd "$ROOT" && $PY -m ruff check src/ tests/ scripts/ --ignore E501,E402) \
            || soft_fail "Python ruff lint"

        step "mypy src/ (type check)"
        (cd "$ROOT" && $PY -m mypy src/ --ignore-missing-imports --no-error-summary 2>&1 | tail -20) \
            || soft_fail "Python mypy type check"

        step "pytest tests/ -m 'not integration' (unit tests only, no DB needed)"
        (cd "$ROOT" && $PY -m pytest tests/ -m "not integration" -q --tb=short 2>&1) \
            || soft_fail "Python pytest"

        pass "Python checks complete"
    fi
fi

# =============================================================================
# BLOCK 4 — NODE / NEXT.JS DASHBOARD
# =============================================================================
if $RUN_NODE; then
    header "NODE — TypeScript type-check + ESLint"

    if ! command -v node &>/dev/null; then
        skip "node not found — install Node >= 20"
    else
        step "pnpm install (dashboard deps)"
        if command -v pnpm &>/dev/null; then
            (cd "$ROOT/dashboard" && pnpm install --frozen-lockfile 2>&1 | tail -5) \
                || soft_fail "pnpm install"
        elif command -v npm &>/dev/null; then
            (cd "$ROOT/dashboard" && npm ci 2>&1 | tail -5) \
                || soft_fail "npm ci"
        fi

        step "tsc --noEmit  (TypeScript type check)"
        (cd "$ROOT/dashboard" && npx tsc --noEmit 2>&1) \
            || soft_fail "Dashboard TypeScript errors"
        pass "Dashboard TypeScript clean"

        step "next lint  (ESLint)"
        (cd "$ROOT/dashboard" && npx next lint 2>&1) \
            || soft_fail "Dashboard ESLint"
        pass "Dashboard ESLint clean"
    fi
fi

# =============================================================================
# BLOCK 5 — GO
# =============================================================================
if $RUN_GO; then
    header "GO — go build + go vet"

    if ! command -v go &>/dev/null; then
        skip "go not found — install Go >= 1.22"
    else
        step "go build ./..."
        (cd "$ROOT/go" && go build ./... 2>&1) \
            || soft_fail "Go build failed"
        pass "Go build clean"

        step "go vet ./..."
        (cd "$ROOT/go" && go vet ./... 2>&1) \
            || soft_fail "Go vet failed"
        pass "Go vet clean"
    fi
fi

# =============================================================================
# BLOCK 6 — PROTO
# =============================================================================
if $RUN_PROTO; then
    header "PROTO — buf lint"

    if ! command -v buf &>/dev/null; then
        skip "buf not found — install: brew install bufbuild/buf/buf"
    else
        step "buf lint"
        (cd "$ROOT/proto" && buf lint 2>&1) \
            || soft_fail "Proto buf lint failed"
        pass "Proto lint clean"

        step "buf breaking --against '.git#branch=main'"
        (cd "$ROOT/proto" && buf breaking --against '.git#branch=main' 2>&1) \
            || soft_fail "Proto breaking change detected vs main"
        pass "No proto breaking changes"
    fi
fi

# =============================================================================
# FINAL REPORT
# =============================================================================
echo ""
echo "══════════════════════════════════════════════════════"
if [ ${#FAILED_STEPS[@]} -eq 0 ]; then
    echo -e "${GREEN}✅  ALL CI CHECKS PASSED — safe to merge to main${NC}"
else
    echo -e "${RED}❌  THE FOLLOWING CHECKS FAILED:${NC}"
    for s in "${FAILED_STEPS[@]}"; do
        echo -e "    ${RED}•  $s${NC}"
    done
    echo ""
    echo "Fix these before merging to main."
    exit 1
fi
echo "══════════════════════════════════════════════════════"
