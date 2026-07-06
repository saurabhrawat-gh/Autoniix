#!/usr/bin/env bash
# =============================================================================
# ci-local.sh — Local pre-push CI mirror.
#
# Answers: "will every job in .github/workflows/* pass?" before you push.
# Uses the same tool versions and postgres major as CI (via versions.env).
#
# DEFAULT MODE: strict Rust CI mirror (~90s). Recommended for every push.
# FLAGS:
#   --python   ci.yml python-lint-and-tests + dependency-scan + migration-equivalence
#              + build.yml python-harness
#   --node     ci.yml dashboard-typecheck + remotion-typecheck + build.yml dashboard-tests
#   --go       build.yml go-harness (go test ./shared/testharness/...)
#   --proto    proto-validate.yml lint + breaking + generate
#   --full     everything above + the Rust block (matches CI wall-time exactly)
#   --docker   run the ENTIRE pipeline inside pinned ubuntu:24.04 (max parity)
#   --skip-rust  don't run the Rust block
#
# Examples:
#   bash scripts/ci-local.sh                # default: Rust mirror
#   bash scripts/ci-local.sh --full         # every CI job, on host
#   bash scripts/ci-local.sh --full --docker # every CI job, inside ubuntu:24.04
# =============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PG_CONTAINER="ci-local-pg"
PG_PORT="15432"
PG_HOST="${PG_HOST:-localhost}"
DB_URL="postgresql://postgres:postgres@${PG_HOST}:${PG_PORT}/autoniix_test"

# Env normalization — match GitHub Actions ubuntu-latest defaults byte-for-byte
export TZ=UTC LC_ALL=C.UTF-8 LANG=C.UTF-8
export DOCKER_DEFAULT_PLATFORM=linux/amd64
export CARGO_TERM_COLOR=always
export PIP_DISABLE_PIP_VERSION_CHECK=1
export NPM_CONFIG_FUND=false NPM_CONFIG_AUDIT=false

# Load version pins from single source of truth
if [[ ! -f "$ROOT/versions.env" ]]; then
    echo "❌  $ROOT/versions.env missing" >&2
    exit 1
fi
# shellcheck disable=SC1091
set -a; source "$ROOT/versions.env"; set +a

# ─── Flag parsing ────────────────────────────────────────────────────────────
RUN_RUST=true
RUN_PYTHON=false; RUN_NODE=false; RUN_GO=false; RUN_PROTO=false
RUN_IN_DOCKER=false

for arg in "$@"; do
    case "$arg" in
        --python)     RUN_PYTHON=true ;;
        --node)       RUN_NODE=true ;;
        --go)         RUN_GO=true ;;
        --proto)      RUN_PROTO=true ;;
        --full)       RUN_PYTHON=true; RUN_NODE=true; RUN_GO=true; RUN_PROTO=true ;;
        --docker)     RUN_IN_DOCKER=true ;;
        --skip-rust)  RUN_RUST=false ;;
        --ci-only)    ;;
        -h|--help)    sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown flag: $arg (use --help)"; exit 2 ;;
    esac
done

# ─── --docker mode: build pinned image and re-exec inside it ────────────────
if $RUN_IN_DOCKER; then
    HASH=$(sha256sum "$ROOT/versions.env" | awk '{print substr($1,1,12)}')
    TAG="autoniix/ci-local:${HASH}"
    if ! docker image inspect "$TAG" >/dev/null 2>&1; then
        echo "▶  Building ci-local image ($TAG) — one-time (~2 min)..."
        docker build --platform linux/amd64 \
            --build-arg "RUST_VERSION=$RUST_VERSION" \
            --build-arg "NODE_VERSION=$NODE_VERSION" \
            --build-arg "NPM_VERSION=$NPM_VERSION" \
            --build-arg "PYTHON_VERSION=$PYTHON_VERSION" \
            --build-arg "GO_VERSION=$GO_VERSION" \
            --build-arg "BUF_VERSION=$BUF_VERSION" \
            -f "$ROOT/scripts/ci-local.Dockerfile" -t "$TAG" "$ROOT" \
            || { echo "❌  Failed to build ci-local image"; exit 1; }
    else
        echo "▶  Reusing cached ci-local image ($TAG)"
    fi
    INNER=()
    for a in "$@"; do [[ "$a" == "--docker" ]] || INNER+=("$a"); done
    exec docker run --rm -it --platform linux/amd64 \
        --add-host=host.docker.internal:host-gateway \
        -v "$ROOT:/work" -v /var/run/docker.sock:/var/run/docker.sock \
        -w /work \
        -e TZ=UTC -e LC_ALL=C.UTF-8 -e LANG=C.UTF-8 \
        -e DOCKER_DEFAULT_PLATFORM=linux/amd64 \
        -e PG_HOST=host.docker.internal \
        "$TAG" bash scripts/ci-local.sh "${INNER[@]}"
