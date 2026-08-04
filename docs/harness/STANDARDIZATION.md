# Standardization Harness

**Status:** Phase 7 complete (2026-08-04)  
**Stack:** Python + TypeScript only

This document describes the standardization harness applied to the Autoniix codebase after the polyglot → two-language migration.

---

## Overview

The harness enforces consistent code style, quality, and testing across the entire monorepo using industry-standard tools.

---

## Python

### Tools

| Tool | Purpose | Config |
|------|---------|--------|
| **Ruff** | Format + lint | `ruff.toml` |
| **mypy** | Type checking (libs) | `pyproject.toml` |
| **basedpyright** | Type checking (services) | `pyrightconfig.json` |
| **pytest** | Testing + coverage | `pytest.ini` |

### Commands

```bash
# Format
ruff format .

# Lint
ruff check .
ruff check --fix .

# Type check
mypy libs/python/
basedpyright services/

# Test
pytest
pytest --cov --cov-report=html
```

### Rules

- **Line length:** 120
- **Target:** Python 3.12
- **Imports:** isort with known-first-party
- **Quotes:** Double quotes
- **Type hints:** Required for all public APIs

---

## TypeScript

### Tools

| Tool | Purpose | Config |
|------|---------|--------|
| **Prettier** | Format | `.prettierrc.json` |
| **ESLint** | Lint | `eslint.config.mjs` |
| **tsc** | Type checking | `tsconfig.json` |
| **Vitest** | Testing + coverage | `vitest.config.ts` |

### Commands

```bash
# Format
npx prettier --write .

# Lint
npx eslint .
npx eslint --fix .

# Type check
npm run typecheck  # in each package

# Test
npm test
npm run test:coverage
```

### Rules

- **Line length:** 120
- **Target:** ES2022
- **Quotes:** Double quotes
- **Trailing commas:** ES5
- **Semi:** Always
- **Plugins:** Tailwind CSS class sorting

---

## Pre-commit Hooks

### Tool: Lefthook

Lefthook runs on every commit and push to enforce quality gates.

**Install:**
```bash
lefthook install
```

**Config:** `lefthook.yml`

### Pre-commit (runs on `git commit`)

- `ruff format` — auto-format Python files
- `ruff check --fix` — auto-fix Python lint errors
- `prettier --write` — auto-format TS/JS/JSON/MD/YAML
- `eslint --fix` — auto-fix TypeScript lint errors

All fixes are automatically staged.

### Pre-push (runs on `git push`)

- `mypy` — type check Python libs
- `basedpyright` — type check Python services
- `tsc --noEmit` — type check TypeScript packages
- `pytest` — run Python unit tests
- `vitest` — run TypeScript unit tests

---

## CI

### Workflow: `.github/workflows/ci.yml`

**Jobs:**
1. **Python Lint** — `ruff check`
2. **Python Types** — `mypy` + `basedpyright`
3. **Python Tests** — `pytest --cov` (80%+ coverage)
4. **TypeScript Lint** — `eslint`
5. **TypeScript Types** — `tsc --noEmit`
6. **TypeScript Tests** — `vitest --coverage` (80%+ coverage)
7. **Security Audit** — `pip-audit` + `npm audit`
8. **Build** — Docker images for all services

**Target:** <6 min total runtime

---

## Coverage

### Python

```bash
pytest --cov --cov-report=html
open htmlcov/index.html
```

**Target:** 80%+ line coverage

### TypeScript

```bash
npm run test:coverage
open coverage/index.html
```

**Target:** 80%+ line coverage

---

## Conventions

### Python

- **Imports:** Absolute imports preferred, relative imports only within same package
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes
- **Docstrings:** Google style for public APIs
- **Type hints:** Required for function signatures, optional for internal variables
- **Error handling:** Specific exceptions, no bare `except:`

### TypeScript

- **Imports:** Absolute imports via `@/` alias
- **Naming:** `camelCase` for functions/variables, `PascalCase` for components/classes
- **JSDoc:** Required for exported functions
- **Type safety:** `strict: true`, no `any` without justification
- **React:** Functional components, hooks, no class components

---

## Makefile Targets

```bash
# Format entire codebase
make format

# Lint entire codebase
make lint

# Type check entire codebase
make typecheck

# Run all tests
make test

# Run full harness (format + lint + typecheck + test)
make harness
```

---

## Migration Notes

**Before Phase 7:**
- Mixed code styles (Rust, Go, Python, TypeScript)
- No consistent formatting
- No pre-commit hooks
- Manual lint/format enforcement

**After Phase 7:**
- Consistent Python + TypeScript styles
- Auto-formatting on commit
- Type checking on push
- CI enforces all quality gates
- 80%+ test coverage

---

## Troubleshooting

### Ruff errors

```bash
# Show all errors
ruff check .

# Auto-fix safe errors
ruff check --fix .

# Ignore specific error
# Add to ruff.toml [lint.ignore]
```

### ESLint errors

```bash
# Show all errors
npx eslint .

# Auto-fix safe errors
npx eslint --fix .

# Disable specific rule
// eslint-disable-next-line rule-name
```

### Type errors

```bash
# Python
mypy --show-error-codes libs/python/

# TypeScript
npm run typecheck -- --pretty
```

### Pre-commit hook failures

```bash
# Skip hooks (emergency only)
git commit --no-verify

# Re-run hooks manually
lefthook run pre-commit
```

---

## References

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Prettier Documentation](https://prettier.io/docs/en/)
- [ESLint Documentation](https://eslint.org/docs/latest/)
- [Lefthook Documentation](https://github.com/evilmartians/lefthook)
- [pytest Documentation](https://docs.pytest.org/)
- [Vitest Documentation](https://vitest.dev/)
