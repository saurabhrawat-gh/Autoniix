#!/usr/bin/env bash
# Run once to create all GitHub labels for the Autoniix SDLC workflow.
# Usage: GITHUB_TOKEN=<your-pat> bash scripts/create-github-labels.sh

set -euo pipefail

REPO="saurabhrawat-gh/Autoniix"
API="https://api.github.com/repos/${REPO}/labels"
AUTH="Authorization: Bearer ${GITHUB_TOKEN}"

create_label() {
  local name="$1" color="$2" desc="$3"
  echo "Creating label: $name"
  curl -sf -X POST "$API" \
    -H "$AUTH" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    -d "{\"name\":\"${name}\",\"color\":\"${color}\",\"description\":\"${desc}\"}" \
    > /dev/null && echo "  ✓ $name" || echo "  ⚠ $name (may already exist)"
}

# ── Issue type labels ────────────────────────────────────────────────────────
create_label "feature"     "0075ca" "New capability from a story"
create_label "bug"         "d73a4a" "Defect in existing behaviour"
create_label "hotfix"      "b60205" "Critical prod-impacting fix — fast-track"
create_label "subtask"     "e4e669" "Atomic sub-item under a story or task"
create_label "test-case"   "6f42c1" "QA-generated test plan with checkbox test cases"
create_label "post-mortem" "f9d0c4" "Post-incident analysis"

# ── Workflow labels ──────────────────────────────────────────────────────────
create_label "ready-for-qa"    "bfd4f2" "BA complete — waiting for QA agent to create test cases"
create_label "qa-approved"     "c2e0c6" "QA agent has created test-case issues — ready for dev"

# ── Ticket lifecycle labels ──────────────────────────────────────────────────
create_label "in-progress"     "0052cc" "Developer is actively working on this"
create_label "dev-done"        "fbca04" "Code complete — PR opened — waiting for QA"
create_label "in-qa"           "e99695" "Manual QA in progress — tester checking test cases"
create_label "qa-verified"     "0e8a16" "All test cases verified by tester"
create_label "ready-to-merge"  "006b75" "QA verified — approved to merge to main"
create_label "in-prod"         "5319e7" "Deployed to production"
create_label "prod-verified"   "1d76db" "Verified working in production"
create_label "rolled-back"     "ee0701" "Deploy was rolled back due to issue"

echo ""
echo "Done. All labels created in https://github.com/${REPO}/labels"
