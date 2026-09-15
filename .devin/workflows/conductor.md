---
description: Conductor — top-level orchestrator that routes work between all agent teams, enforces human checkpoints at every team boundary, and maintains resumable session state on GitHub issues.
---

> **🚫 BUILD FREEZE — until 2026-07-11**
> No deploys, no pushes to `main`, no PR merges to `main` of any kind until the freeze lifts.
> If asked to deploy or promote to `main` before 2026-07-11, STOP and reply: "Build freeze in effect until 2026-07-11. I cannot deploy or push to main."
> After 2026-07-11 the user will explicitly say "freeze lifted" or "deploy" before any main promotion.

> **Source of Truth — LOCKED:**
>
> - Jira **Issue Management (IM)** project (`IM-XXX`) is the **only** active project. When the user says "pick up IM-XXX", resolve it from the IM board.
> - Jira **Autoniix Engineering (AE)** space is **archived** — read-only, never route work there.
> - GitHub **Autoniix MVP** project board is **closed** — do not reference it.
> - Board: https://autoniix.atlassian.net/jira/software/c/projects/IM/boards/35/backlog

# /conductor — Multi-Agent Orchestrator

The conductor is the single entry point for all development work on Autoniix. It routes between teams, enforces checkpoints, and resumes sessions that were paused.

**Usage:**

```
/conductor feature #N          — run full feature pipeline for an existing issue
/conductor feature             — pick the highest-priority ready-for-dev issue
/conductor new feature         — start from BA (no issue yet)
/conductor hotfix              — pick up highest-priority bug:production issue
/conductor sprint              — run board scan + sprint planning
/conductor incident            — diagnose and fix a production problem
/conductor audit               — run a full security audit
/conductor resume #N           — resume a paused session for issue #N
```

---

## Pre-flight: Always Check Hotfixes First

Before running any path, call `mcp0_list_issues` with label `bug:production` AND state `open`.

- If any exist → **immediately route to Hotfix Path**, do not start any other path.
- If none exist → proceed with the requested path.

---

## Path 1 — Feature Path

Use for: `/conductor feature #N`, `/conductor feature`, `/conductor new feature`

```
Step 1:  BA Team         (only if no issue exists yet, or if /conductor new feature)
         → Human Checkpoint
Step 2:  Research Team   (codebase impact + approach)
         → Human Checkpoint
Step 3:  Dev Team        (implement + push to develop → issue set to ready-to-deploy)
         → Human Checkpoint (review diff before merge)
Step 4:  Security Team   (scan diff)
         → Human Checkpoint if risk MEDIUM+; auto-proceed if LOW
Step 5:  DevOps Team     (deploy monitoring + smoke test)
         → Human Checkpoint: "Verify on prod — type verified #N when done"
```

### Feature Path — Detailed Steps

**Step 1: BA Team** (skip if issue already exists with full spec)

- Invoke `/ba-agent` workflow
- BA Lead asks product owner questions, presents options, owner chooses
- Issue Architect files Epic→Story→Task with correct title format
- Emit HandoffPayload: `from_team: ba, to_team: research`
- Print checkpoint → wait for "proceed"

**Step 2: Research Team**

- Invoke `/research-agent` workflow
- Research Lead runs Codebase Analyst + Dep Auditor + Architecture Advisor
- Posts `research_notes` comment on issue
- Emit HandoffPayload: `from_team: research, to_team: dev`
- Print checkpoint → wait for "proceed"

**Step 3: Dev Team**

- Invoke `/dev-agent` for the specific issue
- Dev Lead reads Research notes before coding
- Backend Dev + Frontend Dev + Test Writer run in sequence
- Merges to develop, pushes → issue set to `ready-to-deploy` (GitHub) + **Ready to Deploy** (Jira)
- Emit HandoffPayload: `from_team: dev, to_team: security`
- Print checkpoint (show diff summary) → wait for "proceed"

**Step 4: Security Team**

- Invoke `/security-agent` workflow
- Runs Secret Scanner + Dep Scanner + Policy Enforcer
- Posts security report as issue comment
- Emit HandoffPayload: `from_team: security, to_team: devops`
- If risk LOW → auto-proceed (log it, skip checkpoint)
- If risk MEDIUM+ → print checkpoint → wait for "proceed"

**Step 5: DevOps Team**

- Invoke `/devops-agent deploy` (monitor mode)
- Checks GHA deploy run status
- Runs smoke tests
- On success: transitions all `ready-to-deploy` issues → `in-prod` (GitHub) **and** Jira → In Prod (transition id:41)
- Emit HandoffPayload: `from_team: devops, to_team: human`
- Print checkpoint: "Deploy complete. Verify at https://dash.autoniix.com — then type `verified #N`."

