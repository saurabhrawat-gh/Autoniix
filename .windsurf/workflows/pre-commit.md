---
description: Pre-commit validation — lint, type check, test suite, secret scan
---

# Pre-Commit Workflow

Run this before committing code changes to ensure quality and safety.

## Steps

1. **Check for hardcoded secrets**
   ```bash
   # turbo
   grep -rn "api_key\s*=\s*['\"]" src/ --include="*.py" | grep -v "settings\." | grep -v ".example"
   grep -rn "password\s*=\s*['\"]" src/ --include="*.py" | grep -v "settings\."
   ```
   If any matches found: **STOP**. Move to config.py + .env.

2. **Run linter**
   ```bash
   # turbo
   ruff check src/ tests/
   ```
   Fix any errors before proceeding.

3. **Run test suite**
   ```bash
   # turbo
   pytest --tb=short -q
   ```
   All tests must pass. If failures: fix before committing.

4. **Check git diff scope**
   ```bash
   # turbo
   git diff --stat
   ```
   If more than 5 files changed for a single task: **PAUSE** and justify why. Surgical changes should touch few files.

5. **Verify no production-only code in test path**
   ```bash
   # turbo
   grep -rn "ENVIRONMENT_MODE.*production" src/ --include="*.py" | head -5
   ```
   Ensure environment checks use `is_test()` / `is_production()` from `src.environment`, not hardcoded strings.

6. **Commit with descriptive message**
   ```bash
   git add -A && git commit -m "feat: [description of what changed and why]"
   ```
