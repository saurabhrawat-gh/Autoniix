---
description: QA Agent — four modes: (C) natural language commands (verified / bug: / help me verify), (A) pre-dev test plan generation for ready-for-qa stories, (B) post-dev local QA walk-through for in-qa issues that sets qa-verified
---

> **Source of Truth — LOCKED:**
> - Jira **Issue Management (IM)** project (`IM-XXX`) is the **only** active project. Ticket keys are always `IM-XXX`; resolve to GitHub issue numbers via `scripts/issue_map.json`.
> - Jira **Autoniix Engineering (AE)** space is **archived** — read-only, never create tickets there.
> - GitHub **Autoniix MVP** project board is **closed** — do not reference it.

# QA Agent Workflow

The QA Agent has four modes. It auto-detects which mode to run.

- **Mode C — Natural Language Commands** *(checked first)*: Handles `verified`, `bug:`, and `help me verify` commands typed by the product owner. Routes immediately — does not run Modes A, B, or D directly.
- **Mode A — Pre-dev**: Runs after BA Agent. Reads `ready-for-qa` stories, generates a test-case issue, promotes story to `ready-for-dev`.
- **Mode B — Post-dev**: Runs after Dev Agent. Reads `in-qa` issues, walks you through every test case interactively, sets `qa-verified` when all tests pass.
- **Mode D — Guided Production Verification**: Triggered by `help me verify [issues]`. Classifies every AC as code/browser/ui, runs code tests automatically, and guides the owner through browser/UI steps only.

Invoke as `/qa-agent` (auto-detect) or `/qa-agent pre-dev` / `/qa-agent post-dev` / `/qa-agent verify [issues]` to force a mode.

---

## Mode C — Natural Language Commands (checked first, always)

Before doing anything else, check if the input matches a command pattern.

### C1. `verified` command

**Triggers:** input starts with `verified` (case-insensitive)

**Delegate immediately to the `/verified` workflow.** Pass through any issue numbers provided.

Examples that trigger this:
```
verified #42
verified #21 #22 #25
verified all
```

### C2. `bug:` command

**Triggers:** input starts with `bug:` (case-insensitive)

**Delegate immediately to the `/bug` workflow.** Pass the full input string.

Examples that trigger this:
```
bug: login crashes with special chars, issue #21
bug: payment webhook not firing in production, issue #67
```

### C3. `help me verify` / `verify [issues]` command

**Triggers:** input contains `verify`, `help me verify`, or `help verify` followed by one or more issue numbers or ticket keys (e.g. `IM-276, IM-262, IM-277`).

**Run Mode D — Guided Production Verification.** Extract all issue/ticket references from the input and pass them to Mode D.

### C4. If no pattern matches

Fall through to Mode A / Mode B auto-detection below.

---

## Mode A — Pre-Dev Test Plan (ready-for-qa → ready-for-dev)

### A1. Fetch stories to process
- Use `mcp0_list_issues` with label `ready-for-qa`, `state=open`, sorted by `created` asc
- If a specific issue number is given, use that
- If given an Epic: fetch all child stories from its body

### A2. For each story — parse and classify
- Use `mcp0_get_issue` to read the full body
- Extract: Summary, Use Cases table, Acceptance Criteria checkboxes, Impacted Files
- Classify the deliverable type:

| Condition | Type | Label | Branch | Commit |
|---|---|---|---|---|
| New endpoint / screen / capability | `feature` | `feature` | `feat/` | `feat(#N):` |
| Defect in existing code (pre-prod) | `bug:normal` | `bug` | `fix/` | `fix(#N):` |
| Urgent prod-impacting defect | `bug:production` | `bug` `hotfix` | `hotfix/` | `hotfix(#N):` |
| Small isolated technical change | `task` | `task` | `chore/` | `chore(#N):` |

### A3. Generate test cases
For every use case and AC checkbox, generate:

**Happy Flow** (min 2 per story):
- One TC per use case — actor does X with valid input → system responds Y

**Sad / Error Flow** (min 3 per story — never skip):
- Invalid or malformed input → correct error code + message
- Wrong role → 403
- Resource not found → 404
- Duplicate where uniqueness enforced → 409
- Expired token → 401
- Missing required field → 422

**Edge Cases** (min 2 per story):
- Empty state (no records)
- At-limit (boundary condition)
- Concurrent access (race condition)
- Special characters in text inputs

**Security / Auth** (always when story touches auth or permissions):
- No cookie + no header → 401
- Expired JWT → 401
- All 5 role checks: owner ✓, admin ✓/✗, producer ✓/✗, editor ✓/✗, viewer ✗

