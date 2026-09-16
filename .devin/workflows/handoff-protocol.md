---
description: Handoff Protocol — defines the HandoffPayload schema and Human Checkpoint template used by all agent teams to communicate with each other through the conductor.
---

> **Source of Truth — LOCKED:**
>
> - Jira **Issue Management (IM)** project (`IM-XXX`) is the **only** active project.
> - Jira **Autoniix Engineering (AE)** space is **archived** — read-only.
> - GitHub **Autoniix MVP** project board is **closed** — do not reference it.

# Handoff Protocol

This document is the reference spec for inter-agent communication in the Autoniix multi-agent system. Every agent team reads this and emits a HandoffPayload at the end of its work.

---

## HandoffPayload Schema

Every agent team emits this YAML block as their final output before the Human Checkpoint fires.

```yaml
handoff:
  from_team: dev # ba | research | dev | security | qa | pm | scrum | devops
  to_team: security # same values
  issue: 42 # GitHub issue number (or list for batch)
  branch: feat/issue-42-slack-webhook # git branch (if applicable, else omit)
  summary: "One-line: what was done"
  changed_files: # list of files created/modified (dev/security only)
    - src/api/webhooks.py
    - tests/test_webhooks.py
  risk_level: medium # low | medium | high | critical
  actions_pending: # what the next team will do
    - "Secret scan on changed files"
    - "QA walkthrough TC-42-01 through TC-42-07"
  blockers: [] # list any blockers found; empty = none
  notes: "" # extra context for next team
```

### Risk level guidelines

| Level      | When to use                                                          |
| ---------- | -------------------------------------------------------------------- |
| `low`      | Read-only changes, doc updates, test-only changes, config tweaks     |
| `medium`   | New endpoints, UI changes, DB reads added, new dependencies          |
| `high`     | Auth changes, DB writes/schema changes, external API calls, payments |
| `critical` | Security fixes, data migration, prod rollback, credentials touched   |

---

## Human Checkpoint Template

Printed at every team boundary. The product owner reads it and types one of three responses.

```
╔══════════════════════════════════════════════════════════════════╗
║  CHECKPOINT: {from_team} → {to_team}  │  Issue #{N}  │  {RISK} ║
╠══════════════════════════════════════════════════════════════════╣
║  DONE ({from_team} team):                                        ║
║    ✓ {summary line 1}                                           ║
║    ✓ {summary line 2}                                           ║
║                                                                  ║
║  NEXT ({to_team} team will):                                    ║
║    → {actions_pending[0]}                                       ║
║    → {actions_pending[1]}                                       ║
║                                                                  ║
║  BLOCKERS: {blockers or "None"}                                 ║
╚══════════════════════════════════════════════════════════════════╝
  → Type: proceed / pause / [describe a change]
```

### Response handling

| Response      | What conductor does                                                                            |
| ------------- | ---------------------------------------------------------------------------------------------- |
| `proceed`     | Delegates to the next team                                                                     |
| `pause`       | Posts state comment on GitHub issue, stops the chain, prints resume command                    |
| Anything else | Treats it as an amendment — loops back to previous team with the note, re-runs, re-checkpoints |

### Auto-proceed rule (Security team only)

- `risk_level: low` from Security team → checkpoint skipped, conductor auto-proceeds and logs "Security: LOW — auto-proceeding"
- `risk_level: medium` or higher → checkpoint always fires

---

## Session State Comment Format

The conductor posts and updates this comment on the GitHub issue throughout the session.

```
<!-- CONDUCTOR_SESSION -->
**CONDUCTOR SESSION — Issue #{N}: {title}**

| Phase | Team | Status | Time |
|---|---|---|---|
| 1 | BA | ✅ done | {timestamp} |
| 2 | Research | ✅ done | {timestamp} |
| 3 | QA Mode A | ✅ done | {timestamp} |
| 4 | Dev | 🔄 running | — |
| 5 | Security | ⏳ pending | — |
| 6 | QA Mode B | ⏳ pending | — |
| 7 | DevOps | ⏳ pending | — |

**Last human approval:** Dev phase — {timestamp}
**Resume:** `/conductor resume #{N}`
```

The conductor searches for the `<!-- CONDUCTOR_SESSION -->` marker to find and update this comment on resume.

---

## Priority Enforcement Rule (all teams must follow)

When any team scans the backlog or picks up work, the priority order is always:

```
1. bug:production  (priority:critical)  → hotfix path, immediate
2. bug:normal      (priority:high)      → normal path, after hotfixes
3. feat/task/story                      → ordered by PM sprint plan
```

No team or agent reorders this. PM Agent's sprint plan operates only within the feat/task/story tier.
