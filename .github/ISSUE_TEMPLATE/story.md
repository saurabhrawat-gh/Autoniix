---
name: Story
about: A deliverable unit of work scoped to one feature area. Filed by the BA agent.
labels: story
---

**Parent Epic:** #

## Summary
<!-- One sentence: what this story delivers. -->

## Personas
<!-- Who is affected by this change? -->
- **[Role]**: ...

## Use Cases
| ID | Actor | Action | Expected Outcome |
|---|---|---|---|
| UC-XX-01 | ... | ... | ... |

## Acceptance Criteria
<!-- Specific, testable conditions. Each must be verifiable. -->
- [ ] ...
- [ ] ...

## Impacted Systems
<!-- Files, tables, services affected. -->
- `src/...`
- `dashboard/...`
- Migration: `scripts/migrations/...`

## QA Test Cases
<!-- Linked test-case issue(s) created by /qa-agent -->
- Test plan: #

## Definition of Done
- [ ] `/qa-agent` run — test-case issue(s) created and linked above
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] PR opened and linked to this issue
- [ ] `/diff-review` workflow passed
- [ ] All test-case checkboxes verified (`qa-verified`)
