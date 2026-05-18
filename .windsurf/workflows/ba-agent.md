---
description: BA Agent — gather requirements for any new feature, then file structured GitHub Issues (Epic → Story → Task)
---

# BA Agent Workflow

Use this workflow at the START of every new feature request, before any code is written.

## Steps

1. **Understand the raw request**
   - Read the user's request carefully
   - Identify: What problem is being solved? Who are the users/personas? What is the scope?

2. **Ask clarifying questions (BA phase)**
   Ask these for every feature — do not skip:
   - Who are the actors? (Owner, Admin, Producer, Editor, Viewer — which roles are affected?)
   - What are the happy path use cases? (Actor does X → System does Y)
   - What are the failure/edge cases? (Invalid input, permission denied, resource not found)
   - What is explicitly OUT of scope for this iteration?
   - Any dependencies on other features or external systems?
   - Is backend, frontend, or both affected?
   - Are there DB schema changes needed?
   - What does "done" look like? How will we test it?

3. **Document use cases**
   Format every use case as:
   ```
   | ID | Actor | Action | Expected Outcome |
   ```

4. **Define acceptance criteria**
   Format as Given/When/Then or explicit checkboxes:
   ```
   - [ ] Given [context], when [action], then [outcome]
   ```

5. **Identify impacted systems**
   List every file, table, service, and API endpoint that will change.

6. **Get user sign-off**
   Present the use cases and acceptance criteria to the user. Get explicit confirmation before creating GitHub issues.

7. **Create GitHub Issues in saurabhrawat-gh/Autoniix**
   - One **Epic** issue (label: `epic`) — Goal, Business Value, Stories list, Out of Scope, DoD
   - One **Story** issue per deliverable unit (label: `story`, `ready-for-dev`) — Summary, Personas, Use Cases, ACs, Impacted Files, DoD
   - Add **Task** issues (label: `task`) only if a story has complex sub-steps worth tracking separately

8. **Label lifecycle**
   ```
   ba-approved → ready-for-dev → in-dev → in-review → done
   ```
   Stories start at `ready-for-dev` after user sign-off.

9. **Update PENDING.md if needed**
   If any part of this feature is intentionally deferred, add an entry to PENDING.md with a concrete trigger condition.

## Rules
- Never write code during BA phase
- Never create issues without use cases + acceptance criteria
- Every epic must have an explicit Out of Scope section
- Role-based features must reference the 5-role matrix: owner > admin > producer > editor > viewer
