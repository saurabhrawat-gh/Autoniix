# Autoniix Standardization Harness

**Status:** Active (Phase 0 complete, implementing Phase 1–7)  
**Owner:** Saurabh Rawat  
**Last Updated:** 2026-08-01

This document is the **canonical reference** for code quality, testing, linting, formatting, and CI standards in the Autoniix monorepo.

See also: `@/Users/saurabhrawat/Desktop/projects/Autoniix/docs/architecture/adr-004-two-language-simplification.md`

---

## Languages

**Two languages only:**
- **Python 3.12** — all backend services, workers, AI/ML
- **TypeScript** — gateway, dashboard, marketing, streaming hub, Remotion

**Deleted:** Rust, Go, Protocol Buffers

---

## Tool Versions (Single Source of Truth)

**File:** `versions.env`

```bash
NODE=22.23.1
NPM=10.9.8
PNPM=9.15.0
PYTHON=3.12.7
POSTGRES=pg15
```

**Manager:** `mise` (`.mise.toml` + `.tool-versions`)

**Verification:** `make verify-versions` (runs in CI)

---

## Python Standards

### Package Manager: uv

**Why:** 10-100× faster than pip, replaces pip + pip-tools + virtualenv.

**Install:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Usage:**
```bash
uv sync                    # install all deps from pyproject.toml
uv add <package>           # add dependency
uv add --dev <package>     # add dev dependency
uv run pytest              # run command in venv
```

### Workspace Structure

**Root:** `pyproject.toml` (uv workspace)

**Members:**
```
services/api/
services/brain/
services/agents/
services/workers/
services/research/
services/script/
services/voice/
services/thumbnail/
services/delivery/
services/analytics/
services/finishing/
libs/python/contracts/
libs/python/core/
libs/python/events/
libs/python/intelligence/
libs/python/testing/
```

Each member has its own `pyproject.toml` with:
```toml
[project]
name = "autoniix-<service>"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [...]

[tool.uv.sources]
autoniix-contracts = { workspace = true }
autoniix-core = { workspace = true }
```

### Formatter: Ruff Format

**Config:** `ruff.toml` (root)

```toml
target-version = "py312"
line-length = 100

[format]
quote-style = "double"
indent-style = "space"
```

**Run:**
```bash
ruff format .                # format all
ruff format --check .        # check only (CI)
ruff format path/to/file.py  # format one file
```

### Linter: Ruff

**Config:** `ruff.toml`

```toml
select = [
    "E",      # pycodestyle errors
    "F",      # pyflakes
    "W",      # pycodestyle warnings
    "I",      # isort (import sorting)
    "N",      # pep8-naming
    "D",      # pydocstyle (docstrings)
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "PT",     # flake8-pytest-style
    "RET",    # flake8-return
    "ARG",    # flake8-unused-arguments
    "PL",     # pylint
    "RUF",    # ruff-specific
    "S",      # flake8-bandit (security)
    "ASYNC",  # flake8-async
]

ignore = [
    "D100",   # missing docstring in public module
    "D104",   # missing docstring in public package
    "PLR0913", # too many arguments
]

[per-file-ignores]
"tests/**" = ["S101", "D", "PLR2004", "ARG"]
"scripts/**" = ["D"]
```

**Run:**
```bash
ruff check .                 # lint all
ruff check --fix .           # auto-fix
ruff check path/to/file.py   # lint one file
```

### Type Checker: mypy + basedpyright

**mypy** for `libs/python/*` (strict):

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

**basedpyright** for `services/*` (gradual):

```toml
# pyproject.toml
[tool.basedpyright]
pythonVersion = "3.12"
typeCheckingMode = "standard"
reportMissingTypeStubs = false
```

**Run:**
```bash
mypy libs/python/
basedpyright services/
```

### Import Rules

1. **Absolute imports only** — no `from .x import ...` across service boundaries
2. **Order** (enforced by Ruff `I`):
   - stdlib
   - third-party
   - `libs.*`
   - `services.<self>.*`
   - local (same package)
3. **No cross-service imports** — enforced by `tach`:
   ```bash
   tach check
   ```
4. **Shared code only via `libs/python/`**

### Testing: pytest

**Config:** `pytest.ini`

```ini
[pytest]
testpaths = tests services
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = 
    --strict-markers
    --cov=services
    --cov=libs/python
    --cov-report=term-missing
    --cov-report=xml
    -n auto
```

**Plugins:**
- `pytest-asyncio` — async test support
- `pytest-cov` — coverage
- `pytest-xdist` — parallel execution
- `pytest-mock` — mocking
- `respx` — httpx mocking
- `syrupy` — snapshot testing
- `testcontainers` — Postgres/Redis containers

