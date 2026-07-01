"""Provider clean-slate helper.

Shared between the CLI (`scripts/clean_slate_providers.py`) and the BFF
admin endpoint (`POST /api/v2/providers/_admin/clean-slate`). Lives
under `src/providers/` so it ships in the same Docker image as the BFF.

Wipes ALL provider configuration to a true clean slate:
- Truncates every provider-related table (credentials, chains, routes,
  quotas, sandbox runs).
- Best-effort clears the vault prefix where secrets are stored.
- Invalidates local + cluster-wide chain caches.

Keeps schemas, categories, content_modes, and feature flags untouched.
"""
from __future__ import annotations

import structlog

from src.db import get_pool

logger = structlog.get_logger()


PROVIDER_TABLES = [
    "provider_chains_v2",
    "provider_priority_chains",
    "provider_routes",
    "provider_quotas",
    "provider_sandbox_runs",
    "provider_credentials",
]


async def _truncate_provider_tables() -> list[str]:
    pool = await get_pool()
    done: list[str] = []
    for t in PROVIDER_TABLES:
        try:
            exists = await pool.fetchval(
                "SELECT to_regclass($1) IS NOT NULL", t,
            )
            if not exists:
                continue
            await pool.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE")
            done.append(t)
        except Exception as exc:
            logger.warning("provider_truncate.failed", table=t, error=str(exc))
    return done


def _wipe_vault_secrets() -> int:
    """Best-effort: remove provider/* secrets from the backing vault/db.

    `delete_prefix` is implemented by backends that own writable
    storage (currently `db`). Env/Vault/Infisical are skipped silently.
    """
    try:
        from src.providers.secrets import delete_prefix
        return int(delete_prefix("providers/") or 0)
    except Exception as exc:
        logger.warning("vault.delete_prefix_failed", error=str(exc))
        return 0


def _invalidate_local_caches() -> None:
    try:
        from src.providers.chain import invalidate
        invalidate()
    except Exception:
        pass
    try:
        from src.providers.registry import ProviderRegistry
        ProviderRegistry.reset()
    except Exception:
        pass


async def _publish_invalidate() -> None:
    """Tell every running service to drop their cached chains too."""
    try:
        from src.providers.invalidation import publish_invalidate
        await publish_invalidate(category=None)
    except Exception as exc:
        logger.warning("publish_invalidate.failed", error=str(exc))


async def run(verbose: bool = False) -> dict:
    """Execute the full wipe. Returns a summary dict."""
    tables = await _truncate_provider_tables()
    if verbose:
        pass

    secrets = _wipe_vault_secrets()
    if verbose:
        pass

    _invalidate_local_caches()
    await _publish_invalidate()
    if verbose:
        pass

    return {"tables": tables, "secrets_deleted": secrets}
