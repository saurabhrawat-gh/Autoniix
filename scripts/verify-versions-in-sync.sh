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
echo "1. Runtime pin files"
grep -qE "^channel *= *\"$RUST_VERSION\"" "$ROOT/rust-toolchain.toml" \
    && pass "rust-toolchain.toml channel = $RUST_VERSION" \
    || fail "rust-toolchain.toml channel != $RUST_VERSION"
[[ "$(tr -d '[:space:]' < "$ROOT/.nvmrc")" == "$NODE_VERSION" ]] \
    && pass ".nvmrc = $NODE_VERSION" || fail ".nvmrc != $NODE_VERSION"
[[ "$(tr -d '[:space:]' < "$ROOT/.python-version")" == "$PYTHON_VERSION" ]] \
    && pass ".python-version = $PYTHON_VERSION" || fail ".python-version != $PYTHON_VERSION"
[[ "$(tr -d '[:space:]' < "$ROOT/.go-version")" == "$GO_VERSION" ]] \
    && pass ".go-version = $GO_VERSION" || fail ".go-version != $GO_VERSION"
contains ".tool-versions" "rust $RUST_VERSION"     ".tool-versions rust"
contains ".tool-versions" "nodejs $NODE_VERSION"   ".tool-versions nodejs"
contains ".tool-versions" "python $PYTHON_VERSION" ".tool-versions python"
contains ".tool-versions" "golang $GO_VERSION"     ".tool-versions golang"
contains ".tool-versions" "buf $BUF_VERSION"       ".tool-versions buf"

echo ""
echo "2. package.json engines + packageManager"
check_pkg() {
    local pkg="$1"
    [[ -f "$ROOT/$pkg" ]] || return
    local pm en em
    pm=$(python3 -c "import json;print(json.load(open('$ROOT/$pkg')).get('packageManager',''))" 2>/dev/null || echo "")
    en=$(python3 -c "import json;print(json.load(open('$ROOT/$pkg')).get('engines',{}).get('node',''))" 2>/dev/null || echo "")
    em=$(python3 -c "import json;print(json.load(open('$ROOT/$pkg')).get('engines',{}).get('npm',''))" 2>/dev/null || echo "")
    [[ "$pm" == "npm@$NPM_VERSION" ]] && pass "$pkg packageManager = npm@$NPM_VERSION" \
        || fail "$pkg packageManager = '$pm' (expected npm@$NPM_VERSION)"
    [[ "$en" == "$NODE_VERSION" ]] && pass "$pkg engines.node = $NODE_VERSION" \
        || fail "$pkg engines.node = '$en' (expected $NODE_VERSION)"
    [[ "$em" == "$NPM_VERSION" ]] && pass "$pkg engines.npm = $NPM_VERSION" \
        || fail "$pkg engines.npm = '$em' (expected $NPM_VERSION)"
}
check_pkg "package.json"
check_pkg "dashboard/package.json"
check_pkg "services/remotion/package.json"
check_pkg "web/package.json"

echo ""
echo "3. Workflow YAML — no floating action pins, no literal versions, no pg16"
for wf in "$ROOT"/.github/workflows/*.yml; do
    rel="${wf#$ROOT/}"
    not_contains "$rel" 'rust-toolchain@stable'         "$rel: no rust-toolchain@stable"
    not_contains "$rel" 'buf-setup-action@v1$'          "$rel: no unpinned buf-setup-action"
    not_contains "$rel" 'pgvector/pgvector:pg16'        "$rel: no pg16 (must be pg15)"
    not_contains "$rel" '^[[:space:]]*python-version: ' "$rel: no literal python-version"
    not_contains "$rel" '^[[:space:]]*node-version: '   "$rel: no literal node-version"
    not_contains "$rel" '^[[:space:]]*go-version: '     "$rel: no literal go-version"
done

echo ""
echo "4. Dockerfile pins"
contains "rust/gateway/Dockerfile"              "RUST_IMAGE=rust:$RUST_VERSION-bookworm"       "rust/gateway rust image"
contains "rust/gateway/Dockerfile"              "DEBIAN_IMAGE=debian:bookworm-slim"            "rust/gateway debian image"
contains "rust/gateway/Dockerfile"              "COPY rust-toolchain.toml"                     "rust/gateway copies rust-toolchain.toml"
contains "dashboard/Dockerfile"                 "NODE_ALPINE_IMAGE=node:$NODE_VERSION-alpine"  "dashboard node-alpine"
contains "web/Dockerfile"                       "NODE_ALPINE_IMAGE=node:$NODE_VERSION-alpine"  "web node-alpine"
contains "services/remotion/Dockerfile"         "NODE_IMAGE=node:$NODE_VERSION-bookworm-slim"  "remotion node-bookworm-slim"
contains "Dockerfile"                           "PYTHON_IMAGE=python:$PYTHON_VERSION-slim"     "root python"
contains "services/sentry-agent/Dockerfile"     "PYTHON_IMAGE=python:$PYTHON_VERSION-slim"     "sentry-agent python"
contains "services/resolve-finisher/Dockerfile" "PYTHON_IMAGE=python:$PYTHON_VERSION-slim"     "resolve-finisher python"

echo ""
echo "5. docker-compose.yml postgres image"
contains "docker-compose.yml" "image: $POSTGRES_IMAGE" "docker-compose postgres-app image"

echo ""
if [[ $FAILED -ne 0 ]]; then
    printf "${RED}❌  Drift detected — fix the files above.${NC}\n"
    exit 1
fi
printf "${GREEN}✅  Every pinned file is in sync with versions.env${NC}\n"
