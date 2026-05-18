---
name: Epic
about: A large feature with multiple stories. Filed by the BA agent.
labels: epic
---

## Goal
<!-- One paragraph: what this epic delivers and why it matters. -->

## Business Value
<!-- List 3-5 concrete outcomes for the user or business. -->

## Stories
<!-- Link each child story issue once created. -->
- [ ] STORY: ...
- [ ] STORY: ...

## Out of Scope
<!-- Explicitly list what this epic does NOT cover. -->

## Test Coverage
<!-- QA agent runs /qa-agent on each story — test-case issues auto-created -->
- All stories have linked test-case issues (created by `/qa-agent`)

## Definition of Done
- [ ] All stories closed
- [ ] `/qa-agent` run on every story — test-case issues created and verified
- [ ] All test-case checkboxes across all stories marked `qa-verified`
- [ ] Acceptance tests passing
- [ ] `/devops-agent deploy` run — deployed to production and smoke-tested
- [ ] All story issues labelled `prod-verified` and closed
