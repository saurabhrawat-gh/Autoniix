---
description: Diff review — review git diff for surgical compliance, no style drift or unrelated changes
---

# Diff Review Workflow

Run this after making code changes to verify surgical compliance — no style drift, no unrelated changes, no speculative additions.

## Steps

1. **Generate the diff**
   ```bash
   # turbo
   git diff --stat
   git diff
   ```

2. **Check file count**
   - If more than 3 files changed for a single-file task: **PAUSE** and justify why.
   - If more than 5 files changed for any task: list each file and explain why it was touched.

3. **Review each changed line against the task**
   For every changed line, ask:
   - Does this line trace directly to the user's request?
   - Was this formatting/style change explicitly asked for?
   - Was this import addition/removal necessary for the task?
   - Was this comment/docstring change requested?

4. **Check for anti-patterns**
   - ❌ Quote style changes (single→double or vice versa) not requested
   - ❌ Type hints added to code that didn't have them
   - ❌ Docstrings added to functions that didn't have them
   - ❌ Whitespace/formatting changes unrelated to the fix
   - ❌ "Improvements" to adjacent code not mentioned in the task
   - ❌ Dead code deletion not requested (mention it, don't delete it)
   - ❌ New abstractions for single-use code
   - ❌ Features beyond what was explicitly asked

5. **Verify style consistency**
   - New code should match the existing style in the file.
   - If the file uses `snake_case`, don't add `camelCase`.
   - If the file has no type hints, don't add them.
   - If the file uses `structlog`, use `structlog` (not `logging`).

6. **Fix any violations**
   - Revert unrelated changes with `git checkout -- <file>` for specific hunks.
   - Or use `git add -p` to stage only relevant changes.

7. **Final verification**
   ```bash
   # turbo
   git diff --stat
   ```
   Confirm the diff is minimal and surgical.
