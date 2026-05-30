---
description: Dev Agent — pick up the oldest ready-for-dev GitHub Issue and implement it end-to-end
---

# Dev Agent Workflow

Use this workflow to implement a feature from a GitHub Issue marked `ready-for-dev`.

There are two paths depending on issue type:
- **Normal path** (`feature` / `bug` / `task`) → merges to `develop`
- **Hotfix path** (`hotfix` / `bug:production`) → merges directly to `main`

---

## Step 0.A — Manual invocation by Jira key (NEW — takes precedence)

If the user invoked this workflow with a Jira key (e.g. `/dev-agent AE-227`, or any message containing a `AE-\d+` pattern as the explicit target):

1. **Resolve the Jira key to a GitHub issue number** via reverse-lookup in `scripts/migration/state/issue_map.json`:
   ```bash
   python3 -c "import json; m={v:int(k) for k,v in json.load(open('scripts/migration/state/issue_map.json')).items()}; print(m['AE-227'])"
   ```
2. **If no mapping found** → STOP. Report to the user: "AE-XXX has no GitHub mirror. Create the mirror first (use `/tmp/mirror_jira_to_gh.py` as template) and update `scripts/migration/state/issue_map.json` before invoking `/dev-agent`."
3. **If mapping found** → set `{N}` = resolved GH issue number, then **skip Step 0 and Step 1**. Read the GH issue body directly via `mcp1_get_issue` and jump to Step 1a (Read Research Notes).
4. **Path selection** — inspect the GH issue's labels:
   - Has `bug:production` or `hotfix` → take the **Hotfix Path** starting at H2.
   - Otherwise → take the **Normal Path** starting at step 2.

This bypasses autopick. The user has explicitly chosen the ticket.

---

## Step 0 — Autopick: hotfixes always take priority

Only run this step if the user did NOT pass a Jira key (i.e. plain `/dev-agent` invocation).

Before anything else, check for open hotfix issues:
- Call `mcp0_list_issues` with label `bug:production` AND state `open`
- Also call `mcp0_list_issues` with label `hotfix` AND state `open`
- If ANY results exist → **immediately take the Hotfix Path** for the highest-priority one (`priority:critical` first, then `priority:high`, then oldest)
- If none exist → continue to Normal Path below

---

## Normal Path (feature / bug / task)

### 1. Fetch the issue
- Use `mcp0_list_issues` on `saurabhrawat-gh/Autoniix` with label `ready-for-dev`, sorted by `created` asc, then by priority (`priority:critical` first)
- Pick the highest-priority open issue that is NOT a `hotfix` or `bug:production`
- Read the full issue body: Summary, Use Cases, Acceptance Criteria, Impacted Files, DoD
- Note the linked test-case issue number from the "Test Plan" section
- Note the issue title format: `[Type] | [Layer] | Description` — confirm the layer before starting

### 1a. Read Research Notes
- Search the issue comments for a comment containing `## Research Notes`
- If found: read the Codebase Impact map, Dependency section, and Recommended Approach
- **Follow the recommended approach exactly** — do not deviate from it
- If NOT found: proceed (Research Team may not have run yet — follow existing patterns)

### 2. Label as in-progress
- Call `mcp0_update_issue`: remove `ready-for-dev`, add `in-progress`
- Call `mcp0_transitionJiraIssue` with cloudId `73672c49-7089-4f35-adde-e3fa0d1e438f`, issueIdOrKey = the Jira key for this issue (look up in `scripts/migration/state/issue_map.json`), transition id `21` (→ In Progress)
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

### 7. Run pre-commit checks
```bash
# turbo
ruff check src/ tests/ && pytest --tb=short -q
```

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

**Hard rules — non-negotiable:**
- Feature branches must NEVER be pushed to `origin` for any reason
- Feature branches must be deleted locally immediately after merging into `develop`
- If `git branch -d` refuses (unmerged), STOP and report — do not force-delete without product-owner approval
- The only branches that ever exist on `origin` are `main` and `develop`

