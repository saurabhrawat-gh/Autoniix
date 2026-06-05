---
description: Context hygiene — summarize current session into State Card format, drop stale context
---

# Context Hygiene Workflow

Run this when the session has been running long and context may be polluted. Summarizes progress into a compact State Card.

## Steps

1. **Review what's been done**
   - List all files read, edited, or created in this session.
   - List all commands run.
   - Identify the current task and its status.

2. **Create a State Card** — Use this format:
   ```markdown
   ## Agent State Card — [current timestamp]

   COMPLETED:
   - [bullet list of done items with file paths]

   IN PROGRESS:
   - [current task + last known state]

   BLOCKERS:
   - [anything needing human input]

   NEXT:
   1. [next step]
   2. [step after that]
   3. [step after that]
   ```

3. **Drop stale context**
   - Remove full file contents from conversation — replace with file references.
   - Summarize long outputs into key findings.
   - Keep only: State Card + current task context + relevant skill.

4. **Verify context is lean**
   - Active context should be under 2000 tokens (rules + skills + task).
   - If reading more than 10 files for a new task, delegate to a subagent instead.

5. **Save progress notes** (optional)
   - If multi-session work, create a `progress.txt` or update the plan file.
   - Include: what was done, what's pending, any decisions made.
