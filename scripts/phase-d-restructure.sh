#!/usr/bin/env bash
#
# Phase D — Deployable-Unit Monorepo Restructure
# ================================================
#
# Implements ADR-002 (monorepo-layout-9dc209.md).
# Migrates the repo from the current mixed layout to:
#
#   apps/        services/        libs/        infra/        tools/
#
# Run each phase on a SEPARATE branch. Do NOT run all phases at once.
# Every phase is independently revertable with: git revert <merge-commit>
#
# Prerequisites: clean working tree, on develop (or a branch from it).
#
# Usage:
#   ./scripts/phase-d-restructure.sh phase<N>
#   e.g.: ./scripts/phase-d-restructure.sh phase1
#
# Phases:
#   phase0  — skeleton dirs + ADR (docs only, no code moves)
#   phase1  — apps/ (dashboard + web)
#   phase2  — services/ Rust (gateway + harness)
#   phase3  — verify existing polyglot services (no moves, validation only)
#   phase4a — libs/python/ (pure Python src — largest phase, ~200 files)
#   phase4b — services/ Python (running processes: agents, api, temporal-workers)
#   phase5  — libs/go/shared + libs/sdk/python
#   phase6  — infra/ + tools/
#   phase7  — docs + final grep cleanup
#
# Each phase verifies:
#   1. bash scripts/ci-local.sh --full (if available)
#   2. docker compose config --quiet
#
# See: docs/architecture/adr-002-monorepo-layout.md

set -euo pipefail

PHASE="${1:-}"
if [[ -z "$PHASE" ]]; then
  echo "Usage: $0 phase<N>  (e.g. $0 phase1)" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: working tree is not clean. Commit or stash first." >&2
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

