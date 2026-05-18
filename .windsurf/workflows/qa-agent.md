---
description: QA Agent — read BA-produced stories, classify deliverables as bug/feature/task/hotfix/subtask, and create linked GitHub test-case issues with full happy/sad/edge checkbox suites
---

# QA Agent Workflow

Use this workflow after the BA agent has created stories (labelled `ready-for-qa`), before the dev agent picks them up.

## Steps

1. **Accept input**
   - Accept a story or epic issue number, OR process all open `ready-for-qa` issues
   - Use `mcp0_list_issues` on `saurabhrawat-gh/Autoniix` with label `ready-for-qa`, sorted by `created` asc, if no number given
   - If given an Epic: fetch all child stories listed in its body and process each one

2. **Fetch and parse the issue**
   - Use `mcp0_get_issue` to read the full body
   - Extract: Summary, Personas, Use Cases table (`UC-XX-NN` rows), Acceptance Criteria checkboxes, Impacted Files
   - Note the issue type context: is this a new capability, a defect, a migration, a security fix?

3. **Classify each deliverable**
   Determine the issue type for each acceptance criteria group or use case cluster:

   | Condition | Type | Label | Branch prefix | Commit prefix |
   |---|---|---|---|---|
   | New endpoint / screen / capability | `feature` | `feature` | `feat/` | `feat(#N):` |
   | Defect in existing shipped code | `bug` | `bug` | `fix/` | `fix(#N):` |
   | Urgent prod-impacting issue | `hotfix` | `hotfix` | `hotfix/` | `hotfix(#N):` |
   | Small isolated technical change | `task` | `task` | `chore/` | `chore(#N):` |
   | Sub-step of a task too large to be atomic | `subtask` | `subtask` | `chore/` | `chore(#N):` |

4. **Generate test cases**
   For every use case row and acceptance criteria checkbox, generate:

   **Happy Flow** (minimum 2 per story):
   - One TC per use case: actor does X with valid input → system does Y correctly
   - Include all roles that should succeed (owner, admin, etc.)

   **Sad / Error Flow** (minimum 3 per story — always include these):
   - Invalid or malformed input → proper error code + message
   - Wrong role (non-owner calls owner-only endpoint) → 403
   - Resource not found → 404
   - Duplicate entry where uniqueness is enforced → 409
   - Expired or revoked token → 401
   - Missing required field → 422

   **Edge Cases** (minimum 2 per story):
   - Plan limit boundary (at limit, over limit)
   - Empty state (no records exist)
   - Concurrent / race condition (two requests simultaneously)
   - Maximum payload or list size
   - Special characters in text inputs
   - Action on already-completed / already-cancelled resource

   **Security / Auth checks** (always add when story involves auth, tokens, or permissions):
   - No cookie + no header → 401
   - Expired JWT → 401
   - Token not in localStorage (XSS check)

5. **Create child GitHub issues**
   For each classified work item, call `mcp0_create_issue` with:
   - **Title:** `[TEST] {story_title} — {item_short_description}`
   - **Body:** use the `test-case` issue template, pre-filled with all generated TCs as checkboxes (use `TC-{story_number}-NN` IDs)
   - **Labels:** `test-case`, the item's type label (`feature` / `bug` / `task` / etc.), `ready-for-dev`
   - **Body header:** `**Parent Story:** #{story_number}` and `**Issue Type:** {type}`

6. **Comment on the parent story**
   Call `mcp0_add_issue_comment` on the story issue:
   ```
   QA review complete. Test cases created:
   - #{tc_issue_number}: {description}
   - ...
   All happy / sad / edge cases documented as checkboxes.
   Story is now ready for dev.
   ```

7. **Update parent story labels**
   Call `mcp0_update_issue` on the story:
   - Remove label: `ready-for-qa`
   - Add labels: `qa-approved`, `ready-for-dev`

8. **If processing a batch (all ready-for-qa)**
   Continue to the next `ready-for-qa` issue until the list is empty.

---

## Test Case Quality Rules
- Every permission-sensitive endpoint: test all 5 roles (owner ✓, admin ✓/✗, producer ✓/✗, editor ✓/✗, viewer ✗)
- Every DB write: test duplicate entry + missing required field
- Every auth endpoint: test expired token + replayed token (if refresh rotation involved)
- Every plan-limited feature: test at limit (success) and over limit (402)
- Every list endpoint: test empty list + list with items
- Every delete: test delete own resource (✓) + delete other's resource (403/404)

---

## Lifecycle After QA Agent Runs
```
QA agent creates test-case issue (label: test-case, ready-for-dev)
         ↓
/dev-agent picks up parent story (now labelled ready-for-dev)
         ↓
Dev implements → story label: in-progress → dev-done
         ↓
You open the test-case issue → tick checkboxes
         ↓
All checked → update story label: qa-verified
         ↓
/devops-agent deploy → in-prod → prod-verified → closed
```

---

## Rules
- Never write code during QA phase
- Never skip edge cases for auth, permissions, or plan limits
- One test-case issue per story — all TCs inside one issue as checkboxes
- If a story has >15 TCs, split into two test-case issues (happy+sad in one, edges in another)
- When you tick all boxes and move to `qa-verified`, comment on the parent story: "QA passed — all {N} test cases verified ✓"
