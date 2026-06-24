#!/usr/bin/env bash
# =============================================================================
# ci-local.sh — Local pre-push verification.
#
# DEFAULT MODE (no args): EXACT mirror of .github/workflows/build.yml
#   → answers "will the GitHub CI build pass?"
#   → checks Rust + Docker only (because that is all CI runs today)
#
# OPT-IN FLAGS: broader code-quality checks for languages not in CI
#   --python   ruff + mypy + pytest (non-integration)
#   --node     tsc --noEmit + next lint  (dashboard/)
#   --go       go build + go vet  (go/)
#   --proto    buf lint + buf breaking  (proto/)
#   --full     all of the above + the CI mirror
#
# Examples:
#   bash scripts/ci-local.sh            # before every push  — CI mirror only
#   bash scripts/ci-local.sh --full     # before a big release — every language
#   bash scripts/ci-local.sh --python   # only ran Python changes? quick check
#
# WHAT IS NEVER TESTED LOCALLY:
#   - The 'deploy' job runs on your self-hosted VPS — only the VPS can verify that
# =============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PG_CONTAINER="ci-local-pg"
PG_PORT="15432"
DB_URL="postgresql://postgres:postgres@localhost:${PG_PORT}/autoniix_test"

# ─── Flag parsing ────────────────────────────────────────────────────────────
RUN_CI=true       # the strict CI mirror — always on by default
RUN_PYTHON=false
RUN_NODE=false
RUN_GO=false
RUN_PROTO=false

for arg in "$@"; do
    case "$arg" in
        --python) RUN_PYTHON=true ;;
        --node)   RUN_NODE=true ;;
        --go)     RUN_GO=true ;;
        --proto)  RUN_PROTO=true ;;
        --full)   RUN_PYTHON=true; RUN_NODE=true; RUN_GO=true; RUN_PROTO=true ;;
        --ci-only) ;;  # default already
        -h|--help)
            sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Unknown flag: $arg (use --help)"; exit 2 ;;
    esac
done

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
pass()  { echo -e "${GREEN}✅  $1${NC}"; }
fail()  { echo -e "\n${RED}❌  FAILED: $1${NC}\n"; exit 1; }
warn()  { echo -e "${YELLOW}⏭️   SKIPPED: $1${NC}"; }
step()  { echo -e "\n${YELLOW}▶  $1${NC}"; }

# Prerequisite checks — fail fast if anything missing
command -v docker >/dev/null || fail "docker not installed"
command -v cargo  >/dev/null || fail "cargo not installed"
docker info >/dev/null 2>&1 || fail "docker daemon not running"

