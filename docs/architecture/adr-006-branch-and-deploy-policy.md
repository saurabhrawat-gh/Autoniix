# ADR-006: Branch and Deploy Policy

Status: Accepted (2026-08-05)
Related: ADR-005 (Harness), branch-protection.md

## Context

Prior state allowed direct pushes to `main` if a commit message happened to
contain the word "develop" (the previous CI `guard` job matched on message
substring). Deploy fired on every `main` push regardless of merge parentage
after `if: always()` fallbacks. There was no client-side prevention.

## Decision

The promotion pipeline is strictly:

```
feature/*  →  PR  →  develop  →  promote-develop-to-main.yml  →  main  →  deploy
```

Enforced at four levels:

### 1. Client-side (`.husky/pre-push`)

- Hard-rejects `git push origin main`. Bypass: `AUTONIIX_ALLOW_MAIN=1`
  (audit-logged to `.harness/bypass.log`). Only the promote workflow uses it.
- Requires `.harness/deploys/<sha>.ok` sentinel from a successful
  `make pre-deploy` for every push to `develop`. Bypass:
  `AUTONIIX_SKIP_SENTINEL=1` (also audit-logged).
- Feature branches: only version-drift check runs.

### 2. GitHub branch protection

- `main`: requires `harness/all-green` + `versions.env drift check` +
  1 approval + linear history + up-to-date + no force-push + no deletions.
  Restrictions block direct push for all humans.
- `develop`: requires the two status checks + no force-push.

Declared in `.github/branch-protection.yml`; applied by
`scripts/apply-branch-protection.sh`. See `docs/architecture/branch-protection.md`.

### 3. CI `guard` job (`ci.yml`)

For pushes to `main`, verifies HEAD's second parent is an ancestor of
`origin/develop` (or `origin/hotfix/*`) using `git merge-base --is-ancestor`.
This closes the "commit message contains 'develop'" loophole.

### 4. Promotion workflow (`promote-develop-to-main.yml`)

Sole allowed entry to `main`. Two modes:

- `manual` (default): opens a `develop → main` PR; human clicks merge.
- `auto`: opens the PR and enables GitHub auto-merge. Merges when required
  status checks green and, for `main`, an approval lands.

Preconditions verified in the workflow before opening a PR:

1. `develop` HEAD has succeeded on the `harness/all-green` check-run.
2. `develop` is ahead of `main` by ≥ 1 commit.
3. No open PR from any other head against `main` with the `blocks-promotion`
   label (future extension).

Nightly cron dry-run reports drift between `develop` and `main` without
opening a PR.

### Hotfix path

`hotfix/*` branches may PR directly to `main`. The `guard` job accepts merge
parents on any `origin/hotfix/*` branch. Reviewers must ensure the hotfix is
back-merged to `develop` in the same day; the `check-pending.md` workflow
tracks this.

## Consequences

+ Direct pushes to `main` are impossible from three angles simultaneously.
+ Every `main` commit is a merge from `develop` (or `hotfix/*`), tested and
  known-green before landing.
+ Deploy fires only on green-verified `main` pushes.
- Adds one workflow-dispatch step to weekly releases. Mitigated by the
  `auto` mode.
- If GitHub auto-merge is disabled at the org level, `auto` mode degrades to
  `manual` — documented in the promote workflow output.

## Bypass audit

All client-side bypasses land in `.harness/bypass.log` with timestamp, user,
target ref, and reason. Server-side bypass requires temporarily lifting
branch protection (admin operation), audited by GitHub.

## Verification

1. `git push origin main` on a laptop is rejected client-side.
2. On GitHub, direct-push branch-protection rejects at the wire.
3. A PR from a feature branch cannot merge without `harness/all-green`.
4. Deploy job does not fire on `main` when the guard fails.
5. `promote-develop-to-main.yml` refuses to open a PR when
   `harness/all-green` is not green on `develop` HEAD.

## Related files

- `.husky/pre-push`
- `.github/workflows/ci.yml` (guard, deploy)
- `.github/workflows/promote-develop-to-main.yml`
- `.github/branch-protection.yml`
- `scripts/apply-branch-protection.sh`
- `docs/architecture/branch-protection.md`
