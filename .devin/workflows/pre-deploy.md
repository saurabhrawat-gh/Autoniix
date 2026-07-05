---
description: Pre-deploy verification — run every CI job locally, confirm green, then promote develop to main
---

# Pre-Deploy Workflow

**One command gives you a 100% local guarantee before touching main.**

`make pre-deploy` runs the exact same checks as every GitHub Actions job.
If it passes locally, the remote build passes. No surprises.

---

## Steps

### 1. Confirm you are on develop with a clean tree
```bash
# turbo
git checkout develop && git status
```
Output must be `nothing to commit, working tree clean`. If not, commit or stash first.

### 2. Run every CI job locally
```bash
make pre-deploy
```

This runs `bash scripts/ci-local.sh --full` which mirrors:

| CI Workflow | Job | Local equivalent |
|---|---|---|
| `build.yml` | `rust` | cargo fmt + clippy + cargo test (all crates) |
| `build.yml` | `go-harness` | go build + vet + test ./... |
| `build.yml` | `bench-regression` | Criterion benchmarks vs baseline |
| `build.yml` | `python-harness` | contract tests + migration tests |
| `build.yml` | `dashboard-frontend` | tsc --noEmit + vitest + eslint |
| `ci.yml` | `python-lint-and-tests` | ruff + mypy + pytest |
| `ci.yml` | `dashboard-typecheck` | tsc --noEmit |
| `ci.yml` | `remotion-typecheck` | tsc --noEmit |
| `ci.yml` | `dependency-scan` | pip-audit |
| `equivalence.yml` | `harness-contract` | cargo test -p harness |
| `proto-validate.yml` | `proto-validate` | buf lint + format + breaking |

**Wait for the final line:**
- `✅  ALL CHECKS PASSED — build WILL pass on GitHub Actions` → proceed to step 3
- `⚠  N check(s) failed: ...` → **STOP. Fix every listed failure. Re-run `make pre-deploy` until green.**

For maximum parity (inside a pinned ubuntu:24.04 container):
```bash
make ci-local-docker
```

### 3. Push to develop and wait for CI
```bash
# turbo
git push origin develop
```
Watch the Actions run: `gh run watch` or open the GitHub Actions tab.

### 4. Promote to main (deploy)

> ⚠️  **BUILD FREEZE** — do not run this step until the freeze lifts (2026-07-11).

```bash
git checkout main
git merge --no-ff develop
git push origin main
```

The `deploy` job in `build.yml` triggers automatically on `main` push.
It runs on the self-hosted VPS runner. Monitor with:
```bash
gh run list --workflow=build.yml --limit=5
```

### 5. Verify deploy health
```bash
make health
```

---

## When to run which command

| Situation | Command |
|---|---|
| Changed only Rust code | `bash scripts/ci-local.sh` (default Rust-only, ~90s) |
| Changed only Python | `bash scripts/ci-local.sh --python` |
| Changed only TypeScript | `bash scripts/ci-local.sh --node` |
| Changed only Go | `bash scripts/ci-local.sh --go` |
| Changed protos | `bash scripts/ci-local.sh --proto` |
| **Before any deploy** | `make pre-deploy` (full, every job) |
| Suspect env difference | `make ci-local-docker` (inside ubuntu:24.04) |
