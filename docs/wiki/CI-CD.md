# CI / CD

## Source

- `.github/workflows/ci.yml`

## Jobs

### `python-lint-and-tests`

- Python 3.11 with pip cache.
- Strips heavy ML deps from `requirements.txt` before install (kept out
  of the lint/test matrix; exercised in the docker smoke job).
- `ruff check src tests scripts` (warn-only until the codebase
  is baselined).
- AST-parses every `src/**/*.py` to catch syntax errors fast.
- `pytest -m "not integration and not load"`.

### `dependency-scan`

- `pip-audit` against `requirements.txt`.
- `cyclonedx-py` produces SBOM.
- Artifacts retained 90 days.

### `docker-smoke` (suggested / future)

- `docker compose build` for changed services.
- `docker compose up -d` in test mode.
- `make smoke` against the stack.
- Tear down.

### `deploy`

On push to `main` (manual approval gate):

- SSH into target host.
- `git pull && docker compose build && docker compose up -d`.
- `make smoke` post-deploy.
- Slack notification (success / failure).

## Local mirror

`make deploy-check` runs the same gates as CI before pushing:

- Secret defaults check.
- Required env vars present.
- Migrations apply cleanly.
- Unit tests pass.

## Concurrency

The workflow uses `concurrency: ci-${{ github.ref }}` with
`cancel-in-progress: true` so re-pushing a PR cancels the previous run.

## Related pages

- [[Testing-Strategy]] · [[Operations-Runbook]] ·
  [[Security-Network-TLS-Hardening]]
