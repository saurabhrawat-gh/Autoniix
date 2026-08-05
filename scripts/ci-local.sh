#!/usr/bin/env bash
# =============================================================================
# ci-local.sh — Local mirror of GitHub Actions CI (Phase 7: Python + TypeScript).
#
# Answers: "will every required CI job pass?" — before you push.
#
# Every function below corresponds 1:1 to a GitHub Actions job. If a job's
# working-directory or command changes in .github/workflows/*, update the
# matching function here. Deviations from CI cause silent "green locally, red
# in CI" incidents — the entire point of this script is to prevent them.
#
# Modes:
#   (no flags)   Fast subset (~60s): format-check, lint, TS typecheck.
#   --full       Everything: all Python + TS + FE + migration jobs (~5-8min).
#   --docker     Wrap the whole run in the pinned ubuntu:24.04 image
#                (scripts/ci-local.Dockerfile). Byte-parity with GH Actions.
#
# Individual selectors (compose with --full or use standalone):
#   --python           python-lint-and-tests
#   --node             gateway + streaming-hub + contracts TS
#   --dashboard        dashboard-typecheck + frontend tests
#   --remotion         remotion-typecheck
#   --deps             dependency-scan (pip-audit + SBOM)
#   --migration        migration-equivalence (requires local postgres)
#   --python-harness   contract + migration tests (build.yml python-harness)
#
# Examples:
#   bash scripts/ci-local.sh                # fast subset
#   bash scripts/ci-local.sh --full         # everything, on host
#   bash scripts/ci-local.sh --full --docker # everything, inside ubuntu:24.04
#   bash scripts/ci-local.sh --python       # only the python job
#
# On failure, the script prints the exact CI job name that would fail, so a
# red local check maps 1:1 to the GitHub Actions page.
# =============================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PG_CONTAINER="ci-local-pg"
PG_PORT="15432"
PG_HOST="${PG_HOST:-localhost}"
DB_URL="postgresql://postgres:postgres@${PG_HOST}:${PG_PORT}/autoniix_test"

# Env normalization — match GitHub Actions ubuntu-latest byte-for-byte.
export TZ=UTC LC_ALL=C.UTF-8 LANG=C.UTF-8
export DOCKER_DEFAULT_PLATFORM=linux/amd64
export PIP_DISABLE_PIP_VERSION_CHECK=1
export NPM_CONFIG_FUND=false NPM_CONFIG_AUDIT=false

# Load version pins from single source of truth.
if [[ ! -f "$ROOT/versions.env" ]]; then
    echo "❌  $ROOT/versions.env missing" >&2
    exit 1
fi
set -a; source "$ROOT/versions.env"; set +a

# ─── Flag parsing ────────────────────────────────────────────────────────────
RUN_PYTHON=false
RUN_NODE=false
RUN_DASHBOARD=false
RUN_REMOTION=false
RUN_DEPS=false
RUN_MIGRATION=false
RUN_PYTHON_HARNESS=false
RUN_IN_DOCKER=false
RUN_FAST=true  # default: fast subset

for arg in "$@"; do
    case "$arg" in
        --python)          RUN_PYTHON=true;         RUN_FAST=false ;;
        --node)            RUN_NODE=true;           RUN_FAST=false ;;
        --dashboard)       RUN_DASHBOARD=true;      RUN_FAST=false ;;
        --remotion)        RUN_REMOTION=true;       RUN_FAST=false ;;
        --deps)            RUN_DEPS=true;           RUN_FAST=false ;;
        --migration)       RUN_MIGRATION=true;      RUN_FAST=false ;;
        --python-harness)  RUN_PYTHON_HARNESS=true; RUN_FAST=false ;;
        --full)
            RUN_PYTHON=true; RUN_NODE=true; RUN_DASHBOARD=true; RUN_REMOTION=true
            RUN_DEPS=true;   RUN_MIGRATION=true; RUN_PYTHON_HARNESS=true
            RUN_FAST=false
            ;;
        --docker)          RUN_IN_DOCKER=true ;;
        -h|--help)         sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown flag: $arg (use --help)"; exit 2 ;;
    esac
done

