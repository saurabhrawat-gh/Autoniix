---
description: Pre-commit validation — lint, type check, test suite, secret scan (Phase 7)
---

# Pre-Commit Workflow

**HARD RULE: never push to `origin/develop` without a green local harness.**
**HARD RULE: never push to `origin/main` — use the promote workflow.**

The husky pre-commit hook already gates every commit on ruff format + lint
and TypeScript typecheck. This workflow is what you as an agent should do
before running `git commit` at all.

---

## Steps

### 1. Check for hardcoded secrets
```bash
# turbo
grep -rn "api_key\s*=\s*['\"]" shared/ backend/ --include="*.py" | grep -v "settings\." | grep -v ".example"
grep -rn "password\s*=\s*['\"]" shared/ backend/ --include="*.py" | grep -v "settings\."
```
If any matches found: **STOP**. Move to `shared/python/core/config.py` + `.env`.

### 2. Run local checks — targeted to what you changed

Every function in `scripts/ci-local.sh` maps to a GH Actions job.

| What you changed                    | Command                                       |
|-------------------------------------|-----------------------------------------------|
| Python code                         | `bash scripts/ci-local.sh --python`            |
| TypeScript (gateway/streaming-hub)  | `bash scripts/ci-local.sh --node`              |
| Frontend dashboard                  | `bash scripts/ci-local.sh --dashboard`         |
| Remotion (backend/media/remotion)   | `bash scripts/ci-local.sh --remotion`          |
| DB migrations                       | `bash scripts/ci-local.sh --migration`         |
| Multiple areas / unsure             | `bash scripts/ci-local.sh --full`              |
| Fast sanity                         | `bash scripts/ci-local.sh` (default subset)    |

**Final line must be:**
- `✅  ci-local passed — CI would be green.` → proceed.
- `❌  ci-local FAILED — the following GH jobs would be red: ...` → **STOP.**
  Fix every listed job. Re-run until green.

### 3. Check git diff scope
```bash
# turbo
git diff --stat
```
> 5 files changed for a single task: **PAUSE** and justify. Surgical changes touch few files.

### 4. Verify no production-only code in the test path
```bash
# turbo
grep -rn "ENVIRONMENT_MODE.*production" shared/ backend/ --include="*.py" | head -5
```
Use `is_test()` / `is_production()` from `shared.python.core.environment`,
not hardcoded strings.

### 5. Commit with descriptive message
```bash
git add -A && git commit -m "feat(#N): [description of what changed and why]"
```
The husky pre-commit hook runs ruff format check + lint + TS typecheck on
the changed files.

### 6. Push only after green
```bash
# For develop: pre-push hook requires .harness/deploys/<sha>.ok sentinel
make pre-deploy      # writes sentinel on success
git push origin develop
```
Never `git push origin main`. Use `gh workflow run promote-develop-to-main.yml`.
