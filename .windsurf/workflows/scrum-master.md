---
description: Scrum Master — scan all open issues, execute automatic lifecycle transitions, and post a sprint board summary
---

# Scrum Master Workflow

Run this workflow at any time to advance issues through the lifecycle automatically and surface what needs human attention.

## Full Issue Lifecycle

```
ready-for-dev  →  in-progress  →  dev-done
                                     ↓  (auto)
                                   in-qa
                                     ↓  (human: QA ticks test cases)
                                 qa-verified
                                     ↓  (auto)
                              ready-to-deploy
                                     ↓  (auto: triggers deploy PR)
                                   in-prod
                                     ↓  (human: ticks all AC checkboxes)
                                prod-verified  →  CLOSED  (auto)
```

**Auto** = this workflow executes it.  
**Human** = only the user can do it.

---

## Steps

1. **Fetch the current board**
   - Use `mcp0_list_issues` on `saurabhrawat-gh/Autoniix` with `state=open`, `per_page=100`
   - Filter to actual issues only (skip anything with `pull_request` key)
   - Group by lifecycle label. Print a board summary table:

   | Status | Issues |
   |---|---|
   | `ready-for-dev` | #N title, #N title … |
   | `in-progress` | … |
   | `dev-done` | … |
   | `in-qa` | … |
   | `qa-verified` | … |
   | `ready-to-deploy` | … |
   | `in-prod` | … |
   | No lifecycle label | … |

   Issues with NO lifecycle label are flagged as **⚠️ Unlabelled**.

---

2. **Transition: `dev-done` → `in-qa`** *(automatic)*
   For every open issue labelled `dev-done` but NOT `in-qa`:
   - Call `mcp0_update_issue`: remove label `dev-done`, add label `in-qa`
   - Look for a linked test-plan issue: search the issue body for `[TEST]` issue reference or `#3N` pattern in a "Test Plan" section
   - Call `mcp0_add_issue_comment`:
     ```
     🔍 **QA Phase Started**

     This story is ready for testing. All dev work is merged to `develop`.

     **Test plan:** #{test_plan_issue} ← open this and tick each checkbox as you verify

     **How to test locally:**
     1. `git checkout develop && git pull`
     2. `docker compose build dashboard-bff dashboard-ui && docker compose up -d --force-recreate dashboard-bff dashboard-ui`
     3. Open http://localhost:3000 and follow the test cases in #{test_plan_issue}

     Once all test cases in #{test_plan_issue} are ticked ✅, add the `qa-verified` label to THIS issue.
     ```
   - Log: `✅ #N dev-done → in-qa`

---

3. **Transition: `qa-verified` → `ready-to-deploy`** *(automatic)*
   For every open issue labelled `qa-verified` but NOT `ready-to-deploy`:
   - Call `mcp0_update_issue`: remove label `qa-verified`, add label `ready-to-deploy`
   - Call `mcp0_add_issue_comment`:
     ```
     🚀 **Ready to Deploy**

     QA has signed off on `develop`. This story is queued for the next production deploy.

     Next step: merge the open `develop → main` PR (or run `/devops-agent` to open one).
     After the deploy, this issue will move to `in-prod` automatically.
     ```
   - Log: `✅ #N qa-verified → ready-to-deploy`

---

4. **Transition: `ready-to-deploy` → `in-prod`** *(automatic — checks for merged deploy PR)*
   For every open issue labelled `ready-to-deploy`:
   a. Call `mcp0_list_pull_requests` with `base=main`, `state=closed` — look for a PR merged in the last 24h whose head was `develop`
   b. If a recent merged PR exists:
      - Call `mcp0_update_issue`: remove label `ready-to-deploy`, add label `in-prod`
      - Call `mcp0_add_issue_comment`:
        ```
        🟢 **In Production**

        Deployed to https://dash.autoniix.com via PR #{pr_number}.

        Please verify ALL acceptance criteria checkboxes in this issue on production.
        When every box is ticked ✅, the scrum master will automatically close this issue.
        ```
      - Log: `✅ #N ready-to-deploy → in-prod`
   c. If NO recent merged PR:
      - Check if a `develop → main` PR is already open via `mcp0_list_pull_requests` with `base=main`, `state=open`, `head=saurabhrawat-gh:develop`
      - If no open PR: call `mcp0_create_pull_request`:
        - title: `Release: Autoniix MVP — Sprint deploy`
        - head: `develop`, base: `main`
        - body: list all `ready-to-deploy` issues with `Closes #N` lines
      - Log: `⏳ #N ready-to-deploy — deploy PR opened/exists, awaiting merge`