# ─── --docker mode: build pinned image and re-exec inside it ────────────────
if $RUN_IN_DOCKER; then
    command -v docker >/dev/null || { echo "❌  docker not installed"; exit 1; }
    docker info >/dev/null 2>&1 || { echo "❌  docker daemon not running"; exit 1; }
    HASH=$(sha256sum "$ROOT/versions.env" 2>/dev/null | awk '{print substr($1,1,12)}' || shasum -a 256 "$ROOT/versions.env" | awk '{print substr($1,1,12)}')
    TAG="autoniix/ci-local:${HASH}"
    if ! docker image inspect "$TAG" >/dev/null 2>&1; then
        echo "▶  Building ci-local image ($TAG) — one-time (~3 min)..."
        docker build --platform linux/amd64 \
            --build-arg "NODE_VERSION=$NODE_VERSION" \
            --build-arg "NPM_VERSION=$NPM_VERSION" \
            --build-arg "PYTHON_VERSION=$PYTHON_VERSION" \
            -f "$ROOT/scripts/ci-local.Dockerfile" -t "$TAG" "$ROOT" \
            || { echo "❌  Failed to build ci-local image"; exit 1; }
    else
        echo "▶  Reusing cached ci-local image ($TAG)"
    fi
    INNER=()
    for a in "$@"; do [[ "$a" == "--docker" ]] || INNER+=("$a"); done
    exec docker run --rm --platform linux/amd64 \
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
fail()  { printf "\n${RED}❌  CI JOB FAILED: %s${NC}\n" "$1" >&2
          printf "${RED}     (would fail as GH Actions job: %s)${NC}\n\n" "${2:-$1}" >&2
          exit 1; }
step()  { printf "\n${YELLOW}▶  %s${NC}\n" "$1"; }

FAILED_JOBS=()
run_job() {
    local name="$1" gh_name="$2" fn="$3"
    step "$name  (mirrors GH job: $gh_name)"
    if "$fn"; then
        pass "$name"
    else
        FAILED_JOBS+=("$gh_name")
        printf "${RED}❌  $name failed${NC}\n" >&2
    fi
}

# =============================================================================
# JOB FUNCTIONS — one per GH Actions job in .github/workflows/{ci,build}.yml
# =============================================================================

# GH job: ci.yml → python-lint-and-tests
job_python() {
    (cd "$ROOT" && ruff format --check . && ruff check .) || return 1
    # AST parse safety net across the whole Python tree (matches ci.yml).
    (cd "$ROOT" && python3 - <<'PY'
import ast, pathlib, sys
fails = []
for base in ("shared/python", "backend", "scripts"):
    root = pathlib.Path(base)
    if not root.exists():
        continue
    for p in root.rglob("*.py"):
        try:
            ast.parse(p.read_text())
        except SyntaxError as e:
            fails.append(f"{p}: {e}")
if fails:
    print("\n".join(fails)); sys.exit(1)
print("AST parse clean")
PY
    ) || return 1
    (cd "$ROOT" && pytest tests -q --ignore=tests/e2e -m "not integration") || return 1
    # Prompt-eval on mock LLM (matches ci.yml).
    if [[ -f "$ROOT/scripts/run_prompt_eval.py" ]]; then
        (cd "$ROOT" && python3 scripts/run_prompt_eval.py) || return 1
    fi
}

# GH job: ci.yml → contracts + gateway + streaming-hub TS
job_node() {
    (cd "$ROOT/shared/ts/contracts"       && npm ci --silent && npm run typecheck) || return 1
    (cd "$ROOT/backend/api/gateway"       && npm ci --silent && npm run typecheck && npm test) || return 1
    (cd "$ROOT/backend/api/streaming-hub" && npm ci --silent && npm run typecheck && npm test) || return 1
}

# GH job: ci.yml → dashboard-typecheck + build.yml → dashboard-frontend
job_dashboard() {
    if [[ ! -d "$ROOT/frontend/dashboard" ]]; then
        printf "${YELLOW}⏭  frontend/dashboard missing — skipping${NC}\n"
        return 0
    fi
    (cd "$ROOT/frontend/dashboard" && npm ci --silent) || return 1
    (cd "$ROOT/frontend/dashboard" && npm run lint:tokens:strict) || return 1
    (cd "$ROOT/frontend/dashboard" && npx tsc --noEmit) || return 1
    (cd "$ROOT/frontend/dashboard" && npm test -- --watch=false --passWithNoTests) || return 1
}

# GH job: ci.yml → remotion-typecheck
job_remotion() {
    local d="$ROOT/backend/media/remotion"
    if [[ ! -d "$d" ]]; then
        printf "${YELLOW}⏭  backend/media/remotion missing — skipping${NC}\n"
        return 0
    fi
    (cd "$d" && npm ci --silent) || return 1
    (cd "$d" && npx tsc --noEmit) || return 1
}

