---
description: Resume CI — restore all GitHub Actions auto-triggers and lift the build freeze
---

# Resume CI Workflow

Use this when the build freeze is over and you want all GitHub Actions workflows to auto-trigger again.

Invoke with: `/resume-ci`

---

## Step 1 — Restore `build.yml`

Change the `on:` block back to:
```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:
```

## Step 2 — Restore `ci.yml`

Change the `on:` block back to:
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      reason:
        description: "Reason for manual deploy trigger"
        required: false
        default: "manual hotfix deploy"
```

## Step 3 — Restore `equivalence.yml`

Change the `on:` block back to:
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
```

## Step 4 — Restore `rust-build.yml`

Change the `on:` block back to:
```yaml
on:
  workflow_dispatch:
  push:
    branches:
      - main
    paths:
      - 'rust/**'
      - 'proto/**/*.proto'
```

## Step 5 — Restore `proto-validate.yml`

Change the `on:` block back to:
```yaml
on:
  workflow_dispatch:
  push:
    branches:
      - main
    paths:
      - 'proto/**/*.proto'
      - 'proto/buf.yaml'
      - 'proto/buf.gen.yaml'
```

## Step 6 — Restore `versions-in-sync.yml`

Change the `on:` block back to:
```yaml
on:
  push:
    branches: [main, develop]
  pull_request:
  workflow_dispatch:
```

## Step 7 — Remove build freeze banners

Remove the `🚫 BUILD FREEZE` blockquote from the top of:
- `.devin/workflows/dev-agent.md`
- `.devin/workflows/devops-agent.md`
- `.devin/workflows/conductor.md`

## Step 8 — Commit and push

```bash
git add .github/workflows/ .devin/workflows/
git commit -m "chore: restore CI auto-triggers — build freeze lifted"
git push origin develop
```

## Step 9 — Update memory

Delete or update the BUILD FREEZE memory (id: `3e949843-b8de-4560-b99c-1f4cd43ae426`) to reflect the freeze is lifted.
