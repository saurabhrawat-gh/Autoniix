---
name: Hotfix
about: Critical production-impacting issue requiring fast-track fix. Filed by dev or on-call.
labels: hotfix, in-progress
---

**Linked to Story/Issue:** #
**Production Impact:** [service-down | data-loss | security | revenue | auth-broken]
**Detected At:** <!-- timestamp -->

## What Is Broken
<!-- One sentence. Be specific. -->

## Impact Scope
- Affected users / % of requests: ...
- Workaround available: [yes: `...` | no]
- SLA breach risk: [yes | no]

## Root Cause (fill in once diagnosed)
<!-- What went wrong. -->

## Fix
<!-- What change is needed. Keep it minimal — hotfixes should be surgical. -->

## Test Cases

### Smoke After Fix
- [ ] TC-HF-01: Service responds to health check (`/health` returns 200)
- [ ] TC-HF-02: Critical path (login / trigger / progress) works end-to-end
- [ ] TC-HF-03: The specific error no longer appears in `docker logs`
- [ ] TC-HF-04: No new errors introduced (adjacent features spot-checked)

## Fast-Track Checklist
- [ ] Fix committed to `hotfix/issue-{N}-{slug}` branch
- [ ] Unit/smoke test added
- [ ] PR opened (title: `hotfix(#N): ...`)
- [ ] Deployed to production directly from hotfix branch
- [ ] Post-mortem issue created (label: `post-mortem`)
- [ ] Hotfix cherry-picked to `develop` and `main` after deploy

## Definition of Done
- [ ] Production error resolved
- [ ] All smoke test cases pass
- [ ] Post-mortem filed
