---
description: Pre-deploy verification — run every CI job locally, confirm green, open promotion PR
---

# Pre-Deploy Workflow (Phase 7 harness)

**One command gives you a 100% local guarantee before touching main.**

`make pre-deploy` runs the full dockerized CI mirror. On success it writes a
sentinel file that `.husky/pre-push` requires for pushes to `develop`. See
`docs/architecture/adr-005-harness-and-parity.md` and
`docs/architecture/adr-006-branch-and-deploy-policy.md`.

---

## Steps

### 1. Confirm you are on develop with a clean tree

```bash
# turbo
git checkout develop && git status
```

Must be `nothing to commit, working tree clean`. Commit or stash first.

### 2. Run the full dockerized mirror

```bash
make pre-deploy
```

Behind the scenes: `bash scripts/ci-local.sh --full --docker`, which runs
every job in `.github/workflows/ci.yml` inside pinned `ubuntu:24.04`. Each
function in `ci-local.sh` maps 1:1 to a CI job:

| CI job                     | Local function     |
| -------------------------- | ------------------ |
| python-lint-and-tests      | job_python         |
| ts-typecheck-and-tests     | job_node           |
| dashboard-typecheck        | job_dashboard      |
| remotion-typecheck         | job_remotion       |
| dependency-scan            | job_deps           |
| migration-equivalence      | job_migration      |
| python-harness (build.yml) | job_python_harness |

On success:

- Prints `✅  SAFE TO PUSH`.
- Writes `.harness/deploys/<sha>.ok` sentinel (consumed by pre-push hook).

On failure:

- Prints the exact GH Actions job name(s) that would go red.
- No sentinel is written; the pre-push hook will block your push.

### 3. Push to develop

```bash
# turbo
git push origin develop
```

The pre-push hook verifies `.harness/deploys/<sha>.ok` exists for HEAD. CI
runs on the push; watch with `gh run watch` or `gh run list --limit 5`.

### 4. Promote to main (deploy)

**Never push directly to main.** The pre-push hook rejects it. Instead, use
the promotion workflow:

```bash
# Opens a develop → main PR after verifying develop is green on harness/all-green.
gh workflow run promote-develop-to-main.yml -f mode=manual
```

- `mode=manual` — PR opened, human clicks merge.
- `mode=auto` — PR opened with auto-merge enabled; merges when required
  checks + approval are met.

The `deploy` job in `ci.yml` fires on the `main` push that lands the merge.
Monitor with:

```bash
gh run list --workflow=ci.yml --limit=5
```

### 5. Verify deploy health

```bash
make health
```

---

## When to run which command

| Situation                    | Command                                        |
| ---------------------------- | ---------------------------------------------- |
| Iterating on Python only     | `bash scripts/ci-local.sh --python`            |
| Iterating on TypeScript only | `bash scripts/ci-local.sh --node`              |
| Iterating on dashboard       | `bash scripts/ci-local.sh --dashboard`         |
| Any push to develop          | `make pre-deploy` (mandatory; writes sentinel) |
| Fast sanity check            | `bash scripts/ci-local.sh` (default subset)    |
| Suspect env difference       | `make pre-deploy` (already dockerized)         |

## Bypasses (audit-logged)

- `AUTONIIX_SKIP_SENTINEL=1 git push origin develop` — bypass sentinel gate.
  Reason must be documented in commit message. Logged to `.harness/bypass.log`.
- `AUTONIIX_ALLOW_MAIN=1 git push origin main` — bypass main-push guard.
  Reserved for the promote workflow. Do not use manually.
- `git push --no-verify` — bypass the entire pre-push hook. Discouraged.
