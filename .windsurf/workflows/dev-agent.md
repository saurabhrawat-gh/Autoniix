---
description: Dev Agent — pick up the oldest ready-for-dev GitHub Issue and implement it end-to-end
---

# Dev Agent Workflow

Use this workflow to implement a feature from a GitHub Issue marked `ready-for-dev`.

There are two paths depending on issue type:
- **Normal path** (`feature` / `bug` / `task`) → merges to `develop`
- **Hotfix path** (`hotfix` / `bug:production`) → merges directly to `main`

---

## Normal Path (feature / bug / task)

### 1. Fetch the issue
- Use `mcp0_list_issues` on `saurabhrawat-gh/Autoniix` with label `ready-for-dev`, sorted by `created` asc
- Pick the oldest open issue that is NOT a `hotfix` or `bug:production`
- Read the full issue body: Summary, Use Cases, Acceptance Criteria, Impacted Files, DoD
- Note the linked test-case issue number from the "Test Plan" section

### 2. Label as in-progress
- Call `mcp0_update_issue`: remove `ready-for-dev`, add `in-progress`
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

### 10. Merge branch to develop locally (no PR)
```bash
git checkout develop
git merge --no-ff {branch-name} -m "{prefix}: merge issue-{N} into develop"
```

### 11. Set issue to in-qa and push develop
- Call `mcp0_update_issue` on the issue: remove `in-progress`, add `in-qa`
- Call `mcp0_add_issue_comment`:
  ```
  ✅ Implementation complete. Merged to `develop`.

  **Ready for local QA testing.**

  How to test:
  1. `git checkout develop && git pull`
  2. `docker compose build && docker compose up -d`
  3. Follow the test cases in #{test_case_issue}

  Once all tests pass, run `/qa-agent` to confirm and promote to deploy queue.
  ```
- Push develop to remote:
  ```bash
  git push origin develop
  ```

---

## Hotfix Path (hotfix / bug:production)

Use this path ONLY for issues labelled `hotfix` or `bug:production`. These skip QA and go directly to production.

### H1. Fetch the hotfix issue
- Use `mcp0_list_issues` with label `hotfix` OR `bug:production`, sorted by `priority:critical` first
- Read the full issue body

### H2. Label as in-progress
- Call `mcp0_update_issue`: remove `ready-for-dev`, add `in-progress`

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

### H6. Merge directly to main
```bash
git checkout main
git merge --no-ff hotfix/issue-{number}-{short-slug} -m "hotfix(#N): merge into main"
git push origin main
```

### H7. Backport to develop
```bash
git checkout develop
git merge --no-ff main -m "chore: backport hotfix(#N) to develop"
git push origin develop
```

### H8. Set issue to in-prod
- Call `mcp0_update_issue`: remove `in-progress`, add `in-prod`
- Call `mcp0_add_issue_comment`:
  ```
  🔥 Hotfix deployed directly to `main`.

  Deployed to https://dash.autoniix.com.
  Please verify the fix in production and tick all AC checkboxes.
  Once all boxes are checked, add `prod-verified` label to close this issue.
  ```

---

## Rules
- Never implement without reading the full issue body
- Never skip writing tests (even for hotfixes — at minimum a regression test)
- One issue per branch — never bundle multiple issues
- Never push directly to `main` except for hotfixes
- Never open a PR for normal issues — merge to develop locally
- If the issue is ambiguous, comment on the issue and flag to the user — do NOT guess
- Role checks must use `require_role()` from `_deps.py` — never inline permission logic
- All DB changes must be in a timestamped migration file, never applied directly
- Never tick AC checkboxes in issue bodies — that is the user's job during QA
