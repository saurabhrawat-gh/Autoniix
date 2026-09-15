# Toolchain — Version Parity Between Local, CI, and Production

Every language runtime, build tool, base Docker image, and postgres major version used anywhere in Autoniix is pinned to a **single source of truth**: [`versions.env`](../versions.env) at the repo root.

```
                       ┌───────────────────┐
                       │   versions.env    │  ← the ONLY file that names versions
                       └────────┬──────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
   local dev tools        CI workflows            prod Dockerfiles
   (rustc, node,          (.github/workflows)     (rust/gateway,
    python, go, buf)                               dashboard, web, …)
```

If any layer drifts, the **Versions in Sync** CI job blocks the PR.

## Pinned versions

| Tool                | Version   | Source                                   |
| ------------------- | --------- | ---------------------------------------- |
| Rust                | `1.83.0`  | `rust-toolchain.toml`, `.tool-versions`  |
| Node                | `20.18.0` | `.nvmrc`, `.tool-versions`               |
| npm                 | `10.9.0`  | `packageManager` in every `package.json` |
| Python              | `3.12.7`  | `.python-version`, `.tool-versions`      |
| Go                  | `1.22.10` | `.go-version`, `.tool-versions`          |
| Buf                 | `1.47.2`  | `.tool-versions`                         |
| Postgres (pgvector) | `pg15`    | `docker-compose.yml` + every CI job      |
| cargo-audit         | `0.20.1`  | `versions.env`                           |

All Python dev/CI tools (ruff, mypy, pytest, pip-audit, cyclonedx-bom, …) are `==`-pinned in [`requirements-dev.txt`](../requirements-dev.txt).

## Installing pinned tools

Pick **one**:

### mise (recommended)

```bash
brew install mise
mise install                       # reads .tool-versions
```

### asdf

```bash
brew install asdf
asdf plugin add rust nodejs python golang buf
asdf install                       # reads .tool-versions
```

### Manual

```bash
rustup show                                          # reads rust-toolchain.toml
nvm install $(cat .nvmrc) && nvm use
pyenv install $(cat .python-version) && pyenv local $(cat .python-version)
curl -fsSL https://go.dev/dl/go$(cat .go-version).$(uname | tr A-Z a-z)-$(uname -m).tar.gz | sudo tar -C /usr/local -xzf -
brew install bufbuild/buf/buf
```

Verify:

```bash
make verify-versions
```

## Running the local CI mirror

### Fast mode — on host

```bash
make ci-local        # Rust only (~90s)
make ci-local-full   # Rust + Python + Node + Go + Proto (~5min)
```

### Ultimate parity mode — pinned ubuntu:24.04 container

```bash
make ci-local-docker
```

Rebuilds nothing on the host. Every step runs inside an image built from [`scripts/ci-local.Dockerfile`](../scripts/ci-local.Dockerfile):

- Ubuntu 24.04, linux/amd64 (matches CI + prod)
- `TZ=UTC`, `LC_ALL=C.UTF-8`
- Every toolchain pinned to `versions.env`
- Same postgres major as prod

Image is cached; rebuilds only when `versions.env` changes.

**Use `--docker` mode if:**

- You're on Apple Silicon (arm64) and want prod (amd64) parity
- Your locale isn't `C.UTF-8`
- You can't install the exact pinned tools
- You're doing a release and want maximum confidence

## Checking drift

```bash
make check-drift
```

Reads `versions.env` and asserts every downstream file (rust-toolchain.toml, .nvmrc, .python-version, .go-version, .tool-versions, every `package.json`, every workflow YAML, every Dockerfile, docker-compose.yml) matches. This is what the CI **Versions in Sync** job runs.

## Bumping a version

1. Edit `versions.env` — change one or more `*_VERSION` values.
2. `make check-drift` — see the list of files that now drift.
3. Update each listed file:
   - `rust-toolchain.toml` channel
   - `.nvmrc`, `.python-version`, `.go-version`, `.tool-versions`
   - Every `package.json` `engines` + `packageManager`
   - Every Dockerfile `ARG *_IMAGE` default
   - The pgvector image in `docker-compose.yml`
4. `make check-drift` — must be green.
5. `make ci-local-docker` — must be green (proves the new versions actually build + test).
6. Commit everything in **one atomic PR**.

## Pre-push hook

`.husky/pre-push` runs `check-drift` on every push (~2s). Blocks the push if any pin drifts.

Enable the full CI mirror on every push (recommended before releases):

```bash
echo 'export AUTONIIX_PREPUSH_CI=1' >> ~/.zshrc
```

Bypass in an emergency:

```bash
git push --no-verify
```

## Why this exists

**Bugs this file structure prevents:**

- Migration written against pg16-only SQL syntax, CI green (pg16), prod fails (pg15).
- Silent rust-toolchain@stable upgrade breaks a build a week after merge.
- Dev's node 22 formats JSON differently from CI's node 20.
- Apple Silicon dev builds arm64 image, prod is amd64.
- `pip install ruff` at CI-time picks up a new major, entire codebase relints.

Each of these was possible before. Now every one triggers a red CI check before merge.

## File map

| File                                     | Purpose                                       |
| ---------------------------------------- | --------------------------------------------- |
| `versions.env`                           | Single source of truth                        |
| `rust-toolchain.toml`                    | rustup channel pin                            |
| `.nvmrc`                                 | nvm + `setup-node` `node-version-file`        |
| `.python-version`                        | pyenv + `setup-python` `python-version-file`  |
| `.go-version`                            | `setup-go` `go-version-file`                  |
| `.tool-versions`                         | mise + asdf                                   |
| `.npmrc`                                 | `engine-strict=true` — npm refuses wrong node |
| `.gitattributes`                         | Force LF line endings                         |
| `requirements-dev.txt`                   | Pinned Python dev tools                       |
| `scripts/verify-versions.sh`             | Assert local install matches                  |
| `scripts/verify-versions-in-sync.sh`     | Assert all pin files match                    |
| `scripts/ci-local.sh`                    | Local CI mirror (host or `--docker`)          |
| `scripts/ci-local.Dockerfile`            | The pinned ubuntu:24.04 image                 |
| `.github/workflows/versions-in-sync.yml` | CI drift detector                             |
| `.husky/pre-push`                        | Automatic drift check before push             |
