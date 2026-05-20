---
description: Scrum Master — scan all open issues, report board state, surface anomalies, and flag what needs human attention. Does NOT execute transitions — those are handled by GitHub Actions and agents automatically.
---

# Scrum Master Workflow

Run `/scrum-master` at any time to get a full board health report.

**What this agent does:** Reads, scans, reports, flags anomalies, and suggests actions.
**What this agent does NOT do:** Change labels, close issues, or move tickets. Transitions are handled by:
- Dev Agent → sets `in-qa` when branch merges to develop
- QA Agent → sets `qa-verified` when all tests pass
- GitHub Actions → handles `qa-verified → ready-to-deploy → in-prod → closed`

## Full Issue Lifecycle (reference)

```
ready-for-dev → in-progress → in-qa → qa-verified → ready-to-deploy → in-prod → prod-verified → CLOSED

Hotfix path: ready-for-dev → in-progress → in-prod → prod-verified → CLOSED
```

Who drives each transition:
- `ready-for-dev → in-progress` : Dev Agent (picks up issue)
- `in-progress → in-qa` : Dev Agent (merges to develop + calls GitHub MCP)
- `in-qa → qa-verified` : QA Agent (walks test cases with user + calls GitHub MCP)
- `qa-verified → ready-to-deploy` : **GitHub Actions** (auto, label trigger)
- `ready-to-deploy → in-prod` : **GitHub Actions** (auto, after deploy to main)
- `in-prod → CLOSED` : **GitHub Actions** (auto, after user adds `prod-verified` + all ACs ticked)
- `in-progress → in-prod` (hotfix) : Dev Agent (merges to main + calls GitHub MCP)

---

## Steps

### 1. Fetch the full board
- Use `mcp0_list_issues` on `saurabhrawat-gh/Autoniix` with `state=open`, `per_page=100`
- Skip any issue with a `pull_request` key (those are PRs, not issues)
- Group by lifecycle label

### 2. Print board state

```
── BOARD STATE ── {date} ──────────────────────────────────
  ready-for-dev    : #N title, #N title …
  in-progress      : …
  in-qa            : …
  qa-verified      : …
  ready-to-deploy  : …
  in-prod          : …
  ⚠️ No label      : … (these need investigation)
──────────────────────────────────────────────────────────
```

### 3. Check Epic → Story → Task hierarchy health
For each open Epic issue:
- Search its body for `#{N}` child story references
- Fetch each child story's state and lifecycle label
- Determine Epic status:
  - ALL stories closed → flag: "Epic ready to close"
  - SOME stories in-prod or beyond → flag: "Epic partially complete"
  - ZERO stories started → flag: "Epic not started"
  - Any story stuck `in-progress` > 5 days → flag: "Epic has stalled story"

For each open Story issue:
- Search its body for child task references
- If all child tasks are closed but story is not `prod-verified`: flag "Story has all tasks done — needs prod verification"
- If story is `qa-verified` or beyond but Epic is still `in-progress`: flag "Epic label may be stale"

### 4. Check for stale issues
Flag any issue stuck in the same state too long:

| State | Stale after |
|---|---|
| `in-progress` | 5 days since last update |
| `in-qa` | 3 days since last update |
| `ready-to-deploy` | 2 days (GHA should have acted) |
| `in-prod` | 7 days with unchecked AC boxes |

Use `updated_at` from the API response.

### 5. Check for bug lifecycle anomalies
- `bug:normal` with no parent story link → flag: "Normal bug must be linked to a parent story"
- `bug:production` without `priority:critical` or `priority:high` → flag: "Production bug priority may be too low"
- `bug:reopened` without a comment explaining why → flag: "Reopened bug needs a reason comment"
- Any issue labelled `in-prod` that was previously `prod-verified` and then reopened → flag as: "Regression — was prod-verified"

### 6. Check for lifecycle anomalies
- Issues with `qa-verified` label that still also have `in-qa` → flag: "Duplicate label — remove in-qa"
- Issues with `ready-to-deploy` for more than 2 days → flag: "GHA should have created deploy PR — check Actions tab"
- Issues with no lifecycle label that are not Epics, test-case issues, or milestones → flag: "Unlabelled issue — needs triage"
- Any issue closed without `prod-verified` label → flag: "Closed without prod-verified — may have been closed manually"

### 7. Check prod-verification pending
For every open issue labelled `in-prod`:
- Fetch full body via `mcp0_get_issue`
- Count `- [ ]` patterns
- If unchecked boxes remain: flag "#{N} in-prod — {count} AC boxes need verification"
- If zero unchecked: flag "#{N} in-prod — all ACs ticked, waiting for prod-verified label"

### 8. Print full report

```
── SCRUM MASTER REPORT ── {date} ──────────────────────────

BOARD STATE:
  ready-for-dev    : #21, #22, #23
  in-progress      : #20
  in-qa            : #18
  qa-verified      : —
  ready-to-deploy  : #19
  in-prod          : #16, #17
  ⚠️ No label      : #5 (needs triage)

EPIC HEALTH:
  #40 Provider & API Config   : 3/13 stories closed (23%) — in-progress
  #41 Video Pipeline          : 0/13 stories closed (0%)  — not started
  #43 Infrastructure          : 0/6 stories closed (0%)   — not started

⚠️ ANOMALIES:
  #20 in-progress for 6 days — stale
  #19 ready-to-deploy for 3 days — GHA may not have triggered, check Actions
  #16 in-prod — 2 AC boxes still unchecked (7 days)
  #5 has no lifecycle label — needs triage

PROD VERIFICATION NEEDED:
  #16: 2 boxes unchecked — verify on https://dash.autoniix.com
  #17: all boxes ticked — add prod-verified label to close

SUGGESTED NEXT ACTIONS:
  1. Run /qa-agent post-dev → walk test cases for #18 (in-qa)
  2. Tick AC boxes in #16 on https://dash.autoniix.com
  3. Add prod-verified to #17 (all ACs already ticked)
  4. Check GitHub Actions tab — #19 ready-to-deploy for 3 days
  5. Triage unlabelled issue #5
```

---

## Rules
- Never change any issue label — read-only
- Never close any issue — read-only
- Never create PRs or branches — read-only
- Epics and test-case issues (`test-case` label) do NOT follow the lifecycle — do not flag them for missing lifecycle labels
- Safe to run multiple times — fully idempotent (read-only)
- If an issue appears stuck and the reason is unclear, suggest: "Comment on the issue asking for status update"
