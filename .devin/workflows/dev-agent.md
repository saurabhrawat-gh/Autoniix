---
description: Dev Agent — pick up the oldest ready-for-dev GitHub Issue and implement it end-to-end
---

> **Source of Truth — LOCKED:**
> - Jira **Issue Management (IM)** project (`IM-XXX`) is the **only** active project. All new tickets go here.
> - Jira **Autoniix Engineering (AE)** space is **archived** — read-only, never create tickets there.
> - GitHub **Autoniix MVP** project board is **closed** — do not reference it.
> - Board: https://autoniix.atlassian.net/jira/software/c/projects/IM/boards/35/backlog

# Dev Agent Workflow

Use this workflow to implement a feature from a GitHub Issue marked `ready-for-dev`.

> **🚫 BUILD FREEZE — until 2026-07-11**
> No pushes to `main` and no deploy triggers of any kind until the freeze lifts.
> If asked to deploy or promote to `main` before 2026-07-11, STOP and reply: "Build freeze in effect until 2026-07-11. I cannot push to main or trigger a deploy."
> After 2026-07-11 the user will explicitly say "freeze lifted" or "deploy" before any main promotion happens.

> **⚠️ NO PUSH TO `main` — EVER (until the user explicitly says so)**
> Dev-agent **never** merges or pushes to `main`. All work — including hotfixes — stops at `develop`.
> The user manually runs `git checkout main && git merge --no-ff develop && git push origin main` when they are ready to trigger a build.

There are two paths depending on issue type:
- **Normal path** (`feature` / `bug` / `task`) → merges to `develop`
- **Hotfix path** (`hotfix` / `bug:production`) → merges to `develop` (same as normal path — user promotes to `main` manually)

---

## Step 0.A — Manual invocation by Jira key (takes precedence)

If the user invoked this workflow with a Jira key (e.g. `/dev-agent IM-227`, or any message containing a `IM-\d+` pattern as the explicit target):

1. **Resolve the Jira key to a GitHub issue number** via reverse-lookup in `scripts/issue_map.json`:
   ```bash
   # turbo
   python3 -c "import json; m={v:int(k) for k,v in json.load(open('scripts/issue_map.json')).items()}; print(m['IM-227'])"
   ```
2. **If no mapping found** → STOP. Report to the user: "IM-XXX has no GitHub mirror. Create the GitHub mirror issue first and update `scripts/issue_map.json` before invoking `/dev-agent`."
3. **If mapping found** → set `{N}` = resolved GH issue number, then **skip Step 0 and Step 1**. Read the GH issue body directly via `mcp1_get_issue` and jump to Step 1a (Read Research Notes).
4. **Path selection** — inspect the GH issue's labels:
   - Has `bug:production` or `hotfix` → take the **Hotfix Path** starting at H2 (note: hotfix path still targets `develop`, not `main`).
   - Otherwise → take the **Normal Path** starting at step 2.

This bypasses autopick. The user has explicitly chosen the ticket.

---

## Step 0 — Autopick: hotfixes always take priority

Only run this step if the user did NOT pass a Jira key (i.e. plain `/dev-agent` invocation).

Before anything else, check for open hotfix issues:
- Call `mcp0_list_issues` with label `bug:production` AND state `open`
- Also call `mcp0_list_issues` with label `hotfix` AND state `open`
- If ANY results exist → **immediately take the Hotfix Path** for the highest-priority one (`priority:critical` first, then `priority:high`, then oldest) — note: hotfix path targets `develop`, not `main`
- If none exist → continue to Normal Path below

---

## Normal Path (feature / bug / task)

### 1. Fetch the issue
- Use `mcp0_list_issues` on `saurabhrawat-gh/Autoniix` with label `ready-for-dev`, sorted by `created` asc, then by priority (`priority:critical` first)
- Pick the highest-priority open issue that is NOT a `hotfix` or `bug:production`
- Read the full issue body: Summary, Use Cases, Acceptance Criteria, Impacted Files, DoD
- Note the linked test-case issue number from the "Test Plan" section
- Note the issue title format: `[Area] | Description` — confirm the area before starting

