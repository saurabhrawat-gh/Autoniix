---
description: Bug command — create a correctly formatted, labelled, and prioritised bug issue from a one-line natural language description. Detects QA vs production context automatically from the referenced parent issue.
---

# /bug — Bug Filing Command

Use this workflow whenever you find a bug during local testing or production verification.

**Usage:**
```
bug: {description}, issue #N
```

**Examples:**
```
bug: login page crashes when email has special chars, issue #21
bug: payment webhook not firing in production, issue #67
bug: video render hangs on empty script field, issue #54
```

The workflow detects context automatically from issue #N's current label:
- Issue #N is `in-qa` → creates a **QA bug** (`bug:normal`, normal queue)
- Issue #N is `in-prod` → creates a **production bug** (`bug:production`, hotfix — highest priority)

---

## Step 1 — Parse the input

Extract:
- `description` — the text before ", issue #"
- `parent_number` — the issue number after "issue #"

If either is missing, print:
```
⚠️  Could not parse. Expected format: bug: {description}, issue #N
    Example: bug: login crashes with special chars, issue #21
```
And stop.

---

## Step 2 — Fetch the parent issue

Call `mcp0_get_issue` for `parent_number`.

Read:
- `title` — to understand the domain
- `labels` — to determine context (QA vs prod)
- `body` — to extract any "Layer" hints (Impacted Files section, API routes, etc.)

---

## Step 3 — Determine bug context and layer

### Context (from parent labels)

| Parent has label | Bug context | Bug type label | Priority | Branch |
|---|---|---|---|---|
| `in-qa` | QA bug — found during local testing | `bug:normal` | Same as parent (default `priority:high`) | `fix/` → `develop` |
| `in-prod` | Prod bug — found in production | `bug:production` + `hotfix` | `priority:critical` | `hotfix/` → `main` |
| Neither | Ambiguous — ask once | — | — | — |

If ambiguous: ask "Is this a QA bug (found locally) or production bug (found on dash.autoniix.com)?" — take the answer and proceed.

### Layer (from description + parent body)

Determine the most appropriate layer from these options:

| Layer | When to use |
|---|---|
| `UI` | Frontend component, page, button, form, visual rendering |
| `Gateway` | API route, auth middleware, request validation, CORS, rate limit |
| `Service` | Backend business logic, worker, Temporal activity, provider call |
| `DB` | Database query, migration, data integrity, ORM |
| `Auth` | Login, logout, token, session, role check, permission |
| `Worker` | Temporal workflow, background job, queue, scheduler |
| `Infra` | Docker, Caddy, DNS, environment variable, deployment |
| `Test` | Test itself is broken (not the feature) |

If unclear from description, pick the closest one and note it in the issue body.

---

## Step 4 — Build the issue title

**Format:** `{Area} | {description}`

> The bug type (QA/Production) is conveyed by the `bug:normal` / `bug:production` label — do not add it to the title.

| Area | Maps from |
|---|---|
| `Gateway` | auth, routing, Rust gateway, API gateway |
| `Dashboard` | UI, frontend, Next.js |
| `Service` | Python backend, DB, API service |
| `Worker` | Temporal, background jobs |
| `Infra` | Docker, CI/CD, infrastructure |

**Examples:**
```
Gateway | OAuth token refresh fails on expired session
Service | Video render hangs on empty script field
Dashboard | Login page crashes with special chars in email
```

---

## Step 5 — Build the issue body

```markdown
**Bug Type:** {QA / Production}
**Parent Story:** #{parent_number} — {parent_title}
**Layer:** {layer}
**Priority:** {priority}

## Description

{description from user's input — expand if possible based on parent issue context}

## Steps to Reproduce

1. {infer from parent issue context or leave as placeholder}
2. {add step}
3. Observe: {expected vs actual}

## Expected Behaviour

{what should happen}

## Actual Behaviour

{what is happening — from the user's description}

## Environment

- Branch: {develop for QA bugs / main for prod bugs}
- URL: {https://dash.autoniix.com for prod bugs / local docker for QA bugs}

## Acceptance Criteria

- [ ] Bug is reproduced and root cause identified
- [ ] Fix implemented and unit test added
- [ ] No regression on parent story #{parent_number}
- [ ] {QA: tested on develop / Prod: tested on https://dash.autoniix.com}
```

---

## Step 6 — Set labels

**QA bug (`bug:normal`):**
- `bug`
- `bug:normal`
- `priority:high` (or same as parent if parent has higher/lower)
- `ready-for-dev`
- The same type label as parent: `feature` / `task` as appropriate

**Prod bug (`bug:production`):**
- `bug`
- `bug:production`
- `hotfix`
- `priority:critical`
- `ready-for-dev`

---

## Step 7 — Create the issue

Call `mcp0_create_issue`:
- `owner`: saurabhrawat-gh
- `repo`: Autoniix
- `title`: the formatted title from Step 4
- `body`: the body from Step 5
- `labels`: the label set from Step 6

---

## Step 8 — Comment on the parent issue

Call `mcp0_add_issue_comment` on `parent_number`:

**For QA bug:**
```
🐛 **Bug filed during QA** → #{new_issue_number}

Issue: bug | QA | {Layer} | {description}
Priority: {priority}

This story stays `in-qa` until the bug is fixed and re-tested.
Dev Agent will pick up #{new_issue_number} after any active hotfixes.
```

**For prod bug:**
```
🔥 **Production bug filed** → #{new_issue_number}

Issue: bug | Prod | {Layer} | {description}
Priority: priority:critical (hotfix)

Dev Agent will pick up #{new_issue_number} immediately — hotfix path.
```

---

## Step 9 — Print confirmation

```
── BUG FILED ─────────────────────────────────────────────────
  #{new_issue_number}: bug | {Env} | {Layer} | {description}
  Type:     {QA bug / Production bug}
  Priority: {priority}
  Parent:   #{parent_number}
  Branch:   {fix/issue-{N}-{slug} → develop / hotfix/issue-{N}-{slug} → main}

  {For prod bugs}: Dev Agent will pick this up as the next hotfix.
  {For QA bugs}:   Dev Agent will queue this after active hotfixes.
──────────────────────────────────────────────────────────────
```

---

## Rules

- Never create a `bug:production` issue for something found only locally — check parent label.
- Never create a `bug:normal` issue for something found in production — check parent label.
- Always link the new bug to its parent story in the body.
- Always set `ready-for-dev` so Dev Agent can pick it up automatically.
- `priority:critical` is mandatory for all prod bugs — never lower it.
- If the user does not provide an issue number, ask once: "Which issue were you testing when you found this?"
- Never file the same bug twice — check if an open issue already describes the same symptom before creating.