### 11. Set issue to ready-to-deploy, update Jira, push develop (GHA auto-merges to main)
- Call `mcp0_update_issue` on the issue: remove `in-progress`, add `ready-to-deploy`
- Look up the Jira key for this issue via `scripts/migration/state/issue_map.json`
- Call `mcp0_transitionJiraIssue` with transition id `41` (→ Dev Done) on the Story's Jira key
- Call `mcp0_add_issue_comment`:
  ```
  ✅ Implementation complete. Merged to `develop`.

  Pushing to `develop` — GitHub Actions will automatically:
  1. Merge `develop → main`
  2. Set this issue to `in-prod` after deploy

  Once it is in production, verify at https://dash.autoniix.com and type `verified #N` in Windsurf.
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
  summary: "Implementation complete. Merged to develop. Pushed — GHA auto-merges to main."
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

Use this path ONLY for issues labelled `hotfix` or `bug:production`. These skip QA and go directly to production.

### H1. Fetch the hotfix issue
- Use `mcp0_list_issues` with label `hotfix` OR `bug:production`, sorted by `priority:critical` first
- Read the full issue body

### H2. Label as in-progress
- Call `mcp0_update_issue`: remove `ready-for-dev`, add `in-progress`
- Look up the Jira key via `scripts/migration/state/issue_map.json`
- Call `mcp0_transitionJiraIssue` with transition id `21` (→ In Progress)
- Call `mcp0_editJiraIssue` to assign to Dev Agent: `{"assignee": {"accountId": "712020:863fd585-7c67-4cac-86c6-8885e80502b3"}}`

### H3. Create branch from main
```bash
git checkout main
git pull origin main
git checkout -b hotfix/issue-{number}-{short-slug}
```

### H4. Implement and verify
- Same as steps 5–8 of the normal path

### H5. Commit
```bash
git add -A && git commit -m "hotfix(#N): {short description}"
```

### H6. Merge directly to main, then delete the hotfix branch
```bash
git checkout main
git pull --ff-only origin main
git merge --no-ff hotfix/issue-{number}-{short-slug} -m "hotfix(#N): merge into main"
git push origin main
```

### H7. Backport to develop and delete the hotfix branch
```bash
git checkout develop
git pull --ff-only origin develop
git merge --no-ff main -m "chore: backport hotfix(#N) to develop"
git push origin develop
# Hotfix branch lifetime ends here — never leave it lingering
git branch -d hotfix/issue-{number}-{short-slug}
```

**Hard rules — non-negotiable (same as Normal Path):**
- Hotfix branches must NEVER be pushed to `origin`
- Hotfix branches must be deleted locally immediately after merging into `main` AND backporting to `develop`
- The only branches that ever exist on `origin` are `main` and `develop`

### H8. Set issue to in-prod
- Call `mcp0_update_issue`: remove `in-progress`, add `in-prod`
- Call `mcp0_transitionJiraIssue` with transition id `3` (→ In Prod)
- Call `mcp0_add_issue_comment`:
  ```
  🔥 Hotfix deployed directly to `main`.

  Deployed to https://dash.autoniix.com.
  When you have verified the fix in production, type `verified #{N}` in Windsurf.
  The agent will tick all AC checkboxes and close this issue automatically.
  If you find another issue, type `bug: description, issue #{N}`.
  ```

### H9. Emit HandoffPayload
```yaml
handoff:
  from_team: dev
  to_team: security
  issue: {N}
  branch: hotfix/issue-{N}-{slug}
  summary: "Hotfix merged to main and backported to develop."
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
- Never push directly to `main` except for hotfixes
- Never open a PR for individual feature/bug/task issues — merge them to `develop` locally and delete the feature branch
- **The only branches that may ever exist on `origin` are `main` and `develop`.** Feature/hotfix branches are local-only and must be deleted after merge
- **Every push to `develop` triggers GHA `on-develop-push` which auto-merges `develop → main` and deploys to production automatically**
- If the issue is ambiguous, comment on the issue and flag to the user — do NOT guess
- Role checks must use `require_role()` from `_deps.py` — never inline permission logic
- All DB changes must be in a timestamped migration file, never applied directly
- Never tick AC checkboxes in issue bodies — the `/verified` command does this automatically when the user says verified
- Always emit the HandoffPayload comment at the end of implementation (Step 12 / H9)
- When creating bug issues, always use the standard format: `bug | {QA/Prod} | {Layer} | description`
- Read Research Notes (if present) before writing a single line of code — the approach is already decided