**Run:**
```bash
uv run pytest                     # all tests
uv run pytest tests/unit/         # unit only
uv run pytest -k test_channel     # filter by name
uv run pytest --cov-report=html   # HTML coverage report
```

### Migrations: alembic

**Config:** `alembic.ini`

**Run:**
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

---

## TypeScript Standards

### Package Manager: pnpm

**Why:** 3× faster than npm, deterministic lockfile, disk-efficient.

**Install:**
```bash
npm install -g pnpm@9.15.0
```

**Workspace:** `pnpm-workspace.yaml`

```yaml
packages:
  - 'apps/*'
  - 'libs/ts/*'
  - 'services/remotion'
```

**Usage:**
```bash
pnpm install                      # install all
pnpm add <package> --filter=dashboard  # add to one app
pnpm run build --filter=dashboard      # build one app
pnpm run dev --parallel                # dev all apps
```

### Build Orchestrator: Turborepo

**Config:** `turbo.json`

```json
{
  "$schema": "https://turbo.build/schema.json",
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": [".next/**", "dist/**"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "lint": {},
    "typecheck": {},
    "test": {}
  }
}
```

**Run:**
```bash
pnpm turbo build      # build all apps
pnpm turbo lint       # lint all
pnpm turbo test       # test all
```

### Formatter: Prettier

**Config:** `.prettierrc.json` (root)

```json
{
  "semi": true,
  "singleQuote": false,
  "trailingComma": "es5",
  "printWidth": 100,
  "tabWidth": 2,
  "useTabs": false,
  "arrowParens": "always",
  "endOfLine": "lf"
}
```

**Run:**
```bash
pnpm exec prettier --write .
pnpm exec prettier --check .
```

### Linter: ESLint 9 (Flat Config)

**Config:** `eslint.config.mjs` (root)

```js
import js from "@eslint/js";
import tsPlugin from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import importPlugin from "eslint-plugin-import";
import reactPlugin from "eslint-plugin-react";
import hooksPlugin from "eslint-plugin-react-hooks";

export default [
  js.configs.recommended,
  {
    files: ["**/*.ts", "**/*.tsx"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        project: "./tsconfig.json",
      },
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
      "import": importPlugin,
      "react": reactPlugin,
      "react-hooks": hooksPlugin,
    },
    rules: {
      ...tsPlugin.configs.strict.rules,
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "import/order": ["error", {
        "groups": ["builtin", "external", "internal", "parent", "sibling", "index"],
        "newlines-between": "always",
        "alphabetize": { "order": "asc" }
      }],
      "import/no-cycle": "error",
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
];
```

**Run:**
```bash
pnpm exec eslint .
pnpm exec eslint --fix .
```

### Type Checker: tsc

**Config:** `tsconfig.base.json` (root, extended by all apps)

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "allowJs": false,
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "exactOptionalPropertyTypes": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  }
}
```

**Run:**
```bash
pnpm exec tsc --noEmit                    # all projects
pnpm exec tsc --noEmit --project apps/dashboard/tsconfig.json
```

### Import Rules

1. **No default exports** except React components + Next.js pages
2. **`import type` mandatory** for type-only imports:
   ```ts
   import type { User } from "./types";
   import { getUser } from "./api";
   ```
3. **Path aliases only** (no `../../../`):
   ```ts
   import { ChannelSchema } from "@autoniix/contracts";
   import { Button } from "@autoniix/ui";
   ```
4. **No circular imports** (enforced by `eslint-plugin-import`)
5. **No cross-app imports** (enforced by `eslint-plugin-boundaries`)

### Testing: Vitest

**Config:** `vitest.config.ts` (per package)

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      exclude: ["**/*.test.ts", "**/*.spec.ts", "**/node_modules/**"],
    },
  },
});
```

**Run:**
```bash
pnpm exec vitest                  # watch mode
pnpm exec vitest run              # run once
pnpm exec vitest --coverage       # with coverage
```

### E2E Testing: Playwright

