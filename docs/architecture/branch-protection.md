# Branch Protection — required GitHub settings

Codified so anyone can reproduce the state via `scripts/apply-branch-protection.sh`.
Manual application requires org admin rights.

## Policy summary

- `main` — production. **No direct pushes.** Only reachable via PR from `develop`
  (or `hotfix/*`) that passes the `harness/all-green` required status check.
- `develop` — integration. All feature work targets develop. Requires
  `harness/all-green` and no force-pushes.

## Required settings for `main`

- Require pull request before merging:
  - Required approvals: **1**
  - Dismiss stale reviews when new commits are pushed: **true**
  - Require review from Code Owners: false (enable when CODEOWNERS lands)
- Require status checks to pass before merging:
  - Required checks: **`harness/all-green`**, **`versions.env drift check`**
  - Require branches to be up to date before merging: **true**
- Require conversation resolution before merging: **true**
- Require linear history: **true**
- Restrict who can push to matching branches: **repository admins only**
  (in practice: nobody except the promote-develop-to-main workflow)
- Allow force pushes: **false**
- Allow deletions: **false**

## Required settings for `develop`

- Require status checks to pass before merging:
  - Required checks: **`harness/all-green`**, **`versions.env drift check`**
  - Require branches to be up to date before merging: **true**
- Require conversation resolution before merging: **true**
- Allow force pushes: **false**
- Allow deletions: **false**
- Approvals: not required on develop (feature branches iterate quickly), but
  strongly encouraged for large PRs.

## Applying

```bash
# Requires: gh CLI authenticated as an org admin.
bash scripts/apply-branch-protection.sh
```

The script is idempotent — it applies the JSON via `gh api PUT` and reports
what changed.

## Verifying

```bash
gh api repos/:owner/:repo/branches/main/protection --jq '.required_status_checks'
gh api repos/:owner/:repo/branches/develop/protection --jq '.required_status_checks'
```

## Bypass log

Any client-side bypass (`AUTONIIX_ALLOW_MAIN=1`, `AUTONIIX_SKIP_SENTINEL=1`,
`git push --no-verify`) is logged to `.harness/bypass.log` locally. Server-side
bypass requires temporarily removing branch protection (admin operation), which
is audited by GitHub.
