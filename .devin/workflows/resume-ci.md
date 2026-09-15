---
description: Resume CI — restore workflow auto-triggers after a build freeze (Phase 7)
---

# Resume CI Workflow

Use this when a build freeze is over. Post-Phase 7 there are only two
workflow files, so this workflow is short.

Invoke with: `/resume-ci`.

---

## Step 1 — `ci.yml`

Ensure the `on:` block reads:

```yaml
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
  workflow_dispatch:
    inputs:
      reason:
        description: "Reason for manual trigger"
        required: false
        default: "manual"
```

## Step 2 — `promote-develop-to-main.yml`

Verify workflow_dispatch is enabled and the nightly cron `30 3 * * *` is
uncommented.

## Step 3 — `versions-in-sync.yml`

Ensure the `on:` block reads:

```yaml
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
  workflow_dispatch:
```

## Step 4 — Remove build-freeze banners

Remove any `🚫 BUILD FREEZE` blockquote from:

- `.devin/workflows/dev-agent.md`
- `.devin/workflows/devops-agent.md`
- `.devin/workflows/conductor.md`

## Step 5 — Commit + push (via harness)

```bash
git add .github/workflows/ .devin/workflows/
git commit -m "chore: restore CI auto-triggers — build freeze lifted"
make pre-deploy
git push origin develop
```

Then promote via `gh workflow run promote-develop-to-main.yml`.
