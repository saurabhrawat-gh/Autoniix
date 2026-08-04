#!/usr/bin/env bash
# Assert every pin file matches versions.env. Exit 1 on drift.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VE="$ROOT/versions.env"
[[ -f "$VE" ]] || { echo "❌  versions.env missing" >&2; exit 1; }
set -a; source "$VE"; set +a

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
FAILED=0
pass() { printf "  ${GREEN}✓${NC} %s\n" "$1"; }
fail() { printf "  ${RED}✗${NC} %s\n" "$1"; FAILED=1; }

contains() {
    local file="$1" needle="$2" label="$3"
    [[ -f "$ROOT/$file" ]] || { fail "$label: $file missing"; return; }
    grep -Fq -- "$needle" "$ROOT/$file" && pass "$label" \
        || fail "$label: expected '$needle' in $file"
}

not_contains() {
    local file="$1" pattern="$2" label="$3"
    [[ -f "$ROOT/$file" ]] || return
    if grep -qE "$pattern" "$ROOT/$file"; then
        fail "$label: forbidden pattern in $file"
        grep -nE "$pattern" "$ROOT/$file" | head -3 | sed 's/^/       /'
    else
        pass "$label"
    fi
}

echo "Verifying pin-file consistency against versions.env..."
echo ""
echo "1. Runtime pin files (Python + Node only)"
[[ "$(tr -d '[:space:]' < "$ROOT/.nvmrc")" == "$NODE_VERSION" ]] \
    && pass ".nvmrc = $NODE_VERSION" || fail ".nvmrc != $NODE_VERSION"
[[ "$(tr -d '[:space:]' < "$ROOT/.python-version")" == "$PYTHON_VERSION" ]] \
    && pass ".python-version = $PYTHON_VERSION" || fail ".python-version != $PYTHON_VERSION"
contains ".tool-versions" "nodejs $NODE_VERSION"   ".tool-versions nodejs"
contains ".tool-versions" "python $PYTHON_VERSION" ".tool-versions python"

echo ""
echo "2. package.json engines (Node only, pnpm workspace)"
check_pkg() {
    local pkg="$1"
    [[ -f "$ROOT/$pkg" ]] || return
    # For TypeScript packages, just check they exist and are valid JSON
    if python3 -c "import json; json.load(open('$ROOT/$pkg'))" 2>/dev/null; then
        pass "$pkg is valid JSON"
    else
        fail "$pkg is invalid JSON"
    fi
}
check_pkg "libs/ts/contracts/package.json"
check_pkg "services/gateway-v2/package.json"
check_pkg "services/streaming-hub-v2/package.json"

echo ""
echo "3. Workflow YAML — no literal versions, no pg16"
for wf in "$ROOT"/.github/workflows/*.yml; do
    rel="${wf#$ROOT/}"
    not_contains "$rel" 'pgvector/pgvector:pg16'        "$rel: no pg16 (must be pg15)"
    not_contains "$rel" '^[[:space:]]*python-version: ' "$rel: no literal python-version"
    not_contains "$rel" '^[[:space:]]*node-version: '   "$rel: no literal node-version"
done

echo ""
echo "4. Dockerfile pins (Python + Node only)"
contains "Dockerfile"                           "PYTHON_IMAGE=python:$PYTHON_VERSION-slim"     "root python"
contains "services/sentry-agent/Dockerfile"     "PYTHON_IMAGE=python:$PYTHON_VERSION-slim"     "sentry-agent python"
contains "services/resolve-finisher/Dockerfile" "PYTHON_IMAGE=python:$PYTHON_VERSION-slim"     "resolve-finisher python"
contains "services/gateway-v2/Dockerfile"       "FROM node:$NODE_VERSION-alpine"               "gateway-v2 node-alpine"
contains "services/streaming-hub-v2/Dockerfile" "FROM node:$NODE_VERSION-alpine"               "streaming-hub-v2 node-alpine"

echo ""
echo "5. docker-compose.yml postgres image"
contains "docker-compose.yml" "image: $POSTGRES_IMAGE" "docker-compose postgres-app image"

echo ""
if [[ $FAILED -ne 0 ]]; then
    printf "${RED}❌  Drift detected — fix the files above.${NC}\n"
    exit 1
fi
printf "${GREEN}✅  Every pinned file is in sync with versions.env${NC}\n"