# GH job: ci.yml → dependency-scan
job_deps() {
    command -v pip-audit >/dev/null 2>&1 || pip install --quiet pip-audit
    (cd "$ROOT" && pip-audit --requirement requirements.txt --skip-editable \
        --ignore-vuln GHSA-r9hx-vwmv-q579) || return 1
}

# GH job: ci.yml → migration-equivalence
job_migration() {
    start_postgres || return 1
    apply_migrations || return 1
    (cd "$ROOT" && TEST_DATABASE_URL="$DB_URL" \
        pytest tests/migration/test_schema_compatibility.py -v) || return 1
}

# GH job: build.yml → python-harness
job_python_harness() {
    (cd "$ROOT" && RUST_GATEWAY_URL="" PYTHON_DASHBOARD_URL="" \
        pytest tests/contracts/ -v --tb=short -q) || return 1
    (cd "$ROOT" && RUST_GATEWAY_URL="" PYTHON_DASHBOARD_URL="" \
        pytest tests/migration/ -v --tb=short -q) || return 1
}

# ─── Postgres infra (only started if needed) ────────────────────────────────
start_postgres() {
    command -v docker >/dev/null || { echo "docker required for --migration"; return 1; }
    docker info >/dev/null 2>&1 || { echo "docker daemon not running"; return 1; }
    docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true
    docker run -d --name "$PG_CONTAINER" --platform linux/amd64 \
        -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=autoniix_test \
        -p "${PG_PORT}:5432" "$POSTGRES_IMAGE" >/dev/null
    for _ in $(seq 1 60); do
        docker exec "$PG_CONTAINER" pg_isready -U postgres >/dev/null 2>&1 && return 0
        sleep 1
    done
    return 1
}

apply_migrations() {
    docker exec -i "$PG_CONTAINER" psql -U postgres -d autoniix_test -v ON_ERROR_STOP=1 \
        < "$ROOT/scripts/init-db.sql" >/dev/null || return 1
    for f in "$ROOT/infra/migrations/"*.sql; do
        [[ -f "$f" ]] || continue
        docker exec -i "$PG_CONTAINER" psql -U postgres -d autoniix_test -v ON_ERROR_STOP=1 \
            < "$f" >/dev/null || return 1
    done
}

cleanup() { docker rm -f "$PG_CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# ─── Fast subset (default when no flags) ────────────────────────────────────
job_fast() {
    (cd "$ROOT" && ruff format --check . && ruff check .) || return 1
    (cd "$ROOT/shared/ts/contracts"       && npm run typecheck) || return 1
    (cd "$ROOT/backend/api/gateway"       && npm run typecheck) || return 1
    (cd "$ROOT/backend/api/streaming-hub" && npm run typecheck) || return 1
}

# =============================================================================
# EXECUTION
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ci-local — mirror of GitHub Actions CI (Phase 7)"
echo "═══════════════════════════════════════════════════════"

if $RUN_FAST; then
    run_job "Fast subset (ruff + TS typecheck)" "fast-subset" job_fast
fi

$RUN_PYTHON         && run_job "Python — lint + tests"         "python-lint-and-tests"  job_python
$RUN_NODE           && run_job "Node — contracts + APIs"       "ts-typecheck-and-tests" job_node
$RUN_DASHBOARD      && run_job "Dashboard — typecheck + tests" "dashboard-typecheck"    job_dashboard
$RUN_REMOTION       && run_job "Remotion — typecheck"          "remotion-typecheck"     job_remotion
$RUN_DEPS           && run_job "Dependency scan (pip-audit)"   "dependency-scan"        job_deps
$RUN_MIGRATION      && run_job "Migration equivalence"         "migration-equivalence"  job_migration
$RUN_PYTHON_HARNESS && run_job "Python harness"                "python-harness"         job_python_harness

echo ""
echo "═══════════════════════════════════════════════════════"
if [[ ${#FAILED_JOBS[@]} -gt 0 ]]; then
    printf "${RED}❌  ci-local FAILED — the following GH jobs would be red:${NC}\n"
    for j in "${FAILED_JOBS[@]}"; do
        printf "    • %s\n" "$j"
    done
    echo "═══════════════════════════════════════════════════════"
    exit 1
fi
printf "${GREEN}✅  ci-local passed — CI would be green.${NC}\n"
echo "═══════════════════════════════════════════════════════"