**Config:** `playwright.config.ts` (root)

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
  ],
  webServer: {
    command: "pnpm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
  },
});
```

**Run:**
```bash
pnpm exec playwright test
pnpm exec playwright test --ui
pnpm exec playwright show-report
```

---

## Contract Layer

**Source of truth:** `libs/ts/contracts/`

**Flow:**
1. Edit Zod schemas in `libs/ts/contracts/src/*.schema.ts`
2. Run `make gen-contracts`:
   - Exports OpenAPI JSON
   - Generates Pydantic models in `libs/python/contracts/`
3. TypeScript imports from `@autoniix/contracts`
4. Python imports from `libs.python.contracts`

**Example schema:**

```ts
// libs/ts/contracts/src/channel.schema.ts
import { z } from "zod";

export const ChannelSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(100),
  platform: z.enum(["youtube", "instagram", "tiktok"]),
  created_at: z.string().datetime(),
});

export type Channel = z.infer<typeof ChannelSchema>;
```

**Generated Pydantic:**

```python
# libs/python/contracts/channel.py (auto-generated)
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Literal

class Channel(BaseModel):
    id: UUID
    name: str = Field(min_length=1, max_length=100)
    platform: Literal["youtube", "instagram", "tiktok"]
    created_at: datetime
```

---

## CI Pipeline

**File:** `.github/workflows/ci.yml`

**Jobs:**

1. **install** — uv sync + pnpm install (cached)
2. **lint** — ruff + eslint + prettier
3. **typecheck** — mypy + basedpyright + tsc
4. **test** — pytest + vitest (parallel)
5. **contract** — schema round-trip validation
6. **build** — docker buildx (all images, cached)
7. **e2e** — docker compose up + playwright
8. **coverage** — codecov (fail if diff <80%)

**Estimated time:** 4–6 minutes

**Hard blocks (PR cannot merge if):**
- Any linter error
- Any format diff
- Any type error
- Any test failure
- Diff coverage <80%
- `pip-audit` or `npm audit` high/critical
- Bundle size regression >10%
- OpenAPI breaking change without `BREAKING-CHANGE:` commit trailer

---

## Pre-Commit Hooks

**Tool:** `lefthook` (replaces husky for Python side)

**Config:** `lefthook.yml`

```yaml
pre-commit:
  parallel: true
  commands:
    ruff-format:
      glob: "*.py"
      run: uv run ruff format {staged_files}
    
    ruff-lint:
      glob: "*.py"
      run: uv run ruff check --fix {staged_files}
    
    prettier:
      glob: "*.{ts,tsx,js,jsx,json,md}"
      run: pnpm exec prettier --write {staged_files}
    
    eslint:
      glob: "*.{ts,tsx}"
      run: pnpm exec eslint --fix {staged_files}

pre-push:
  commands:
    ci-fast:
      run: make ci-fast
```

**Install:**
```bash
lefthook install
```

---

## Makefile Targets

```bash
make setup            # uv sync + pnpm install + mise install
make gen-contracts    # zod -> openapi -> pydantic
make lint             # ruff + eslint + prettier check
make fmt              # ruff format + prettier write
make typecheck        # mypy + basedpyright + tsc
make test             # pytest + vitest
make test-e2e         # playwright
make build            # docker buildx all images
make up               # docker compose up
make down             # docker compose down
make ci-fast          # lint + typecheck + unit (pre-push)
make ci               # full CI locally
make verify-versions  # versions.env parity
make ship             # merge develop -> main
```

---

## File Naming Conventions

**Python:**
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions: `snake_case`
- Constants: `UPPER_SNAKE`

**TypeScript:**
- React components: `PascalCase.tsx`
- Everything else: `kebab-case.ts`
- No `index.ts` re-exports except at package root

---

## Service Structure

**Every Python service:**
```
services/<name>/
├── main.py              # entrypoint
├── app.py               # FastAPI factory
├── routes/              # API routes
├── services/            # business logic
├── models/              # Pydantic models (domain)
├── deps.py              # FastAPI dependencies
├── config.py            # settings
├── tests/               # pytest tests
└── pyproject.toml       # uv config
```

**Every TypeScript app:**
```
apps/<name>/
├── src/                 # source code
├── tests/               # vitest tests
├── package.json
├── tsconfig.json
└── vitest.config.ts
```

---

## Coverage Requirements

| Layer | Minimum | Target |
|-------|---------|--------|
| Unit tests | 80% | 90% |
| Integration tests | 60% | 75% |
| Contract tests | 100% | 100% |
| E2E tests | Critical flows only | — |

**Enforcement:** Codecov diff coverage ≥80% (hard block in CI)

---

## Security

**Python:** `pip-audit` in CI (fails on high/critical)

**TypeScript:** `npm audit` in CI (fails on high/critical)

**Secrets:** Never hardcode. Use Infisical or env vars.

**SQL:** Parameterized queries only (no string interpolation).

---

## Documentation

**Code comments:** Only for non-obvious "why", never "what".

**Docstrings (Python):** Google style, only on public APIs.

**JSDoc (TypeScript):** Only on exported functions/types.

**ADRs:** One per major architectural decision in `docs/architecture/`.

---

## Questions?

See:
- `docs/architecture/adr-004-two-language-simplification.md` — the "why"
- `docs/harness/python-conventions.md` — Python deep dive
- `docs/harness/typescript-conventions.md` — TypeScript deep dive
- `Makefile` — all commands
- `#engineering` Slack — ask the team

---

**Last updated:** 2026-08-01  
**Next review:** After Phase 7 completion
