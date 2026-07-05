#!/usr/bin/env bash
#
# Phase D — Directory Restructure Migration Script
# ================================================
#
# Renames `src/services/*`, `src/intelligence/`, and select agent/embedding
# files under a new top-level `python/` layout as specified in ADR-001.
#
# THIS SCRIPT IS DESTRUCTIVE. Run only on a dedicated feature branch cut from
# `develop`, with a clean working tree, and validate the full test suite
# afterwards before merging.
#
# Usage:
#   git checkout -b chore/phase-d-restructure develop
#   ./scripts/phase-d-restructure.sh
#   pytest tests/
#   docker compose build
#   docker compose up -d && sleep 30 && docker compose ps
#   # verify all services healthy, then commit
#
# The script does two things:
#   1. `git mv` selected src paths under `python/`
#   2. `sed`-replace all import statements that reference the moved paths
#
# It refuses to run if the working tree is dirty.

set -euo pipefail

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: working tree is not clean. Commit or stash first." >&2
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

mkdir -p python

# ---------------------------------------------------------------------------
# 1. Move each target directory / file
# ---------------------------------------------------------------------------
declare -A MOVES=(
  ["src/services/brain"]="python/brain"
  ["src/services/analytics"]="python/analytics"
  ["src/services/experiments"]="python/experiments"
  ["src/services/finishing"]="python/finishing"
  ["src/services/delivery"]="python/delivery"
  ["src/services/thumbnail"]="python/thumbnail"
  ["src/services/voice"]="python/voice"
  ["src/services/research"]="python/research"
  ["src/services/script"]="python/script"
  ["src/intelligence"]="python/quality-gates"
)

for src in "${!MOVES[@]}"; do
  dst="${MOVES[$src]}"
  if [[ -d "$src" ]]; then
    echo "[MOVE dir] $src -> $dst"
    git mv "$src" "$dst"
  else
    echo "[SKIP]     $src (does not exist)"
  fi
done

# Single-file moves
declare -A FILE_MOVES=(
  ["src/agents/critic.py"]="python/agent-critic/critic.py"
  ["src/agents/preventor.py"]="python/agent-preventor/preventor.py"
  ["src/llm/embeddings.py"]="python/embeddings/embeddings.py"
  ["src/workers/activities/brand.py"]="python/brand/brand.py"
  ["src/workers/activities/editor.py"]="python/editor/editor.py"
)

for src in "${!FILE_MOVES[@]}"; do
  dst="${FILE_MOVES[$src]}"
  if [[ -f "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    echo "[MOVE file] $src -> $dst"
    git mv "$src" "$dst"
    # ensure package __init__.py exists
    touch "$(dirname "$dst")/__init__.py"
  else
    echo "[SKIP]      $src (does not exist)"
  fi
done

# ---------------------------------------------------------------------------
# 2. Rewrite import statements
# ---------------------------------------------------------------------------
#
# We use portable perl (-i works on both macOS and Linux without a backup arg).

rewrite() {
  local pattern="$1"
  local replacement="$2"
  echo "[SED] $pattern -> $replacement"
  find . -type f \
    \( -name "*.py" -o -name "*.md" -o -name "*.yml" -o -name "*.yaml" \
       -o -name "Dockerfile*" -o -name "Makefile" -o -name "*.sh" \) \
    -not -path "./.git/*" \
    -not -path "./gen/*" \
    -not -path "./.venv/*" \
    -not -path "./venv/*" \
    -not -path "./node_modules/*" \
    -not -path "./rust/target/*" \
    -not -path "./python/README.md" \
    -not -path "./scripts/phase-d-restructure.sh" \
    -print0 | xargs -0 perl -pi -e "s|${pattern}|${replacement}|g"
}

# Rewrite `from src.services.X` and `import src.services.X` to `python.X`
for pair in \
    "src.services.brain:python.brain" \
    "src.services.analytics:python.analytics" \
    "src.services.experiments:python.experiments" \
    "src.services.finishing:python.finishing" \
    "src.services.delivery:python.delivery" \
    "src.services.thumbnail:python.thumbnail" \
    "src.services.voice:python.voice" \
    "src.services.research:python.research" \
    "src.services.script:python.script" \
    "src.intelligence:python.quality-gates" \
    "src.agents.critic:python.agent-critic.critic" \
    "src.agents.preventor:python.agent-preventor.preventor" \
    "src.llm.embeddings:python.embeddings.embeddings" \
    "src.workers.activities.brand:python.brand.brand" \
    "src.workers.activities.editor:python.editor.editor" \
    ; do
  from="${pair%%:*}"
  to="${pair##*:}"
  # Note: python.quality-gates has a hyphen which is not a valid Python module name.
  # Convert to underscore for import paths.
  to_underscore="${to//-/_}"
  # Escape dots for regex
  from_re="${from//./\\.}"
  rewrite "$from_re" "$to_underscore"
done

# ---------------------------------------------------------------------------
# 3. Fix docker-compose service commands
# ---------------------------------------------------------------------------
# docker-compose has `python -m src.services.X.main:app` style commands.
# The perl rewrite above already covers these, but double-check with a grep.

echo ""
echo "Post-migration verification:"
echo "  Remaining src.services references:"
grep -rn "src\.services\." --include="*.py" --include="*.yml" --include="*.yaml" \
  --include="Dockerfile*" --include="Makefile" \
  . 2>/dev/null | grep -v "^./gen/" | grep -v "^./.venv/" | head -10 || echo "  (none)"

echo ""
echo "Done. Next steps:"
echo "  1. pytest tests/                          # run Python test suite"
echo "  2. docker compose config --quiet          # validate compose syntax"
echo "  3. docker compose build                   # rebuild service images"
echo "  4. docker compose up -d && sleep 60       # start stack"
echo "  5. docker compose ps                      # verify all healthy"
echo "  6. git commit -am 'chore(phase-d): restructure src/ to python/'"
echo "  7. git checkout develop && git merge --no-ff chore/phase-d-restructure"
