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

2. **Label as in-dev**
   - Remove `ready-for-dev` label, add `in-dev` label on the issue

3. **Pre-implementation audit**
   - Run `/pre-commit` workflow on all Impacted Files listed in the issue
   - Run `/safety-audit` if credentials, auth, or DB changes are involved

4. **Create a feature branch**
   ```bash
   git checkout -b feature/issue-{number}-{short-slug}
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

9. **Commit and push**
   ```bash
   git add -A && git commit -m "feat(#{issue_number}): {short description}"
   git push origin feature/issue-{number}-{short-slug}
   ```

10. **Open a Pull Request**
    - Title: `feat(#{issue_number}): {story title}`
    - Body: `Closes #{issue_number}\n\n## Changes\n- ...\n\n## Testing\n- ...'`
    - Label PR: `in-review`

11. **Update issue labels**
    - Remove `in-dev`, add `in-review`
    - Post a comment: "PR opened: #{pr_number}"

## Rules
- Never implement without reading the full issue (use cases + acceptance criteria)
- Never skip writing tests
- One story per branch/PR — do not bundle multiple stories
- If the issue is ambiguous or contradicts existing code, comment on the issue and flag to the user — do NOT guess
- Role checks must use `require_role()` from `_deps.py` — never inline permission logic
- All DB changes must be in a timestamped migration file, never directly applied