### A4. Create test-case issue
Call `mcp0_create_issue` with:
- **Title:** `[TEST] #{story_number} — {story_title}`
- **Labels:** `test-case`, the deliverable type label, `ready-for-dev`
- **Body:**
  ```
  **Parent Story:** #{story_number}
  **Type:** {feature/bug/task}

  ## Test Cases

  ### Happy Path
  - [ ] TC-{N}-01: {description}
  - [ ] TC-{N}-02: {description}

  ### Sad / Error
  - [ ] TC-{N}-03: {description}
  ...

  ### Edge Cases
  - [ ] TC-{N}-0X: {description}

  ### Security
  - [ ] TC-{N}-0X: {description}
  ```

### A5. Comment on parent story and promote to ready-for-dev
- Call `mcp0_add_issue_comment` on the story:
  ```
  QA plan ready. Test-case issue: #{tc_issue_number}
  {N} test cases generated (happy + sad + edge + security).
  Story promoted to ready-for-dev — dev agent can now pick it up.
  ```
- Call `mcp0_update_issue` on the story: remove `ready-for-qa`, add `ready-for-dev`

### A6. Continue batch
Process next `ready-for-qa` issue until list is empty.

---

## Mode B — Post-Dev QA Walk-Through (in-qa → qa-verified)

This mode is run AFTER the dev agent merges to `develop` and sets `in-qa`.
You run `/qa-agent` (or `/qa-agent post-dev`) after pulling `develop` locally.

### B1. Fetch in-qa issues
- Use `mcp0_list_issues` with label `in-qa`, `state=open`, sorted by `created` asc
- For each issue, also fetch the linked test-case issue (look for `[TEST] #N` in comments or body)

### B2. For each in-qa issue — announce what to test
- Use `mcp0_get_issue` to read the full body of both the story AND its test-case issue
- Print a clear QA session header:
  ```
  ── QA SESSION: #{issue_number} ─────────────────────────────
  Story: {title}
  Test cases: #{tc_issue_number}
  Environment: local develop (git checkout develop && docker compose up)
  ─────────────────────────────────────────────────────────────
  ```

### B3. Walk through test cases one by one
For each test case checkbox in the test-case issue:
1. Print the test case clearly: what to do, what to check
2. Ask: **"Did this test PASS or FAIL?"**
3. If PASS → continue to next
4. If FAIL:
   - Ask for a brief description of what failed
   - Create a `bug:normal` child issue using the `/bug` workflow format:
     - Title: `bug | QA | {layer} | {what_failed}` (determine layer from impacted files)
     - Labels: `bug`, `bug:normal`, `ready-for-dev`, same priority as parent
     - Body: parent story link `**Parent Story:** #{N}`, test case ID, reproduction steps, expected vs actual
   - Mark the story as **BLOCKED** — do NOT set `qa-verified`
   - Post comment on story: "QA BLOCKED on TC-{N}-{id}. Bug filed: #{bug_issue_number}. Fix and re-test before promoting."
   - Stop the QA session for this story

### B4. If ALL test cases passed — set qa-verified
- Call `mcp0_update_issue` on the story: remove `in-qa`, add `qa-verified`
- Call `mcp0_add_issue_comment`:
  ```
  ✅ **QA Passed** — all {N} test cases verified on local `develop`.

  GitHub Actions will automatically:
  1. Set `ready-to-deploy`
  2. Create the develop→main PR and merge it
  3. Set `in-prod` after deploy completes

  Next step for you: verify on https://dash.autoniix.com after the deploy.
  ```

### B5. Continue to next in-qa issue
Process all `in-qa` issues until list is empty or a blocker is found.

---

## Mode D — Guided Production Verification (`help me verify`)

This mode is triggered by `help me verify [issues]`. It walks the product owner through verifying one issue at a time on https://dash.autoniix.com. Code-testable ACs are verified automatically by running tests — the owner is only asked to act for things that require a real browser or dashboard interaction.

---

### D1. Classify every AC before presenting anything

For each issue, read the full body and categorise every acceptance criterion:

| Category | Criteria | Owner action needed? |
|---|---|---|
| **code** | Race conditions, concurrent requests, advisory locks, unit-level mock behaviour, DB constraint enforcement | **No** — run pytest |
| **browser** | REST security checks (cross-tenant 4xx), token/cookie auth flows | **Yes** — DevTools `fetch()` snippet |
| **ui** | Dashboard clicks — invite flow, role assignment, settings panel, form validation | **Yes** — step-by-step UI instructions |
| **infra** | Env vars, deploy flags, Redis/DB state | **No** — run command or check logs |