### 1a. Read Research Notes
- Search the issue comments for a comment containing `## Research Notes`
- If found: read the Codebase Impact map, Dependency section, and Recommended Approach
- **Follow the recommended approach exactly** — do not deviate from it
- If NOT found: proceed (Research Team may not have run yet — follow existing patterns)

### 2. Label as in-progress

> **MANDATORY — do this BEFORE writing a single line of code or creating a branch.**

- Call `mcp0_transitionJiraIssue` with cloudId `73672c49-7089-4f35-adde-e3fa0d1e438f`, issueIdOrKey = the Jira key for this issue (look up in `scripts/issue_map.json`), transition id `4` (→ In Progress)
- Call `mcp0_update_issue`: remove `ready-for-dev`, add `in-progress`
- Call `mcp0_editJiraIssue` to assign to Dev Agent: `{"assignee": {"accountId": "712020:863fd585-7c67-4cac-86c6-8885e80502b3"}}`
- Post comment: "Starting implementation of #{issue_number}."

### 3. Pre-implementation audit
- Run `/pre-commit` on all Impacted Files listed in the issue
- Run `/safety-audit` if credentials, auth, or DB changes are involved

### 4. Create a branch from develop

| Issue Type | Branch prefix | Example |
|---|---|---|
| `feature` | `feat/` | `feat/issue-42-add-slack-webhook` |
| `bug` / `bug:normal` | `fix/` | `fix/issue-38-refresh-token-rotation` |
| `task` | `chore/` | `chore/issue-20-5role-migration` |

```bash
git checkout develop
git pull origin develop
git checkout -b {prefix}/issue-{number}-{short-slug}
```

### 5. Implement in this order
a. DB migration (if schema changes needed) — create in `scripts/migrations/`
b. Backend changes (FastAPI routes, business logic, dependencies)
c. Tests — write BEFORE or ALONGSIDE implementation, never after
d. Frontend changes (API client → page component)
e. Update `.env.example` if new env vars added

### 6. Verify acceptance criteria
- Go through every AC checkbox in the issue
- For each: run a test OR perform the manual verification step stated in the issue
- Do NOT tick any checkbox in the issue — the user ticks those during QA

### 7. Run local CI — MANDATORY before any push

Always run the script. The default mode is an **exact mirror** of `.github/workflows/build.yml` (Rust + Docker), which is the only thing CI gates on today:

```bash
# turbo
bash scripts/ci-local.sh
```

