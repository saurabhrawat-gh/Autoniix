#!/usr/bin/env bash
# Assert local tools match versions.env. Exit 1 on any mismatch.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VE="$ROOT/versions.env"
[[ -f "$VE" ]] || { echo "❌  versions.env not found" >&2; exit 2; }
set -a; source "$VE"; set +a

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
FAILED=0

check() {
    local t="$1" e="$2" a="$3" src="$4"
    if [[ -z "$a" ]]; then
        printf "  ${RED}✗${NC} %-9s not installed (expected %s)\n" "$t" "$e"
        FAILED=1; return
    fi
    if [[ "$a" == "$e" ]]; then
        printf "  ${GREEN}✓${NC} %-9s %-12s (pinned via %s)\n" "$t" "$a" "$src"
    else
        printf "  ${RED}✗${NC} %-9s %-12s (expected %s, pinned via %s)\n" "$t" "$a" "$e" "$src"
        FAILED=1
    fi
}
check_min() {
    local t="$1" m="$2" a="$3"
    if [[ -z "$a" ]]; then
        printf "  ${RED}✗${NC} %-9s not installed (expected >= %s)\n" "$t" "$m"
        FAILED=1; return
    fi
    local s; s=$(printf '%s\n%s\n' "$m" "$a" | sort -V | head -n1)
    if [[ "$s" == "$m" ]]; then
        printf "  ${GREEN}✓${NC} %-9s %-12s (>= %s)\n" "$t" "$a" "$m"
    else
        printf "  ${RED}✗${NC} %-9s %-12s (expected >= %s)\n" "$t" "$a" "$m"
        FAILED=1
    fi
}

echo "Verifying local toolchain against versions.env..."

R=""; command -v rustc >/dev/null 2>&1 && R=$(rustc --version 2>/dev/null | awk '{print $2}')
check "rustc"   "$RUST_VERSION"   "$R"  "rust-toolchain.toml"
N=""; command -v node  >/dev/null 2>&1 && N=$(node --version 2>/dev/null | sed 's/^v//')
check "node"    "$NODE_VERSION"   "$N"  ".nvmrc"
M=""; command -v npm   >/dev/null 2>&1 && M=$(npm --version 2>/dev/null)
check "npm"     "$NPM_VERSION"    "$M"  "package.json packageManager"
P=""; command -v python3 >/dev/null 2>&1 && P=$(python3 --version 2>/dev/null | awk '{print $2}')
check "python3" "$PYTHON_VERSION" "$P"  ".python-version"
G=""; command -v go    >/dev/null 2>&1 && G=$(go version 2>/dev/null | awk '{print $3}' | sed 's/^go//')
check "go"      "$GO_VERSION"     "$G"  ".go-version"
B=""; command -v buf   >/dev/null 2>&1 && B=$(buf --version 2>/dev/null | awk '{print $NF}')
check "buf"     "$BUF_VERSION"    "$B"  ".tool-versions"

if [[ "${SKIP_DOCKER:-0}" != "1" ]]; then
    D=""; command -v docker >/dev/null 2>&1 && \
        D=$(docker --version 2>/dev/null | sed -E 's/Docker version ([0-9.]+).*/\1/')
    check_min "docker" "24.0.0" "$D"
fi

echo ""
if [[ $FAILED -ne 0 ]]; then
    printf "${RED}One or more toolchain versions do not match versions.env.${NC}\n\n"
    cat <<HELP
Install the pinned versions with one of:
  mise install                              # reads .tool-versions
  asdf install                              # reads .tool-versions
  rustup show                               # Rust auto-installs from rust-toolchain.toml
  nvm install \$(cat .nvmrc) && nvm use
  pyenv install \$(cat .python-version) && pyenv local \$(cat .python-version)

Or run the pipeline in a pinned container:
  bash scripts/ci-local.sh --docker
HELP
    exit 1
fi
printf "${GREEN}✅  All toolchain versions match versions.env${NC}\n"
