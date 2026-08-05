# ADR-005: Harness & Local ⇄ CI Parity

Status: Accepted (2026-08-05)
Supersedes: nothing
Related: ADR-004 (Phase 7 two-language stack), ADR-006 (branch policy)

## Context

Post Phase 7 the standardization harness (`make harness`), local CI mirror
(`scripts/ci-local.sh`), and GitHub Actions workflows all drifted out of sync:

- `Makefile` and `lefthook.yml` still targeted `libs/python/`,
  `services/gateway-v2`, `services/streaming-hub-v2` (Phase 6 paths).
- `ci.yml` still ran `cargo test -p harness`, `cargo clippy`, `go-harness` on
  directories that were deleted, and its `deploy: needs:` list referenced
  those non-existent jobs — the deploy gate was silently meaningless.
- `package.json` `workspaces` pointed to Phase 6 paths, so `npm ci` never
  linked `@autoniix/contracts` into the new backends; TypeScript typecheck
  was broken but hidden by `|| true` in gating targets.
- `ruff.toml` selected an ambitious rule set (N, UP, B, C4, DTZ, PL, TRY,
  RUF, ...) but CI ran `ruff check ... || true` with a "warn-only until we
  baseline" comment that had been there for a full release cycle. 2377 lint
  errors had accumulated silently.

A developer could not answer the question "will this push turn CI green?"
without pushing and waiting.

## Decision

Three-tier gating with a single source of truth:

1. **Tier 1 — pre-commit (fast, ~5s)**
   Runs on every commit. `ruff format --check` on staged Python, TS typecheck
   on the three TS packages. Enforced by `.husky/pre-commit`.

2. **Tier 2 — pre-push (medium, ~15s)**
   Version-drift check. On pushes to `develop`/`main` a sentinel from Tier 3
   is required (see ADR-006).

3. **Tier 3 — `make pre-deploy` (full, ~5-8min, dockerized)**
   `scripts/ci-local.sh --full --docker` inside a pinned `ubuntu:24.04`
   image. Writes `.harness/deploys/<sha>.ok` on success. This sentinel is
   what the pre-push hook (Tier 2) checks.

Every CI job in `.github/workflows/ci.yml` maps 1:1 to a bash function in
`scripts/ci-local.sh`. When a CI job's working-directory or command changes,
the matching function must be updated in the same PR. Deviation ⇒ silent
"green locally, red in CI" bugs.

The one required status check for branch protection is `harness/all-green` —
a summary job in `ci.yml` that aggregates every quality job. All other
policy (approvals, linearity) is layered on top; no other status check is
required, which keeps CI signal loud and singular.

### Ruff strategy (two-tier)

- BLOCKING `select` in `ruff.toml`: `E, W, F, I` only. Small, safe, mostly
  auto-fixable. Any violation fails `make lint` and `python-lint-and-tests`
  CI job.
- ASPIRATIONAL rules (N, UP, B, ...) documented but not selected. Move one
  rule at a time from aspirational → blocking, cleaning up violations first.
  Track progress in a follow-up ADR when a rule ratchets.

Per-file-ignores exist for legacy F841 dead-assignment files. Each entry is a
TODO — remove the ignore when cleaned up.

## Consequences

+  Local `make pre-deploy` green ⇒ CI green (target: ≥99% reliability).
+  New CI jobs must be added in both `ci.yml` and `ci-local.sh` — enforced by
   code review of PRs that touch either file.
+  The `harness/all-green` single-check pattern makes branch protection
   trivial to configure and reason about.
−  The dockerized `pre-deploy` adds 3-5 min to push flow on `develop`/`main`.
   Acceptable given the assurance it provides.
−  Ratcheting ruff rules is manual — a nightly job could be added later to
   propose the next rule to enable.

## Verification

- `bash scripts/ci-local.sh` green from a clean checkout of `develop`.
- Introducing a deliberate ruff violation on a feature branch fails both the
  local hook and CI.
- Introducing a deliberate TypeScript error fails both.
- Deploy job does not run when `harness-summary` fails.

## Related files

- `Makefile` (targets: `harness`, `harness-report`, `pre-deploy`, `pre-deploy-status`)
- `scripts/ci-local.sh`, `scripts/ci-local.Dockerfile`
- `.github/workflows/ci.yml`, `.github/workflows/versions-in-sync.yml`
- `.husky/pre-commit`, `.husky/pre-push`, `lefthook.yml`
- `ruff.toml`, `package.json`, `versions.env`
