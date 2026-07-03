---
description: Project Manager — sprint planning, milestone progress report, and velocity tracking for the Autoniix MVP
---

> **Source of Truth — LOCKED:**
> - Jira **Issue Management (IM)** project (`IM-XXX`) is the **only** active project. All sprints and tickets go here.
> - Jira **Autoniix Engineering (AE)** space is **archived** — read-only, never create sprints or tickets there.
> - GitHub **Autoniix MVP** project board is **closed** — do not reference it for sprint planning.
> - Board: https://autoniix.atlassian.net/jira/software/c/projects/IM/boards/35/backlog

# Project Manager Workflow

Use this workflow to **plan what to work on next** and **get a progress report** against the Autoniix MVP milestone.

Run it at the start of each week or sprint, or whenever you need a status overview.

---

## Modes

Pass a mode when invoking:
- `/pm-agent plan` — sprint planning: decide which issues to pull into active work
- `/pm-agent report` — status report: current progress, velocity, risk items
- `/pm-agent deploy-watch` — check production deployment health and auto-advance tickets from Ready To Deploy → In Prod
- `/pm-agent` (no arg) — run both `plan` and `report`

---

## Steps

### MODE: `plan` — Sprint Planning

0. **Create a named sprint on Jira (mandatory, do this first)**
   - Determine the sprint number by calling:
     ```
     curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
       "https://api.atlassian.com/ex/jira/73672c49-7089-4f35-adde-e3fa0d1e438f/rest/agile/1.0/board?projectKeyOrId=IM" \
       | python3 -c "import sys,json; boards=json.load(sys.stdin)['values']; print(boards[0]['id'])"
     ```
     Store the board ID. Then list existing sprints to determine the next sprint number:
     ```
     curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
       "https://api.atlassian.com/ex/jira/73672c49-7089-4f35-adde-e3fa0d1e438f/rest/agile/1.0/board/{BOARD_ID}/sprint?state=active,closed" \
       | python3 -c "import sys,json; sprints=json.load(sys.stdin).get('values',[]); print(len(sprints)+1)"   # Board ID is the IM board (35)
     ```
   - Derive the sprint theme from the dominant epic/label of issues being pulled in (e.g. "Providers Rebuild", "Pipeline Quality", "Dashboard UX")
   - Sprint name format: `Sprint {N} — {Theme} — {YYYY-MM-DD}` (e.g. `Sprint 3 — Providers Rebuild — 2026-06-12`)
   - Create the sprint:
     ```
     curl -s -X POST -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
       -H "Content-Type: application/json" \
       "https://api.atlassian.com/ex/jira/73672c49-7089-4f35-adde-e3fa0d1e438f/rest/agile/1.0/sprint" \
       -d '{"name": "Sprint {N} — {Theme} — {YYYY-MM-DD}", "originBoardId": {BOARD_ID}, "startDate": "{now}", "endDate": "{now+14days}"}'
     ```
   - Note: `JIRA_EMAIL` and `JIRA_API_TOKEN` must be set in the shell environment (from `.env`)
   - If sprint creation fails (e.g. board doesn't support sprints), note the error and proceed — do NOT block the rest of planning
   - Print: `🗓️ Created Jira sprint: Sprint {N} — {Theme} — {YYYY-MM-DD} (Board ID: {BOARD_ID})`

1. **Check for production bugs first (mandatory)**
   - Call `mcp0_list_issues` with label `bug:production` AND state `open`
   - If ANY exist: stop all other planning. Print:
     ```
     🚨 PRODUCTION BUGS ACTIVE — Sprint plan is paused.
        #{N} bug | Prod | {layer} | {description} — priority:critical
        Run /conductor hotfix to address immediately.
     ```
   - Do NOT recommend any other work until `bug:production` issues are resolved

2. **Fetch the backlog**
   - Use `mcp0_list_issues` on `saurabhrawat-gh/Autoniix` with label `ready-for-dev`, `state=open`
   - Also fetch all issues with NO lifecycle label (unlabelled — potential backlog leaks)
   - Exclude: Epics (label `epic`), test-case issues (label `test-case`)
   - Sort strictly by priority tier:
     1. `bug:normal` + `priority:critical` or `priority:high` (QA bugs not yet fixed)
     2. `feat`/`task`/`story` with `priority:critical`
     3. `feat`/`task`/`story` with `priority:high`
     4. `feat`/`task`/`story` with `priority:medium`
     5. Everything else

3. **Fetch current WIP (work in progress)**
   - Fetch all open issues with labels: `in-progress`, `in-qa`, `ready-to-deploy`, `in-prod`
   - Exclude Epics and test-case issues from WIP count
   - Count total WIP items

4. **Calculate available capacity**
   - If WIP ≥ 3 stories: flag as **over capacity** — do NOT pull in new work until WIP reduces
   - If WIP < 3 stories: recommend pulling in `(3 - WIP)` issues from the backlog

5. **Recommend sprint issues**
   - Pick the top `(3 - WIP)` issues from the sorted backlog
   - Skip any issue whose dependency is not yet `prod-verified` (check Impacted Files / "Depends on" in body)
   - For each recommended issue, show:
     - Issue number + title (note the `[Type] | [Layer] | Description` format)
     - Priority label
     - Estimated complexity: count AC checkboxes (1–3 = small, 4–7 = medium, 8+ = large)
     - Blocking dependencies: note any issue referenced as a prerequisite

5. **Print sprint plan**
   ```
   ── SPRINT PLAN ── {date} ───────────────────────────────────

   CURRENT WIP (2 stories):
     🔵 #20 5-Role Migration (in-progress)
     🔵 #18 Forgot Password (in-qa)

   RECOMMENDED NEXT (1 slot available):
     → #22 Ownership Transfer Protection (priority:high, medium complexity — 5 ACs)
        No blockers. Ready to pull in.

   FULL BACKLOG (by priority):
     priority:critical : (none)
     priority:high     : #22, #21, #25
     priority:medium   : #23, #24
     priority:low      : #26

   ACTION: Run /dev-agent to start #22.
   ```

6. **Ask for confirmation before labelling**
   - Ask the user: "Should I mark #22 as the next sprint focus? (y/n)"
   - If yes: call `mcp0_add_issue_comment` on the selected issue with "📌 Pulled into current sprint — next up for /dev-agent"

---

### MODE: `report` — Status Report

1. **Fetch milestone progress**
   - Use GitHub API to fetch milestone #1 (`Autoniix MVP`) stats: open_issues, closed_issues
   - Calculate: `closed / (open + closed) * 100` = % complete

2. **Fetch all issues grouped by lifecycle state**
   - Use `mcp0_list_issues` with `state=all`, `milestone=1`
   - Exclude Epics (`epic` label) and test-case issues (`test-case` label) from all counts
   - Group: closed (done), open by lifecycle label

3. **Calculate velocity** (stories completed recently)
   - Fetch issues closed in the last 7 days (check `closed_at` field)
   - Count: this is this week's velocity

4. **Identify risk items**
   - Issues `in-progress` with `updated_at` older than 5 days → stalled
   - Issues `in-qa` with `updated_at` older than 3 days → QA blocked
   - Issues with `priority:critical` NOT yet `qa-verified` → at-risk for launch
   - Any Epic with ALL child stories still `ready-for-dev` → epic not started, at risk
   - Any Epic with mixed story states (some done, some not started) → epic at risk of partial delivery
   - Bug issues with label `bug:production` → flag immediately regardless of priority

5. **Print status report**
   ```
   ── PM STATUS REPORT ── {date} ──────────────────────────────

   MILESTONE: Autoniix MVP
     Progress : ████████░░░░ 8/25 issues closed (32%)
     Due date : 2026-08-31 ({N} days remaining)
     Velocity : 2 stories closed this week

   PIPELINE SUMMARY:
     ✅ Done              : 8 stories
     🔵 In Progress       : 1 story  (#20)
     🔍 In QA             : 1 story  (#18)
     ⏳ QA Verified       : 0
     🚀 Ready to Deploy   : 0
     🟢 In Prod           : 2 stories (#16, #17)
     📋 Backlog           : 13 stories

   AT RISK:
     ⚠️ #20 stalled in-progress for 6 days — check with dev
     ⚠️ #16 priority:critical — in-prod, pending verification

   EPIC HEALTH:
     #12 Auth Epic       : 2/4 stories done (50%)
     #13 Workspace Epic  : 0/5 stories done (0%)
     #14 Providers Epic  : 0/2 stories done (0%)
     #15 Process Epic    : 1/1 stories done (100%) ✅

   RECOMMENDATION:
     Verify #16 on prod (type `verified #16` when ready).
     Then run `/conductor feature #22` to keep velocity up.
   ```

---

### MODE: `deploy-watch` — Production Deployment Promotion

Run this after a deploy has been triggered (or on a schedule). Checks whether production is green and automatically promotes all "Ready To Deploy" tickets to "In Prod".

1. **Check production health**
   - Hit the production health endpoint:
     ```bash
     curl -sf https://dash.autoniix.com/api/health
     ```
   - If the response is non-200 or request fails: **STOP**. Print:
     ```
     ⚠️  Production health check FAILED — not promoting any tickets.
     Response: {status_code} {body}
     Investigate before re-running deploy-watch.
     ```
   - If 200 and body contains `"status": "ok"` (or equivalent healthy signal): proceed.

2. **Fetch all Ready To Deploy tickets in Jira**
   - Call `mcp0_searchJiraIssuesUsingJql` with cloudId `73672c49-7089-4f35-adde-e3fa0d1e438f`:
     ```
     jql: project = IM AND status = "Ready To Deploy" ORDER BY updated ASC
     fields: ["summary", "status"]
     ```
   - If no tickets found: print `✅ No tickets in Ready To Deploy — nothing to promote.` and stop.

3. **Promote each ticket to In Prod**
   - For each ticket returned in step 2:
     - Call `mcp0_transitionJiraIssue` with cloudId `73672c49-7089-4f35-adde-e3fa0d1e438f`, issueIdOrKey = ticket key, transition id `6` (→ In Prod)
     - Call `mcp1_list_issues` on `saurabhrawat-gh/Autoniix` to find the matching GitHub issue via `scripts/issue_map.json` reverse-lookup
     - If GitHub issue found: call `mcp1_update_issue` to remove label `ready-to-deploy`, add label `in-prod`
   - Print one line per ticket: `✅ {KEY} → In Prod — {summary}`

4. **Print promotion summary**
   ```
   ── DEPLOY-WATCH ── {datetime} ─────────────────────
   Production health: ✅ GREEN (https://dash.autoniix.com/api/health)

   Promoted to In Prod ({N} tickets):
     ✅ IM-39  Login page
     ✅ IM-40  Register page
     ...

   ACTION: Type `verified #N` in Windsurf for each ticket after manual smoke test.
   ```

5. **Auto-close completed Epics**

   After promoting tickets in step 3, check every Epic that owns any of the just-promoted stories:

   - For each unique `sprint:*` label or Epic link found on the promoted tickets, fetch the parent Epic from Jira:
     ```
     mcp0_searchJiraIssuesUsingJql:
       jql: project = IM AND issuetype = Epic AND status != Done
       fields: ["summary", "status", "subtasks", "labels"]
     ```
   - For each open Epic, fetch all its child stories:
     ```
     mcp0_searchJiraIssuesUsingJql:
       jql: project = IM AND "Epic Link" = {EPIC_KEY} OR parent = {EPIC_KEY}
       fields: ["summary", "status"]
     ```
     *(Also check stories sharing the epic's sprint label if Epic Link is unavailable.)*
   - **If ALL child stories have status `Done`** (and the Epic itself is not already `Done`):
     - Call `mcp0_transitionJiraIssue` with transition id `51` (→ Done)
     - Find the matching GitHub Epic issue via `scripts/issue_map.json` reverse-lookup
     - Call `mcp1_update_issue` to close it (state: `closed`) and add label `epic-done`
     - Print: `✅ EPIC {KEY} auto-closed — all child stories are Done ({N} stories)`
   - **If some child stories are still open**: skip — do not close the Epic
   - **If no child stories exist** (empty Epic): skip — do not auto-close, flag as an empty Epic warning

6. **Print epic closure summary**
   ```
   EPIC AUTO-CLOSE:
     ✅ IM-1  Core 1: Auth & Platform Foundation — all 11 stories Done → Epic closed
     ⏳ IM-2  Workspace Epic — 3/5 stories done, 2 still open → not closed
   ```

---

## Rules

- **Sprint creation is mandatory at the start of every `plan` run** — always create a new named sprint on Jira before planning
- Sprint name format: `Sprint {N} — {Theme} — {YYYY-MM-DD}` — theme must reflect the dominant epic focus of the recommended issues
- Sprint duration: 2 weeks (14 days) from the planning date
- Never move issues between labels — read-only in both modes
- In `plan` mode, only add a sprint-focus comment — do NOT change lifecycle labels
- Lifecycle transitions in `plan` and `report` modes are read-only — do NOT modify labels or statuses in those modes
- `deploy-watch` mode is the **only** mode that writes Jira transitions or GitHub labels
- `deploy-watch` must NEVER promote tickets if the production health check fails — health gate is non-negotiable
- WIP limit is **3 stories maximum** in active states (`in-progress` + `in-qa` + `in-prod`)
- If WIP ≥ 3, recommend finishing existing work before starting anything new
- Epics and test-case issues are excluded from velocity and WIP counting
- An Epic is NOT done until ALL its child stories are closed
- A Story is NOT done until ALL its child tasks are closed AND it is `prod-verified`
- **When ALL child stories of an Epic are `Done`, the Epic is automatically transitioned to `Done` in `deploy-watch` mode — no manual action needed**
- Empty Epics (no child stories) are never auto-closed — flag them as a warning instead
- `bug:production` issues are always recommended first, above any backlog priority ordering
- Always recommend the highest-priority unblocked story from the backlog