If your change also touched Python / Node / Go / Proto, add the relevant flag(s) so the broader code-quality checks run too (they don't block CI today but should still be green):

```bash
bash scripts/ci-local.sh --python   # touched src/ tests/ scripts/ (Python)
bash scripts/ci-local.sh --node     # touched dashboard/ (Next.js / TS)
bash scripts/ci-local.sh --go       # touched go/
bash scripts/ci-local.sh --proto    # touched proto/
bash scripts/ci-local.sh --full     # touched multiple stacks
```

**Required outcome before proceeding:**
- `✅  ALL CHECKS PASSED — safe to push to main` → continue to step 8 ("safe to push to main" is CI script output language; **we push to `develop` only**)
- `✅  CI MIRROR PASSED ... ⚠  optional check(s) reported issues` → fix the soft failures, re-run, do not proceed while red
- `❌  FAILED: ...` (hard fail in the CI mirror) → **STOP. Fix every failure. Re-run until fully green.**

> This is non-negotiable. **Never push to `origin/develop` without a fully-green `ci-local.sh` run.** Every failed remote build costs real money.

### 8. Run diff review
- Run `/diff-review` — verify no unrelated changes, no style drift

### 9. Commit to the branch

| Issue Type | Commit prefix |
|---|---|
| `feature` | `feat(#N):` |
| `bug` | `fix(#N):` |
| `task` | `chore(#N):` |

```bash
git add -A && git commit -m "{prefix}: {short description}"
```

### 10. Merge branch to develop locally, then delete the feature branch (no push of feature branch)
```bash
git checkout develop
git pull --ff-only origin develop
git merge --no-ff {branch-name} -m "{prefix}: merge issue-{N} into develop"
# Feature branch lifetime ends here — never push it to remote
git branch -d {branch-name}
```

**After merge, re-run local CI on develop to confirm no merge conflicts broke anything:**
```bash
# turbo
bash scripts/ci-local.sh        # CI mirror — always required
# add --python / --node / --go / --proto / --full if relevant to the merge
```
If red: fix before push. If green: proceed to step 11.

**Hard rules — non-negotiable:**
- Feature branches must NEVER be pushed to `origin` for any reason
- Feature branches must be deleted locally immediately after merging into `develop`
- If `git branch -d` refuses (unmerged), STOP and report — do not force-delete without product-owner approval
- The only branches that ever exist on `origin` are `main` and `develop`

### 11. Set issue to ready-to-deploy, update Jira, push develop

**HARD GATE — do not push to `origin/develop` unless BOTH of these are true:**
1. Step 7 (pre-merge) finished with `✅ CI MIRROR PASSED` (or `✅ ALL CHECKS PASSED` if optional flags used)
2. Step 10 (post-merge) finished with the same green outcome

If either was red at any point, you must NOT have reached this step. Go back and fix.

- Call `mcp0_update_issue` on the issue: remove `in-progress`, add `ready-to-deploy`
- Look up the Jira key for this issue via `scripts/issue_map.json`
- Call `mcp0_transitionJiraIssue` with cloudId `73672c49-7089-4f35-adde-e3fa0d1e438f`, issueIdOrKey = Jira key, transition id `5` (→ Ready To Deploy)
- Call `mcp0_add_issue_comment`:
  ```
  ✅ Implementation complete. Merged to `develop`.
  Local CI passed (scripts/ci-local.sh) before push.

  Issue is now **Ready to Deploy**.
  When you are ready to build, promote develop → main manually and deploy.

  After deploy: verify at https://dash.autoniix.com and type `verified #N` in Windsurf.
  If you find a bug, type `bug: description, issue #N` to file it automatically.
  ```
- Push develop to remote:
  ```bash
  git push origin develop
  ```

### 12. Emit HandoffPayload
```yaml
handoff:
  from_team: dev
  to_team: security
  issue: {N}
  branch: {branch_name}
  summary: "Implementation complete. Merged to develop. Awaiting manual develop→main promotion by product owner."
  changed_files:
    - {list all files modified or created}
  risk_level: {low|medium|high based on changes: auth/db/external_api = high, new endpoint = medium, test/docs = low}
  actions_pending:
    - "Security Agent scans diff for secrets and policy violations"
    - "Product owner: verify on https://dash.autoniix.com once in-prod, then type verified #{N}"
  blockers: []
```

---

## Hotfix Path (hotfix / bug:production)

Use this path ONLY for issues labelled `hotfix` or `bug:production`.

> **⚠️ Hotfix path targets `develop`, NOT `main`.** The product owner manually promotes develop → main when ready to deploy.

### H1. Fetch the hotfix issue
- Use `mcp0_list_issues` with label `hotfix` OR `bug:production`, sorted by `priority:critical` first
- Read the full issue body

### H2. Label as in-progress

> **MANDATORY — do this BEFORE writing a single line of code or creating a branch.**

- Look up the Jira key via `scripts/issue_map.json`
- Call `mcp0_transitionJiraIssue` with cloudId `73672c49-7089-4f35-adde-e3fa0d1e438f`, issueIdOrKey = Jira key, transition id `4` (→ In Progress)
- Call `mcp0_update_issue`: remove `ready-for-dev`, add `in-progress`
- Call `mcp0_editJiraIssue` to assign to Dev Agent: `{"assignee": {"accountId": "712020:863fd585-7c67-4cac-86c6-8885e80502b3"}}`

### H3. Create branch from develop
```bash
git checkout develop
git pull origin develop
git checkout -b hotfix/issue-{number}-{short-slug}
```

### H4. Implement and verify
- Same as steps 5–8 of the normal path

### H5. Commit
```bash
git add -A && git commit -m "hotfix(#N): {short description}"
```

### H6. Run local CI, then merge to develop

**GATE: Run local CI first — no second chances once merged:**
```bash
# turbo
bash scripts/ci-local.sh   # run everything — hotfixes touch critical paths
```
Wait for `✅  ALL CI CHECKS PASSED`. If red: fix first. Do NOT push a red hotfix.

```bash
git checkout develop
git pull --ff-only origin develop
git merge --no-ff hotfix/issue-{number}-{short-slug} -m "hotfix(#N): merge into develop"
git push origin develop
# Hotfix branch lifetime ends here — never leave it lingering
git branch -d hotfix/issue-{number}-{short-slug}
```

> **Do NOT merge to `main`.** The product owner will manually promote develop → main when ready.

**Hard rules — non-negotiable (same as Normal Path):**
- Hotfix branches must NEVER be pushed to `origin`
- Hotfix branches must be deleted locally immediately after merging into `develop`
- The only branches that ever exist on `origin` are `main` and `develop`

### H8. Set issue to ready-to-deploy, update Jira
- Call `mcp0_update_issue`: remove `in-progress`, add `ready-to-deploy`
- Call `mcp0_transitionJiraIssue` with cloudId `73672c49-7089-4f35-adde-e3fa0d1e438f`, issueIdOrKey = Jira key, transition id `5` (→ Ready To Deploy)
- Call `mcp0_add_issue_comment`:
  ```
  🔥 Hotfix merged to `develop`.

  Awaiting manual develop → main promotion by product owner.
  When you are ready to deploy, promote develop → main and type `verified #{N}` in Windsurf after confirming the fix.
  If you find another issue, type `bug: description, issue #{N}`.
  ```

### H9. Emit HandoffPayload
```yaml
handoff:
  from_team: dev
  to_team: security
  issue: {N}
  branch: hotfix/issue-{N}-{slug}
  summary: "Hotfix merged to develop. Awaiting manual develop→main promotion by product owner."
  changed_files:
    - {list all files modified or created}
  risk_level: high
  actions_pending:
    - "Security Agent scans hotfix diff"
    - "DevOps: smoke test on production"
    - "Product owner: type verified #{N} after confirming fix on https://dash.autoniix.com"
  blockers: []
```

---

## Rules
- Never implement without reading the full issue body
- Never skip writing tests (even for hotfixes — at minimum a regression test)
- One issue per branch — never bundle multiple issues
- **Never push to `main` — dev-agent never touches `main` under any circumstances. The product owner promotes develop → main manually when ready to build.**
- Never open a PR for individual feature/bug/task issues — merge them to `develop` locally and delete the feature branch
- **The only branches that may ever exist on `origin` are `main` and `develop`.** Feature/hotfix branches are local-only and must be deleted after merge
- **Pushing to `develop` does NOT auto-deploy — the product owner manually merges develop → main to trigger a build. Always run `bash scripts/ci-local.sh` locally before pushing to `develop`, no exceptions.**
- If the issue is ambiguous, comment on the issue and flag to the user — do NOT guess
- Role checks must use `require_role()` from `_deps.py` — never inline permission logic
- All DB changes must be in a timestamped migration file, never applied directly
- Never tick AC checkboxes in issue bodies — the `/verified` command does this automatically when the user says verified
- Always emit the HandoffPayload comment at the end of implementation (Step 12 / H9)
- When creating bug issues, always use the standard format: `bug | {QA/Prod} | {Layer} | description`
- Read Research Notes (if present) before writing a single line of code — the approach is already decided
- **Jira ↔ GitHub sync is mandatory**: When a GitHub issue is created, create a Jira mirror in the **IM** project and update `scripts/issue_map.json`. When a GitHub issue is closed, transition the Jira mirror to Done (transition id `51`). Jira cloudId: `73672c49-7089-4f35-adde-e3fa0d1e438f`, project key: `IM`. If no Jira mirror exists for a GH issue, create one in the IM project before proceeding
- **Jira IM transition IDs (confirmed):** Start Working (To Do→In Progress)=`4`, Deploy Sprint (In Progress→Ready To Deploy)=`5`, Deployed (Ready To Deploy→In Prod)=`6`, Prod Verified/Close (In Prod→Done)=`7`, Defer (→Backlog)=`3`, Prod Bug (In Prod→To Do)=`8`. cloudId: `73672c49-7089-4f35-adde-e3fa0d1e438f`