---

## Path 2 — Hotfix Path

Use for: `/conductor hotfix`, or when `bug:production` issues exist (auto-detected in pre-flight)

```
Step 1:  QA Team         (if not already filed: file bug:production issue)
         → Human Checkpoint
Step 2:  Dev Team        (hotfix branch → develop → product owner promotes to main)
         → Human Checkpoint
Step 3:  Security Team   (scan diff)
         → Human Checkpoint
Step 4:  DevOps Team     (smoke test + verify)
         → Human Checkpoint: "Verify on prod — type verified #N when done"
```

### Hotfix Path — Detailed Steps

**Step 1: Bug Filing** (if no issue exists yet)

- QA Team creates the issue via `/bug` workflow
- Labels: `bug`, `bug:production`, `hotfix`, `priority:critical`, `ready-for-dev`
- Print checkpoint → wait for "proceed"

**Step 2: Dev Team — Hotfix**

- Invoke `/dev-agent` (hotfix path — branch from develop, merge to develop)
- Dev Lead reads Research notes (Research Team does a quick pass first)
- Merges to develop, sets `ready-to-deploy`. Product owner manually promotes develop→main when ready.
- Emit HandoffPayload: `from_team: dev, to_team: security, risk_level: high`
- Print checkpoint → wait for "proceed"

**Step 3: Security Team**

- Always checkpoints for hotfixes regardless of risk level
- Print checkpoint → wait for "proceed"

**Step 4: DevOps**

- Smoke test
- Print: "Hotfix deployed. Verify on https://dash.autoniix.com — type `verified #N` when confirmed."

---

## Path 3 — Sprint Path

Use for: `/conductor sprint`

```
Step 1:  PM Team         (sprint plan + velocity report)
         → Human Checkpoint before any priority changes
Step 2:  (optional) Route to Feature Path for top ready-for-dev issues
```

---

## Path 4 — Incident Path

Use for: `/conductor incident`

```
Step 1:  DevOps Team     (diagnose what is down → restart → rollback if needed)
         → Human Checkpoint before any production action
```

---

## Path 5 — Audit Path

Use for: `/conductor audit`

```
Step 1:  Security Team   (full audit: secrets + deps + cert + VPS metrics)
         → Human Checkpoint for HIGH+ findings
         → Files GitHub issues for each finding automatically
```

---

## Resume Logic

Use for: `/conductor resume #N`

1. Call `mcp0_list_issue_comments` on issue #N
2. Find the comment with `<!-- CONDUCTOR_SESSION -->` marker
3. Parse the state table to find the last `✅ done` phase
4. Identify the next `⏳ pending` phase
5. Print: "Resuming session for #N. Last completed: {phase}. Next: {next_phase}."
6. Invoke the next team's workflow and continue from there

---

## Session State Management

At the START of each path, post the initial state comment:

- Call `mcp0_add_issue_comment` with the session state table (see handoff-protocol.md format)
- Include `<!-- CONDUCTOR_SESSION -->` marker so it can be found on resume

After each phase completes, UPDATE the state comment:

- Find the existing `<!-- CONDUCTOR_SESSION -->` comment
- Update the phase row from `⏳ pending` to `✅ done` with timestamp

---

## Checkpoint Protocol

Reference: see `handoff-protocol.md` for the full template.

The conductor always:

1. Reads the HandoffPayload from the completing team
2. Formats and prints the Human Checkpoint block
3. Waits for response
4. Routes based on response:
   - `proceed` → invoke next team
   - `pause` → update state comment → print resume command → stop
   - anything else → pass as amendment to previous team → re-run → re-checkpoint

---

## Manual Issues Respect Rule

If the product owner creates a GitHub issue manually (any format, any labels):

- If it has `bug:production` → treat as hotfix, pick up immediately in pre-flight
- If it has `bug:normal` or `ready-for-dev` → it enters the queue respecting priority order
- If it has NO lifecycle label → conductor asks product owner once: "Route #N to dev queue?" → on yes, adds `ready-for-dev`

The conductor never silently ignores a manually created issue.

---

## Rules

- Pre-flight hotfix check runs EVERY time — no exceptions
- Checkpoints are non-optional except Security Team LOW-risk auto-proceed
- No agent team skips a phase; no agent team changes scope beyond its role
- Vision protection: agents implement what the spec says; they never decide product direction
- Issue label transitions are always done by agents — the product owner never needs to touch labels
- Session state is always written to GitHub so sessions survive IDE restarts