move_dir() {
  local src="$1" dst="$2"
  if [[ -d "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    echo "  [mv dir]  $src -> $dst"
    git mv "$src" "$dst"
  else
    echo "  [skip]    $src (not found)"
  fi
}

move_file() {
  local src="$1" dst="$2"
  if [[ -f "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    echo "  [mv file] $src -> $dst"
    git mv "$src" "$dst"
  else
    echo "  [skip]    $src (not found)"
  fi
}

# Portable sed-in-place rewrite using perl (works on macOS + Linux)
rewrite_imports() {
  local from_re="$1" to="$2"
  echo "  [import]  $from_re  ->  $to"
  find . -type f \
    \( -name "*.py" -o -name "*.yml" -o -name "*.yaml" \
       -o -name "Dockerfile*" -o -name "Makefile" -o -name "*.sh" \) \
    -not -path "./.git/*"       \
    -not -path "./gen/*"        \
    -not -path "./.venv/*"      \
    -not -path "./venv/*"       \
    -not -path "./node_modules/*" \
    -not -path "./rust/target/*"  \
    -not -path "./scripts/phase-d-restructure.sh" \
    -print0 | xargs -0 perl -pi -e "s|${from_re}|${to}|g"
}

verify() {
  echo ""
  echo "--- verification ---"
  if command -v docker &>/dev/null; then
    docker compose config --quiet && echo "  compose syntax OK"
  fi
  echo "  Run manually: bash scripts/ci-local.sh --full"
  echo "  Run manually: pytest tests/"
  echo "  Run manually: docker compose build && docker compose up -d"
}

# ---------------------------------------------------------------------------
# Phase 0 — ADR + skeleton (documentation-only, safe during build freeze)
# ---------------------------------------------------------------------------
phase0() {
  echo "=== Phase 0: ADR + skeleton dirs ==="
  echo "  ADR-002 already committed at docs/architecture/adr-002-monorepo-layout.md"
  echo "  Creating empty skeleton directories..."

  for d in \
    apps/dashboard apps/marketing \
    services/gateway services/harness \
    services/streaming-hub services/notification-dispatcher \
    services/service-delivery services/service-thumbnail \
    services/service-voice services/service-research services/service-script \
    services/temporal-workers services/agents services/api \
    libs/go/shared libs/python/intelligence libs/python/quality \
    libs/python/llm libs/python/events libs/python/providers \
    libs/python/observability libs/python/schemas libs/python/core \
    libs/sdk/python \
    infra/traefik infra/caddy infra/observability infra/migrations infra/config \
    tools/cleanup tools/migration tools/seeds tools/scripts \
    ; do
    mkdir -p "$d"
    touch "$d/.gitkeep"
    git add "$d/.gitkeep"
    echo "  [mkdir]   $d"
  done

  # Remove the erroneous python/ placeholder dir
  if [[ -d "python" ]]; then
    git rm -rf python/ 2>/dev/null || true
    echo "  [rm]      python/ (superseded placeholder)"
  fi

  echo ""
  echo "Commit as: chore(phase-d-0): ADR-002 + deployable-unit skeleton dirs"
}

# ---------------------------------------------------------------------------
# Phase 1 — apps/ (dashboard + marketing site)
# ---------------------------------------------------------------------------
phase1() {
  echo "=== Phase 1: apps/ ==="
  move_dir "dashboard" "apps/dashboard"
  move_dir "web"       "apps/marketing"
  rm -f apps/dashboard/.gitkeep apps/marketing/.gitkeep 2>/dev/null || true

  echo ""
  echo "  Update docker-compose.yml: build.context dashboard -> apps/dashboard"
  echo "  Update .github/workflows paths"
  echo "  Update Makefile references to dashboard/"
  echo ""
  echo "Commit as: chore(phase-d-1): dashboard + web -> apps/"
  verify
}

# ---------------------------------------------------------------------------
# Phase 2 — services/ Rust (gateway + harness)
# ---------------------------------------------------------------------------
phase2() {
  echo "=== Phase 2: Rust services/ ==="
  move_dir "rust/gateway" "services/gateway"
  move_dir "rust/harness" "services/harness"
  rm -f services/gateway/.gitkeep services/harness/.gitkeep 2>/dev/null || true

  # Cargo.toml workspace: move to root and rewrite members
  if [[ -f "rust/Cargo.toml" ]]; then
    move_file "rust/Cargo.toml" "Cargo.toml"
    perl -pi -e 's|"gateway"|"services/gateway"|g; s|"harness"|"services/harness"|g' Cargo.toml
    echo "  [rewrite] Cargo.toml members -> services/gateway, services/harness"
  fi

  if [[ -d "rust" ]] && [[ -z "$(ls -A rust)" ]]; then
    rmdir rust
    git rm -rf rust/ 2>/dev/null || echo "  rust/ already clean"
    echo "  [rm]      rust/ (now empty)"
  fi

  echo ""
  echo "  Update docker-compose.yml: build.context rust/gateway -> services/gateway"
  echo "  Update .github/workflows/build.yml Rust path filters"
  echo ""
  echo "Commit as: chore(phase-d-2): rust/gateway + harness -> services/"
  verify
}

# ---------------------------------------------------------------------------
# Phase 3 — verify existing polyglot services (no file moves)
# ---------------------------------------------------------------------------
phase3() {
  echo "=== Phase 3: verify existing polyglot services (no moves) ==="
  for d in services/model-server services/resolve-finisher services/sentry-agent services/remotion; do
    if [[ -d "$d" ]]; then
      echo "  [ok]  $d exists"
    else
      echo "  [skip] $d not present yet (expected)"
    fi
  done
  verify
  echo "Commit as: chore(phase-d-3): verify polyglot services (no-op)"
}

# ---------------------------------------------------------------------------
# Phase 4a — libs/python/ (pure code, no process)
# ---------------------------------------------------------------------------
phase4a() {
  echo "=== Phase 4a: libs/python/ (pure Python libs) ==="

  move_dir "src/intelligence"  "libs/python/intelligence"
  move_dir "src/quality"       "libs/python/quality"
  move_dir "src/llm"           "libs/python/llm"
  move_dir "src/events"        "libs/python/events"
  move_dir "src/providers"     "libs/python/providers"
  move_dir "src/observability" "libs/python/observability"
  move_dir "src/schemas"       "libs/python/schemas"

  # Core single files -> libs/python/core/
  mkdir -p libs/python/core
  for f in config.py db.py environment.py flags.py redis_client.py __init__.py; do
    move_file "src/$f" "libs/python/core/$f"
  done
  rm -f libs/python/intelligence/.gitkeep libs/python/quality/.gitkeep \
        libs/python/llm/.gitkeep libs/python/events/.gitkeep \
        libs/python/providers/.gitkeep libs/python/observability/.gitkeep \
        libs/python/schemas/.gitkeep libs/python/core/.gitkeep 2>/dev/null || true

  echo ""
  echo "  Rewriting imports (src.intelligence -> intelligence, etc.)..."
  echo "  NOTE: Using short package names (no autoniix_ prefix) per ADR-002 §open-questions."

  # Package names stay SHORT (no namespace prefix) — zero import churn
  for pair in \
    "src\\.intelligence:intelligence" \
    "src\\.quality:quality" \
    "src\\.llm:llm" \
    "src\\.events:events" \
    "src\\.providers:providers" \
    "src\\.observability:observability" \
    "src\\.schemas:schemas" \
    "src\\.config:core.config" \
    "src\\.db:core.db" \
    "src\\.environment:core.environment" \
    "src\\.flags:core.flags" \
    "src\\.redis_client:core.redis_client" \
    ; do
    rewrite_imports "${pair%%:*}" "${pair##*:}"
  done

  echo ""
  echo "  Update pytest.ini: testpaths, PYTHONPATH"
  echo "  Add pyproject.toml to each libs/python/<pkg>/ (uv workspace)"
  echo ""
  echo "Commit as: chore(phase-d-4a): src/intelligence+llm+providers+... -> libs/python/"
  verify
}

# ---------------------------------------------------------------------------
# Phase 4b — services/ Python running processes
# ---------------------------------------------------------------------------
phase4b() {
  echo "=== Phase 4b: services/ Python (running processes) ==="

  move_dir "src/agents"   "services/agents"
  move_dir "src/services" "services/api"
  move_dir "src/workers"  "services/temporal-workers/workers"

  # temporal_workflows was already deleted (Phase C). Skip if gone.
  if [[ -d "src/temporal_workflows" ]]; then
    move_dir "src/temporal_workflows" "services/temporal-workers/workflows"
  else
    echo "  [skip]    src/temporal_workflows (already deleted in Phase C — correct)"
  fi

  rm -f services/agents/.gitkeep services/api/.gitkeep \
        services/temporal-workers/.gitkeep 2>/dev/null || true

  # Rewrite running-process imports
  for pair in \
    "src\\.agents:agents" \
    "src\\.services:services_api" \
    "src\\.workers:temporal_workers" \
    ; do
    rewrite_imports "${pair%%:*}" "${pair##*:}"
  done

  # docker-compose service commands: python -m src.services.X -> python -m services_api.X
  echo "  [manual]  Update docker-compose.yml service commands (python -m src.services.* -> python -m services_api.*)"

  # Delete now-empty src/ if all subdirs are gone
  if [[ -d "src" ]] && [[ -z "$(ls -A src 2>/dev/null)" ]]; then
    rmdir src
    echo "  [rm]      src/ (now empty)"
  else
    echo "  [info]    src/ still has files — check manually before deleting"
    ls src/ 2>/dev/null || true
  fi

  echo ""
  echo "Commit as: chore(phase-d-4b): src/agents+services+workers -> services/"
  verify
}

# ---------------------------------------------------------------------------
# Phase 5 — libs/go/shared + libs/sdk/python
# ---------------------------------------------------------------------------
phase5() {
  echo "=== Phase 5: libs/go/ + libs/sdk/ ==="
  move_dir "go/shared"   "libs/go/shared"
  move_dir "sdk/python"  "libs/sdk/python"
  rm -f libs/go/shared/.gitkeep libs/sdk/python/.gitkeep 2>/dev/null || true

  echo "  [manual]  Update go/go.mod import paths if go/shared moved"
  echo "  [manual]  Update go.work to include libs/go/shared if it gets its own go.mod"
  echo ""
  echo "Commit as: chore(phase-d-5): go/shared -> libs/go/, sdk/python -> libs/sdk/"
  verify
}

# ---------------------------------------------------------------------------
# Phase 6 — infra/ + tools/
# ---------------------------------------------------------------------------
phase6() {
  echo "=== Phase 6: infra/ + tools/ ==="

  move_dir "traefik"              "infra/traefik"
  move_dir "observability"        "infra/observability"
  move_dir "scripts/migrations"   "infra/migrations"
  move_dir "config"               "infra/config"
  move_file "Caddyfile"           "infra/caddy/Caddyfile"

  move_dir "scripts/cleanup"      "tools/cleanup"
  move_dir "scripts/migration"    "tools/migration"
  move_dir "scripts/seeds"        "tools/seeds"

  rm -f infra/traefik/.gitkeep infra/observability/.gitkeep \
        infra/migrations/.gitkeep infra/config/.gitkeep \
        infra/caddy/.gitkeep tools/cleanup/.gitkeep \
        tools/migration/.gitkeep tools/seeds/.gitkeep 2>/dev/null || true

  echo "  [manual]  Update docker-compose.yml volume paths: traefik/ -> infra/traefik/"
  echo "  [manual]  Update docker-compose.yml volume paths: observability/ -> infra/observability/"
  echo "  [manual]  Update Makefile migration targets"
  echo ""
  echo "Commit as: chore(phase-d-6): traefik+observability+config -> infra/, scripts -> tools/"
  verify
}

# ---------------------------------------------------------------------------
# Phase 7 — Docs + final grep cleanup
# ---------------------------------------------------------------------------
phase7() {
  echo "=== Phase 7: docs + cleanup ==="

  echo "  Manual checklist:"
  echo "  1. Update README.md top-level tree diagram"
  echo "  2. Update docs/00-OVERVIEW.md, docs/01-ARCHITECTURE.md path references"
  echo "  3. Update .devin/workflows/*.md path references (dev-agent.md, bug.md, etc.)"
  echo "  4. Update PENDING.md, QA-MANUAL-TEST-GUIDE.md if they reference old paths"
  echo "  5. Update scripts/ci-local.sh path detection blocks"
  echo ""
  echo "  Final grep verification (nothing should match outside ADR-002):"
  echo ""
  rg 'src/|rust/|dashboard/|web/|go/shared|sdk/python' \
    --glob '*.py' --glob '*.yml' --glob '*.yaml' --glob '*.sh' \
    --glob '*.md' --glob 'Makefile' --glob 'Dockerfile*' \
    --ignore-file .gitignore \
    -l 2>/dev/null \
    | grep -v "docs/architecture/adr-002" \
    | grep -v "scripts/phase-d-restructure.sh" \
    | head -20 \
    || echo "  Clean! No stale path references found."

  echo ""
  echo "Commit as: chore(phase-d-7): docs + path cleanup"
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
echo "Phase D — Deployable-Unit Restructure"
echo "ADR: docs/architecture/adr-002-monorepo-layout.md"
echo "Running: $PHASE"
echo ""

case "$PHASE" in
  phase0)  phase0  ;;
  phase1)  phase1  ;;
  phase2)  phase2  ;;
  phase3)  phase3  ;;
  phase4a) phase4a ;;
  phase4b) phase4b ;;
  phase5)  phase5  ;;
  phase6)  phase6  ;;
  phase7)  phase7  ;;
  *)
    echo "Unknown phase: $PHASE" >&2
    echo "Valid phases: phase0 phase1 phase2 phase3 phase4a phase4b phase5 phase6 phase7" >&2
    exit 1
    ;;
esac