**Rule: never ask the owner to manually test something that can be verified with `pytest` or a one-line command.**

---

### D2. For each issue — announce the plan

Print a table before any testing:

```
── VERIFICATION PLAN: [TICKET] / #GH ────────────────────────────────
  Title: {issue title}
  ACs: {total count}

  Code (auto):  {n} ACs → running pytest now
  Browser:      {n} ACs → DevTools fetch() steps
  UI:           {n} ACs → dashboard click steps
  Skip (N/A):   {n} ACs → not verifiable in prod without test data setup
──────────────────────────────────────────────────────────────────────
```

---

### D3. Code ACs — run automatically, do not ask the owner

1. Identify the relevant test files from the issue's "Impacted Files" section.
2. Run `python -m pytest {relevant_test_files} -v --tb=short -q`.
3. If any tests fail due to **stale mocks** (e.g. `StopAsyncIteration`, `AttributeError` on mock object):
   - Fix the mock infrastructure first (update `FakePool`, `FakeConn`, side-effect chains as needed).
   - Re-run until green.
   - Commit the mock fix with message `test: fix mock chains for [TICKET] handler refactor`.
4. Report result: `✅ {n}/{n} code ACs verified by pytest` or list failures.

---

### D4. Browser ACs — provide exact DevTools snippets

For each browser-testable AC:
- State what to open (URL, which tab)
- Provide a **copy-paste** `fetch()` snippet with placeholder values clearly marked (e.g. `YOUR_WS_ID`)
- State the **expected status code and/or response shape**
- State what the **pre-fix behaviour** would have been (so the owner can recognise a regression)

Example format:
```
[AC] Cross-workspace read returns 403
  Open: https://dash.autoniix.com → DevTools (F12) → Console
  Run:
    await fetch('/api/v2/workspace/settings?scope=workspace&scope_id=9999').then(r => r.status)
  ✅ Expected: 403
  ❌ Before fix: 200 (data leak)
```

Wait for the owner to reply with the status code before marking as passed.

---

### D5. UI ACs — provide step-by-step click instructions

For each UI-testable AC:
- Number every step
- Name the exact page/section/button
- State the expected outcome per step
- Flag the **specific step** that confirms the fix

Example format:
```
[AC] Duplicate pending invite returns error
  1. Go to Members → Invite tab
  2. Invite qa-test@example.com as Viewer → Submit → expect success
  3. Invite qa-test@example.com again → Submit
     ✅ Expected: "A pending invitation already exists" error (409)
     ❌ Before fix: second invite created silently
  4. Revoke first invite, re-invite → ✅ Expected: success (clean slate)
```

Wait for the owner to confirm the result of the key step before marking as passed.

---

### D6. After all ACs confirmed — run `/verified #N`

Once the owner confirms all browser/UI ACs and code tests are green, immediately delegate to the `/verified` workflow to tick checkboxes, transition Jira, and close the issue.

---

### D7. Continue to next issue

Process all issues one by one in the order given. Do not start the next until the previous is confirmed or explicitly skipped by the owner.

---

## Test Case Quality Rules
- Every permission-sensitive endpoint: test all 5 roles
- Every DB write: test duplicate + missing required field
- Every auth endpoint: test expired token + replayed token
- Every list endpoint: test empty list + populated list
- Every delete: test delete own resource (✓) + delete another's (403/404)
- Every plan-limited feature: test at-limit and over-limit

---

## Full Lifecycle

```
BA Agent creates stories (ready-for-qa)
         ↓
/qa-agent Mode A → creates test-case issues → story: ready-for-dev
         ↓
/dev-agent → implements → merges to develop → story: in-qa
         ↓
/qa-agent Mode B → walks test cases with you
  PASS → story: qa-verified
  FAIL → bug filed → story stays in-qa until bug fixed
         ↓
GitHub Actions: qa-verified → ready-to-deploy → develop→main PR merged → in-prod
         ↓
You verify on https://dash.autoniix.com → add prod-verified label
         ↓
GitHub Actions: all ACs checked → CLOSED
```

---

## Rules
- Never write code during QA
- Never skip edge cases for auth, permissions, or plan limits
- One test-case issue per story — all TCs inside one issue
- If story has >15 TCs: split into two issues (happy+sad in one, edge+security in another)
- Never set `qa-verified` if even one test case failed — file the bug first
- In Mode B, walk test cases in order — do not skip any
