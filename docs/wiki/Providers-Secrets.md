# Providers: Secrets

## Purpose

Unified API for reading provider credentials (API keys, OAuth refresh
tokens, etc.). Supports two backends.

## Source

- `src/providers/secrets.py:1-300`

## Backends

### env (default)

Reads directly from process env / `.env` file. No external dependency. The
fastest startup path; appropriate when ops trusts the host file system.

### infisical

Enabled with `SECRETS_BACKEND=infisical` and the compose `secrets` profile
(`infisical` service on port 8222). Provides a UI for rotation and per-env
scoping, but adds an extra dependency to the boot chain.

On read, the resolver falls back to env if Infisical is unreachable, so
the stack still boots cleanly during partial outages.

## API

```python
from src.providers.secrets import get_secret

key = await get_secret("OPENAI_API_KEY")           # env or Infisical
key = await get_secret("OPENAI_API_KEY", scope="channel:long")  # scoped
```

## Production secret guards

The BFF refuses to start in production if any of these are at default
(`CHANGE_ME`) values:

- `ADMIN_JWT_SECRET`, `AUTH_JWT_SECRET`
- `DB_PASSWORD`
- `S3_ACCESS_KEY`, `S3_SECRET_KEY`
- `GRAFANA_ADMIN_PASSWORD`

Generate strong secrets with `openssl rand -hex 32`.

## Related pages

- [[Security-Authn-Authz]] · [[Operations-Runbook]] · [[Appendix-Env-Vars]]
