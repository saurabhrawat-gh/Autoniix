---
description: Pre-commit validation — lint, type check, test suite, secret scan
---

# Pre-Commit Workflow

**HARD RULE: Never push to `origin` (develop or main) without a green local CI run first.**

The `scripts/ci-local.sh` script is the single source of truth. It replicates the exact
same checks that run on GitHub Actions — same Docker image, same commands, same env vars.
If it passes locally, the remote build will pass. If it fails locally, fix it first.

---

## Steps

### 1. Check for hardcoded secrets
```bash
# turbo
grep -rn "api_key\s*=\s*['\"]" src/ --include="*.py" | grep -v "settings\." | grep -v ".example"
grep -rn "password\s*=\s*['\"]" src/ --include="*.py" | grep -v "settings\."
```
If any matches found: **STOP**. Move to config.py + .env.

### 2. Run local CI — targeted to what you changed

Run only the block(s) relevant to your change (fast):

| What you changed | Command |
|---|---|
| Rust code | `bash scripts/ci-local.sh --rust` |
| SQL migration files | `bash scripts/ci-local.sh --db` |
| Python code | `bash scripts/ci-local.sh --python` |
| Dashboard (Next.js / TypeScript) | `bash scripts/ci-local.sh --node` |
| Go code | `bash scripts/ci-local.sh --go` |
| Proto files | `bash scripts/ci-local.sh --proto` |
| Multiple areas / unsure | `bash scripts/ci-local.sh` (runs everything) |

**Wait for the final line:**
- `✅  ALL CI CHECKS PASSED — safe to merge to main` → proceed to step 3
- `❌  THE FOLLOWING CHECKS FAILED: ...` → **STOP. Fix every listed failure. Re-run until green.**

Do NOT skip this step or push while red. Each CI minute on GitHub costs money.

### 3. Check git diff scope
```bash
# turbo
git diff --stat
```
If more than 5 files changed for a single task: **PAUSE** and justify why. Surgical changes should touch few files.

### 4. Verify no production-only code in test path
```bash
# turbo
grep -rn "ENVIRONMENT_MODE.*production" src/ --include="*.py" | head -5
```
Ensure environment checks use `is_test()` / `is_production()` from `src.environment`, not hardcoded strings.

### 5. Commit with descriptive message
```bash
git add -A && git commit -m "feat(#N): [description of what changed and why]"
```

### 6. Push only after green
```bash
# Only run this after step 2 shows ✅ ALL CI CHECKS PASSED
git push origin develop
```