cleanup() { docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# Track any failures across optional blocks (CI block always fails fast)
SOFT_FAILURES=()
soft_fail() { SOFT_FAILURES+=("$1"); echo -e "${RED}❌  $1${NC}"; }

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
step "[8/12] cargo test -p harness"
(cd "$ROOT/rust" && cargo test -p harness) || fail "harness tests"
pass "harness tests pass"

# ─── 9. Middleware + auth integration tests (IM-171 IM-172) ──────────────────
step "[9/12] cargo test -p gateway --test middleware_test"
(cd "$ROOT/rust" && \
    TEST_DATABASE_URL="$DB_URL" \
    AUTH_JWT_SECRET="test-jwt-secret-for-ci" \
    cargo test -p gateway --test middleware_test) || fail "middleware integration tests"
pass "middleware integration tests pass"

step "[10/12] cargo test -p gateway --test auth_test"
(cd "$ROOT/rust" && \
    TEST_DATABASE_URL="$DB_URL" \
    AUTH_JWT_SECRET="test-jwt-secret-for-ci" \
    cargo test -p gateway --test auth_test) || fail "auth integration tests"
pass "auth integration tests pass"

# ─── 11. Release build ───────────────────────────────────────────────────────
step "[11/12] cargo build --release"
(cd "$ROOT/rust" && cargo build --release) || fail "cargo build --release"
pass "release binary built"

# ─── 12. Docker build (matches docker/build-push-action) ─────────────────────
step "[12/12] docker build -f rust/gateway/Dockerfile ."
(cd "$ROOT" && docker build -f rust/gateway/Dockerfile -t autoniix/gateway:ci-local . >/dev/null 2>&1) \
    || fail "docker build (run manually for full log: docker build -f rust/gateway/Dockerfile .)"
pass "docker image built"

# =============================================================================
# OPTIONAL — extra code-quality checks not (yet) wired into CI
# =============================================================================

# ─── Python ──────────────────────────────────────────────────────────────────
if $RUN_PYTHON; then
    step "[python] ruff + mypy + pytest"
    if ! command -v python3 >/dev/null; then
        warn "python3 not installed — skip"
    else
        PY="python3"; PIP="pip3"
        [ -f "$ROOT/.venv/bin/python" ] && { PY="$ROOT/.venv/bin/python"; PIP="$ROOT/.venv/bin/pip"; }

        echo "  → installing tools (ruff, mypy, pytest)..."
        $PIP install --quiet ruff mypy pytest pytest-asyncio 2>&1 | tail -2

        echo "  → ruff check src/ tests/ scripts/"
        (cd "$ROOT" && $PY -m ruff check src/ tests/ scripts/ 2>&1) \
            || soft_fail "python ruff"

        echo "  → mypy src/"
        (cd "$ROOT" && $PY -m mypy src/ --ignore-missing-imports 2>&1 | tail -10) \
            || soft_fail "python mypy"

        echo "  → pytest -m 'not integration'"
        (cd "$ROOT" && $PY -m pytest tests/ -m "not integration" -q --tb=short 2>&1 | tail -10) \
            || soft_fail "python pytest"

        pass "python checks done"
    fi
fi

# ─── Node / Next.js dashboard ────────────────────────────────────────────────
if $RUN_NODE; then
    step "[node] tsc --noEmit + next lint (dashboard/)"
    if ! command -v node >/dev/null; then
        warn "node not installed — skip"
    else
        # Install deps if missing
        if [ ! -d "$ROOT/dashboard/node_modules" ]; then
            echo "  → installing dashboard deps..."
            if command -v pnpm >/dev/null; then
                (cd "$ROOT/dashboard" && pnpm install --frozen-lockfile 2>&1 | tail -3) \
                    || soft_fail "pnpm install"
            else
                (cd "$ROOT/dashboard" && npm install 2>&1 | tail -3) \
                    || soft_fail "npm install"
            fi
        fi

        echo "  → tsc --noEmit"
        (cd "$ROOT/dashboard" && npx tsc --noEmit 2>&1) || soft_fail "dashboard tsc"

        echo "  → next lint"
        (cd "$ROOT/dashboard" && npx next lint 2>&1 | tail -10) || soft_fail "dashboard eslint"

        pass "node checks done"
    fi
fi

# ─── Go ──────────────────────────────────────────────────────────────────────
if $RUN_GO; then
    step "[go] go build + go vet (go/)"
    if ! command -v go >/dev/null; then
        warn "go not installed — skip"
    else
        echo "  → go build ./..."
        (cd "$ROOT/go" && go build ./... 2>&1) || soft_fail "go build"
        echo "  → go vet ./..."
        (cd "$ROOT/go" && go vet ./... 2>&1) || soft_fail "go vet"
        pass "go checks done"
    fi
fi

# ─── Proto ───────────────────────────────────────────────────────────────────
if $RUN_PROTO; then
    step "[proto] buf lint + buf breaking (proto/)"
    if ! command -v buf >/dev/null; then
        warn "buf not installed — install: brew install bufbuild/buf/buf"
    else
        echo "  → buf lint"
        (cd "$ROOT/proto" && buf lint 2>&1) || soft_fail "buf lint"
        echo "  → buf breaking --against .git#branch=main"
        (cd "$ROOT/proto" && buf breaking --against '.git#branch=main' 2>&1) \
            || soft_fail "buf breaking"
        pass "proto checks done"
    fi
fi

# ─── Final report ────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
if [ ${#SOFT_FAILURES[@]} -eq 0 ]; then
    echo -e "${GREEN}✅  ALL CHECKS PASSED — safe to push to main${NC}"
    echo "══════════════════════════════════════════════════════"
    echo ""
    echo "Note: The 'deploy' job runs on your self-hosted VPS and cannot be"
    echo "tested locally. Verify the VPS runner is online before pushing."
else
    echo -e "${GREEN}✅  CI MIRROR PASSED${NC} — GitHub build will pass."
    echo ""
    echo -e "${YELLOW}⚠  But ${#SOFT_FAILURES[@]} optional check(s) reported issues:${NC}"
    for s in "${SOFT_FAILURES[@]}"; do
        echo -e "    ${RED}•  $s${NC}"
    done
    echo ""
    echo "These languages are not currently in CI, so the push is safe."
    echo "But you should fix them before they bite you."
    exit 1
fi