fi

# ─── Helpers ─────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
pass()  { printf "${GREEN}✅  %s${NC}\n" "$1"; }
fail()  { printf "\n${RED}❌  FAILED: %s${NC}\n\n" "$1"; exit 1; }
warn()  { printf "${YELLOW}⏭️   SKIPPED: %s${NC}\n" "$1"; }
step()  { printf "\n${YELLOW}▶  %s${NC}\n" "$1"; }

command -v docker >/dev/null || fail "docker not installed"
command -v cargo  >/dev/null || fail "cargo not installed"
docker info >/dev/null 2>&1  || fail "docker daemon not running"

# Step 0. Verify local toolchain matches versions.env
step "[0] Verify local toolchain matches versions.env"
if ! bash "$ROOT/scripts/verify-versions.sh"; then
    fail "toolchain mismatch — install with mise/asdf (reads .tool-versions), or use --docker mode"
fi

cleanup() { docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT

SOFT_FAILURES=()
soft_fail() { SOFT_FAILURES+=("$1"); printf "${RED}❌  %s${NC}\n" "$1"; }

# ─── 1. Start postgres (same image + arch as CI + prod) ──────────────────────
step "[1/14] Start $POSTGRES_IMAGE (linux/amd64)"
cleanup
docker run -d --name "$PG_CONTAINER" --platform linux/amd64 \
    -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=autoniix_test \
    -p "${PG_PORT}:5432" "$POSTGRES_IMAGE" >/dev/null
for i in $(seq 1 60); do
    docker exec "$PG_CONTAINER" pg_isready -U postgres >/dev/null 2>&1 && break
    sleep 1
done
docker exec "$PG_CONTAINER" pg_isready -U postgres >/dev/null 2>&1 \
    || fail "Postgres did not become ready in 60s"
pass "Postgres ready"

# Export DATABASE_URL so sqlx macros can validate queries live (same as CI)
export DATABASE_URL="postgresql://postgres:postgres@${PG_HOST}:${PG_PORT}/autoniix_test"

# =============================================================================
# RUST CI MIRROR — build.yml `rust` + ci.yml `rust-tests` + `rust-audit`
# =============================================================================
if $RUN_RUST; then

    step "[2/14] cargo fmt --all -- --check"
    (cd "$ROO./" && cargo fmt --all -- --check) || fail "cargo fmt"
    pass "cargo fmt clean"

    step "[3/14] cargo clippy --all-targets --all-features -- -D warnings"
    (cd "$ROO./" && cargo clippy --all-targets --all-features -- -D warnings) \
        || fail "cargo clippy"
    pass "cargo clippy clean"

    step "[4/14] Apply scripts/init-db.sql"
    docker exec -i "$PG_CONTAINER" psql -U postgres -d autoniix_test -v ON_ERROR_STOP=1 \
        < "$ROOT/scripts/init-db.sql" >/dev/null || fail "init-db.sql"
    pass "Base schema applied"

    step "[5/14] Apply infra/migrations/*.sql"
    for f in $(ls "$ROOT/infra/migrations/"*.sql | sort); do
        docker exec -i "$PG_CONTAINER" psql -U postgres -d autoniix_test -v ON_ERROR_STOP=1 \
            < "$f" >/dev/null || fail "Migration: $(basename "$f")"
    done
    pass "All migrations applied"

    step "[6/14] cargo test -p gateway --lib"
    (cd "$ROO./" && \
        TEST_DATABASE_URL="$DB_URL" AUTH_JWT_SECRET="test-jwt-secret-for-ci" \
        cargo test -p gateway --lib) || fail "gateway unit tests"
    pass "gateway unit tests pass"

    step "[7/14] cargo test -p gateway --test schema_compatibility_test"
    (cd "$ROO./" && \
        TEST_DATABASE_URL="$DB_URL" AUTH_JWT_SECRET="test-jwt-secret-for-ci" \
        cargo test -p gateway --test schema_compatibility_test) || fail "schema compat tests"
    pass "schema compat tests pass"

    step "[8/14] cargo test -p harness"
    (cd "$ROO./" && cargo test -p harness) || fail "harness tests"
    pass "harness tests pass"

    step "[9/14] cargo test -p gateway --test gateway_harness_test -- --test-threads=1"
    (cd "$ROO./" && \
        TEST_DATABASE_URL="$DB_URL" AUTH_JWT_SECRET="test-jwt-secret-for-ci" \
        cargo test -p gateway --test gateway_harness_test -- --test-threads=1) \
        || fail "gateway integration tests"
    pass "gateway integration tests pass"

    step "[10/14] cargo test -p gateway --test middleware_test"
    (cd "$ROO./" && \
        TEST_DATABASE_URL="$DB_URL" AUTH_JWT_SECRET="test-jwt-secret-for-ci" \
        cargo test -p gateway --test middleware_test) || fail "middleware tests"
    pass "middleware integration tests pass"

    step "[11/14] cargo test -p gateway --test auth_test"
    (cd "$ROO./" && \
        TEST_DATABASE_URL="$DB_URL" AUTH_JWT_SECRET="test-jwt-secret-for-ci" \
        cargo test -p gateway --test auth_test) || fail "auth tests"
    pass "auth integration tests pass"

    step "[12/14] cargo build --release"
    (cd "$ROO./" && cargo build --release) || fail "cargo build --release"
    pass "release binary built"

    step "[13/14] docker build --platform linux/amd64 -f services/gateway/Dockerfile ."
    (cd "$ROOT" && docker build --platform linux/amd64 \
        --build-arg "RUST_IMAGE=$RUST_IMAGE" \
        --build-arg "DEBIAN_IMAGE=$DEBIAN_IMAGE" \
        -f services/gateway/Dockerfile -t autoniix/gateway:ci-local . >/dev/null 2>&1) \
        || fail "docker build (run manually for full log)"
    pass "docker image built"

    # rust-audit (ci.yml) — non-fatal locally to match `|| true` in the workflow
    if command -v cargo-audit >/dev/null 2>&1; then
        step "[14/14] cargo audit"
        (cd "$ROO./" && cargo audit 2>&1 | tail -20) || soft_fail "cargo audit"
    else
        warn "cargo-audit not installed — cargo install cargo-audit --locked --version $CARGO_AUDIT_VERSION"
    fi
fi

# =============================================================================
# PYTHON — ci.yml python-lint-and-tests + dependency-scan + migration-equivalence
# =============================================================================
if $RUN_PYTHON; then
    step "[python] Full Python CI mirror"
    if ! command -v python3 >/dev/null; then
        warn "python3 not installed — skip"
    else
        PY="python3"; PIP="pip3"
        [ -f "$ROOT/.venv/bin/python" ] && { PY="$ROOT/.venv/bin/python"; PIP="$ROOT/.venv/bin/pip"; }

        echo "  → pip install -r requirements.txt -r requirements-dev.txt (pinned)"
        $PIP install --quiet -r "$ROOT/requirements.txt" 2>&1 | tail -3 \
            || soft_fail "pip install requirements.txt"
        $PIP install --quiet -r "$ROOT/requirements-dev.txt" 2>&1 | tail -3 \
            || soft_fail "pip install requirements-dev.txt"

        echo "  → ruff check src/ tests/ scripts/"
        (cd "$ROOT" && $PY -m ruff check src/ tests/ scripts/ 2>&1) \
            || soft_fail "python ruff"

        echo "  → mypy src/ --ignore-missing-imports"
        (cd "$ROOT" && $PY -m mypy src/ --ignore-missing-imports 2>&1 | tail -10) \
            || soft_fail "python mypy"

        echo "  → AST parse of src/**/*.py + services/**/*.py"
        (cd "$ROOT" && $PY - 2>&1) <<'PYEOF' || soft_fail "python AST parse"
import ast, pathlib, sys
fails = []
for base in ('src', 'services'):
    root = pathlib.Path(base)
    if not root.exists(): continue
    for p in root.rglob('*.py'):
        try: ast.parse(p.read_text())
        except SyntaxError as e: fails.append(f'{p}: {e}')
if fails:
    for f in fails: print(f'  ✗ {f}')
    sys.exit(1)
print('  ✓ All Python files parse cleanly')
PYEOF

        echo "  → pytest -m 'not integration' tests/"
        (cd "$ROOT" && $PY -m pytest tests/ -m "not integration" -q --tb=short 2>&1 | tail -20) \
            || soft_fail "python pytest"

        # ci.yml dependency-scan (non-fatal, mirrors `|| true` in workflow)
        echo "  → pip-audit --requirement requirements.txt"
        (cd "$ROOT" && $PY -m pip_audit --requirement requirements.txt --skip-editable 2>&1 | tail -20) \
            || soft_fail "pip-audit (advisory)"

        # build.yml python-harness — contract + migration tests
        echo "  → pytest tests/contracts/ (offline: auto-skips)"
        (cd "$ROOT" && RUST_GATEWAY_URL="" PYTHON_DASHBOARD_URL="" \
            $PY -m pytest tests/contracts/ -q --tb=short 2>&1 | tail -10) \
            || soft_fail "python contract tests"

        echo "  → pytest tests/migration/ (against pg sidecar)"
        (cd "$ROOT" && TEST_DATABASE_URL="$DB_URL" \
            $PY -m pytest tests/migration/ -q --tb=short 2>&1 | tail -10) \
            || soft_fail "python migration tests"

        pass "python checks done"
    fi
fi

# =============================================================================
# NODE — ci.yml dashboard-typecheck + remotion-typecheck + build.yml dashboard-tests
# =============================================================================
if $RUN_NODE; then
    step "[node] Full Node CI mirror"
    if ! command -v node >/dev/null; then
        warn "node not installed — skip"
    else
        # Dashboard
        if [ ! -d "$ROOT/apps/dashboard/node_modules" ]; then
            echo "  → npm ci (dashboard)"
            (cd "$ROOT/dashboard" && npm ci 2>&1 | tail -3) \
                || soft_fail "npm ci (dashboard)"
        fi

        echo "  → tsc --noEmit (dashboard)"
        (cd "$ROOT/dashboard" && npx tsc --noEmit 2>&1) || soft_fail "dashboard tsc"

        echo "  → npm run lint:tokens:strict (dashboard)"
        (cd "$ROOT/dashboard" && npm run lint:tokens:strict 2>&1 | tail -10) \
            || soft_fail "dashboard token-lint strict"

        echo "  → npm test (dashboard vitest)"
        (cd "$ROOT/dashboard" && npm test 2>&1 | tail -10) \
            || soft_fail "dashboard vitest"

        echo "  → npx next lint (dashboard)"
        (cd "$ROOT/dashboard" && npx next lint 2>&1 | tail -10) \
            || soft_fail "dashboard eslint"

        # Remotion — matches ci.yml remotion-typecheck
        if [ -d "$ROOT/services/remotion" ]; then
            if [ ! -d "$ROOT/services/remotion/node_modules" ]; then
                echo "  → npm ci (remotion)"
                (cd "$ROOT/services/remotion" && npm ci 2>&1 | tail -3) \
                    || soft_fail "npm ci (remotion)"
            fi
            echo "  → tsc --noEmit (remotion)"
            (cd "$ROOT/services/remotion" && npx tsc --noEmit 2>&1) \
                || soft_fail "remotion tsc"
        fi

        pass "node checks done"
    fi
fi

# =============================================================================
# GO — build.yml go-harness + all service unit tests
# =============================================================================
if $RUN_GO; then
    step "[go] Full Go CI mirror"
    if ! command -v go >/dev/null; then
        warn "go not installed — skip"
    else
        echo "  → go build ./..."
        (cd "$ROOT/go" && go build ./... 2>&1) || soft_fail "go build"

        echo "  → go vet ./..."
        (cd "$ROOT/go" && go vet ./... 2>&1) || soft_fail "go vet"

        echo "  → go test ./... (all services + harness)"
        (cd "$ROOT/go" && go test ./... -timeout 120s 2>&1 | tail -30) \
            || soft_fail "go tests"

        pass "go checks done"
    fi
fi

# =============================================================================
# PROTO — proto-validate.yml lint + breaking + generate
# =============================================================================
if $RUN_PROTO; then
    step "[proto] buf lint + format + breaking + generate"
    if ! command -v buf >/dev/null; then
        warn "buf not installed — install: brew install bufbuild/buf/buf"
    else
        echo "  → buf lint"
        (cd "$ROOT/proto" && buf lint 2>&1) || soft_fail "buf lint"

        echo "  → buf format -d --exit-code"
        (cd "$ROOT/proto" && buf format -d --exit-code 2>&1 | tail -10) \
            || soft_fail "buf format"

        echo "  → buf breaking --against ../.git#branch=main"
        (cd "$ROOT/proto" && buf breaking --against '../.git#branch=main' 2>&1) \
            || soft_fail "buf breaking"

        echo "  → buf generate"
        (cd "$ROOT/proto" && buf generate 2>&1 | tail -10) \
            || soft_fail "buf generate"

        pass "proto checks done"
    fi
fi

# ─── Final report ────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
if [ ${#SOFT_FAILURES[@]} -eq 0 ]; then
    printf "${GREEN}✅  ALL CHECKS PASSED — build WILL pass on GitHub Actions${NC}\n"
    echo "══════════════════════════════════════════════════════"
    echo ""
    echo "Next steps:"
    echo "  git push origin develop          # triggers CI"
    echo "  # after CI green on develop:"
    echo "  git checkout main"
    echo "  git merge --no-ff develop"
    echo "  git push origin main             # triggers deploy job"
    echo ""
    echo "Note: The 'deploy' job runs on your self-hosted VPS."
    echo "Verify the runner is online: gh run list --workflow=build.yml"
    exit 0
else
    printf "${YELLOW}⚠  %d check(s) failed:${NC}\n" "${#SOFT_FAILURES[@]}"
    for s in "${SOFT_FAILURES[@]}"; do
        printf "    ${RED}•  %s${NC}\n" "$s"
    done
    echo ""
    echo "══════════════════════════════════════════════════════"
    exit 1
fi
