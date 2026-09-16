#!/usr/bin/env bash
# apply-branch-protection.sh — idempotently apply .github/branch-protection.yml
# to the current GitHub repo. Requires: gh CLI authed as an org admin.
#
# Usage:
#   bash scripts/apply-branch-protection.sh              # apply
#   bash scripts/apply-branch-protection.sh --dry-run    # show payloads only

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="$ROOT/.github/branch-protection.yml"
DRY=false
[[ "${1:-}" == "--dry-run" ]] && DRY=true

command -v gh >/dev/null || { echo "❌ gh CLI not installed"; exit 1; }
command -v python3 >/dev/null || { echo "❌ python3 not installed"; exit 1; }

REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
echo "▶  Repo: $REPO"

python3 - "$CFG" <<'PY' > /tmp/branch-protection.json
import json, sys
try:
    import yaml
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "pyyaml"])
    import yaml
with open(sys.argv[1]) as f:
    doc = yaml.safe_load(f)
print(json.dumps(doc))
PY

for BRANCH in main develop; do
    PAYLOAD=$(python3 -c "
import json
d = json.load(open('/tmp/branch-protection.json'))
print(json.dumps(d.get('$BRANCH', {})))
")
    if [[ "$PAYLOAD" == "{}" ]]; then
        echo "⏭  No config for $BRANCH — skipping."
        continue
    fi
    echo ""
    echo "▶  Applying protection for $BRANCH"
    if $DRY; then
        echo "$PAYLOAD" | python3 -m json.tool
        continue
    fi
    echo "$PAYLOAD" | gh api --method PUT \
        "repos/$REPO/branches/$BRANCH/protection" \
        --input - \
        -H "Accept: application/vnd.github+json" >/dev/null
    echo "✓  $BRANCH protected"
done

echo ""
echo "✅ Branch protection applied."
echo "   Verify:  gh api repos/$REPO/branches/main/protection --jq '.required_status_checks'"
