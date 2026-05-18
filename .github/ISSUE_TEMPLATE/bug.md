---
name: Bug Report
about: A defect in existing behaviour. Filed by the QA agent or dev.
labels: bug, ready-for-dev
---

**Parent Story:** #
**Severity:** [critical | high | medium | low]

## What Is Broken
<!-- One sentence: what behaviour is wrong. -->

## Steps to Reproduce
1. ...
2. ...
3. ...

## Expected Behaviour
<!-- What should happen. -->

## Actual Behaviour
<!-- What actually happens. Include error message or screenshot if available. -->

## Test Cases

### Happy Flow (what should work after fix)
- [ ] TC-BUG-01: [action] → Expected: [correct behaviour]
- [ ] TC-BUG-02: [action] → Expected: [correct behaviour]

### Sad / Error Flow
- [ ] TC-BUG-03: [trigger the original bug] → Expected: [error no longer occurs]
- [ ] TC-BUG-04: [related invalid input] → Expected: [proper error response]

### Regression Check
- [ ] TC-BUG-05: Adjacent feature still works as before

## Environment
- Mode: [test | production]
- Service: [dashboard-bff | worker | script | voice | etc.]
- Introduced in: [commit / PR / deploy date if known]

## Definition of Done
- [ ] Root cause identified and documented in PR
- [ ] Fix implemented with minimal scope
- [ ] Regression test added to test suite
- [ ] All test cases above pass
- [ ] `/diff-review` workflow passed
