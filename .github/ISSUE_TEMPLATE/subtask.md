---
name: Subtask
about: An atomic sub-item under a story or task. Filed by QA agent or dev agent.
labels: subtask, ready-for-dev
---

**Parent Story/Task:** #
**Order:** [1 of N | 2 of N | etc.]

## What

<!-- One sentence: what needs to be done. -->

## Context

<!-- Why this sub-task exists — which part of the parent story it satisfies. -->

## Steps

1. ...
2. ...
3. ...

## Files Affected

- `src/...`
- `dashboard/...`

## Test Cases

- [ ] TC-ST-01: [action] → Expected: [outcome]
- [ ] TC-ST-02: [edge case] → Expected: [outcome]
- [ ] TC-ST-03: Parent story acceptance criteria still met after this change

## Test Command

```bash
pytest tests/test_... -v
```

## Definition of Done

- [ ] Change implemented
- [ ] Test passes
- [ ] No regressions (full suite passes)
- [ ] Parent story DoD checklist item ticked