---

5. **Transition: `in-prod` → `prod-verified` → CLOSED** *(automatic — checks AC checkboxes)*
   For every open issue labelled `in-prod`:
   a. Use `mcp0_get_issue` to fetch the full issue body
   b. Count unchecked boxes: look for `- [ ]` patterns in the body
   c. If **zero unchecked boxes** (all `- [x]`):
      - Call `mcp0_update_issue`: add label `prod-verified`, `state=closed`
      - Call `mcp0_add_issue_comment`:
        ```
        ✅ **Prod Verified — Issue Closed**

        All acceptance criteria have been ticked. This story is complete in production.
        Closed automatically by `/scrum-master`.
        ```
      - Log: `✅ #N prod-verified → CLOSED`
   d. If unchecked boxes remain:
      - Count them and post a reminder (only if no reminder was posted in the last 24h — check recent comments)
      - Call `mcp0_add_issue_comment`:
        ```
        ⏳ **Prod Verification Pending**

        This story is live on https://dash.autoniix.com but {N} acceptance criteria checkboxes are still unticked.
        Please verify on production and tick each checkbox in the issue body.
        Once all are checked, this issue will close automatically on the next `/scrum-master` run.
        ```
      - Log: `⏳ #N in-prod — {N} checkboxes remaining`

---

6. **Check for stale issues** *(informational — no auto-transition)*
   Flag any issue that has been stuck in the same status for too long:
   - `in-progress` for more than **5 days** since last update → ⚠️ stale
   - `in-qa` for more than **3 days** since last update → ⚠️ stale  
   - `ready-to-deploy` for more than **2 days** → ⚠️ stale (deploy is blocked)
   - `in-prod` for more than **7 days** with unchecked boxes → ⚠️ prod verification overdue

   Use `updated_at` from the issue API response to calculate staleness.
   Print a **⚠️ Blockers** section at the end of the report with any stale issues.

---

7. **Final report**
   Print a clean sprint board summary showing:
   - How many issues were automatically transitioned (and to which state)
   - Current board state (re-fetch and re-group after all transitions)
   - Any blockers or stale issues
   - Suggested next human actions (e.g., "QA needed on #18, #19")

   Format:
   ```
   ── SCRUM MASTER REPORT ── {date} ──────────────────────────

   TRANSITIONS EXECUTED:
     ✅ #18 dev-done → in-qa
     ✅ #19 qa-verified → ready-to-deploy
     ⏳ #16 in-prod — 2 checkboxes remaining

   CURRENT BOARD:
     ready-for-dev    : #21, #22, #23
     in-progress      : #20
     in-qa            : #18
     qa-verified      : —
     ready-to-deploy  : #19
     in-prod          : #16, #17
     prod-verified    : —

   ⚠️ BLOCKERS:
     #20 in-progress for 6 days (stale — check with dev)
     #16 in-prod for 8 days — 2 unchecked AC boxes

   NEXT ACTIONS FOR YOU:
     → Tick test cases in #33 to move #18 to qa-verified
     → Tick AC checkboxes in #16 and #17 on https://dash.autoniix.com
   ```

---

## Rules

- Never transition `in-qa → qa-verified` — only the user/QA can do this (by ticking test case checkboxes)
- Never transition `in-progress → dev-done` — only the dev agent does this after implementation
- Never close an issue unless ALL `- [ ]` boxes are gone (all ticked `- [x]`)
- Never create a deploy PR if one is already open — check first
- If an issue has BOTH `dev-done` and `in-qa` labels, remove `dev-done` (it's redundant)
- Epics (#12, #13, #14, #15) do NOT follow this lifecycle — skip them in all transitions
- Test-plan issues (`test-plan` label) do NOT follow this lifecycle — skip them too
- Run this workflow at any time — it is safe to run multiple times (idempotent)
