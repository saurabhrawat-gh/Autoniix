---
description: Dev Agent — pick up the oldest ready-for-dev GitHub Issue and implement it end-to-end
---

# Dev Agent Workflow

Use this workflow to implement a feature from a GitHub Issue that has been BA-approved and marked `ready-for-dev`.

## Steps

1. **Fetch the issue**
   - Use `mcp0_list_issues` on `saurabhrawat-gh/Autoniix` with label `ready-for-dev`, sorted by `created` asc
   - Pick the oldest open issue
   - Read the full issue body: Summary, Use Cases, Acceptance Criteria, Impacted Files, DoD
   - Note the issue type label: `feature` | `bug` | `hotfix` | `task` | `subtask`
   - Note the linked test-case issue (from parent story's QA Test Cases section)

2. **Label as in-progress**
   - Remove `ready-for-dev` label, add `in-progress` label on the issue

3. **Pre-implementation audit**
   - Run `/pre-commit` workflow on all Impacted Files listed in the issue
   - Run `/safety-audit` if credentials, auth, or DB changes are involved

4. **Create a branch — name based on issue type**
   | Issue Type | Branch prefix | Example |
   |---|---|---|
   | `feature` | `feat/` | `feat/issue-42-add-slack-webhook` |
   | `bug` | `fix/` | `fix/issue-38-refresh-token-rotation` |
   | `hotfix` | `hotfix/` | `hotfix/issue-55-prod-login-broken` |
   | `task` / `subtask` | `chore/` | `chore/issue-20-5role-migration` |

   ```bash
   git checkout -b {prefix}/issue-{number}-{short-slug}
   ```

5. **Implement in this order**
   a. DB migration (if schema changes needed) — create in `scripts/migrations/`
   b. Backend changes (FastAPI routes, business logic, dependencies)
   c. Tests (write tests BEFORE or ALONGSIDE implementation, not after)
   d. Frontend changes (API client → page component)
   e. Update `.env.example` if new env vars added

6. **Verify acceptance criteria**
   - Go through every acceptance criteria checkbox in the issue
   - For each: either run a test, or perform the manual verification step stated in the issue

7. **Run pre-commit checks**
   ```bash
   # turbo
   ruff check src/ tests/ && pytest --tb=short -q
   ```

8. **Run diff review**
   - Run `/diff-review` workflow — verify no unrelated changes, no style drift

9. **Commit and push — prefix based on issue type**
   | Issue Type | Commit prefix |
   |---|---|
   | `feature` | `feat(#N):` |
   | `bug` | `fix(#N):` |
   | `hotfix` | `hotfix(#N):` |
   | `task` / `subtask` | `chore(#N):` |

   ```bash
   git add -A && git commit -m "{prefix}: {short description}"
   git push origin {branch-name}
   ```

10. **Open a Pull Request**
    - Title: `{prefix}: {story title}` (e.g. `fix(#38): session refresh token rotation`)
    - Body: `Closes #{issue_number}\n\nTest plan: #{test_case_issue}\n\n## Changes\n- ...\n\n## Testing\n- ...'`
    - Label PR: `in-review`

11. **Update issue labels**
    - Remove `in-progress`, add `dev-done`
    - Post a comment: "PR opened: #{pr_number}. Test cases in #{test_case_issue} — ready for QA."

## Rules
- Never implement without reading the full issue (use cases + acceptance criteria)
- Never skip writing tests
- One story per branch/PR — do not bundle multiple stories
- If the issue is ambiguous or contradicts existing code, comment on the issue and flag to the user — do NOT guess
- Role checks must use `require_role()` from `_deps.py` — never inline permission logic
- All DB changes must be in a timestamped migration file, never directly applied
