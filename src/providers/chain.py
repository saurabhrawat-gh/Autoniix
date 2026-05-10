"""Priority-chain provider resolution.

Looks up the configured chain for a category from the DB
(``provider_priority_chains`` joined to ``provider_credentials``),
instantiates each provider with credentials pulled from the secrets
backend, and wraps them in a :class:`FallbackProvider` that delegates
calls in order, advancing on error.

Falls back to env-based registry if:
  - the ``providers.db_chain.enabled`` feature flag is off,
  - or the chain is empty for that category,
  - or any DB call fails.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import structlog

from src.providers.secrets import get_secret_at

logger = structlog.get_logger()

_chain_cache: dict[str, Any] = {}
_lock = asyncio.Lock()


async def _flag_enabled() -> bool:
    """Cheap check; returns False if the DB / flag isn't reachable."""
    try:
        from src.db import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT enabled FROM feature_flags WHERE key = $1",
                "providers.db_chain.enabled",
            )
        return bool(row and row["enabled"])
    except Exception:
        return False


async def _load_chain(category: str) -> list[dict]:
    from src.db import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT pc.id, pc.provider_name, pc.vault_path, pc.extra_config,
                   pc.enabled, pc.last_health_ok, pc.label, ppc.position,
                   ppc.fallback_strategy
              FROM provider_priority_chains ppc
              JOIN provider_credentials pc ON pc.id = ppc.credential_id
             WHERE ppc.category = $1
               AND pc.enabled = TRUE
             ORDER BY ppc.position
            """,
            category,
        )
    return [dict(r) for r in rows]


class FallbackProvider:
    """Wraps an ordered list of providers; delegates calls and advances on error."""

    def __init__(self, category: str, members: list[Any], labels: list[str]):
        self._category = category
        self._members = members
        self._labels = labels

    def __getattr__(self, name: str) -> Any:
        # Return a callable that tries each member in order. Both sync and
        # async methods are supported; we detect at call time.
        members = self._members
        labels = self._labels
        category = self._category

        def _call(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for member, label in zip(members, labels):
                fn = getattr(member, name, None)
                if fn is None:
                    continue
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("provider.fallback",
                                   category=category, label=label,
                                   method=name, error=str(exc))
                    last_exc = exc
            if last_exc:
                raise last_exc
            raise AttributeError(name)

        async def _acall(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for member, label in zip(members, labels):
                fn = getattr(member, name, None)
                if fn is None:
                    continue
                try:
                    res = fn(*args, **kwargs)
                    if asyncio.iscoroutine(res):
                        return await res
                    return res
                except Exception as exc:  # noqa: BLE001
                    logger.warning("provider.fallback",
                                   category=category, label=label,
                                   method=name, error=str(exc))
                    last_exc = exc
            if last_exc:
                raise last_exc
            raise AttributeError(name)

        # Probe the first method that actually exists to decide sync vs async
        for member in members:
            fn = getattr(member, name, None)
            if fn is None:
                continue
            if asyncio.iscoroutinefunction(fn):
                return _acall
            return _call
        raise AttributeError(f"No member of {category} chain has method {name!r}")


def _instantiate(provider_name: str, vault_path: str, extra_config: dict, registry_map: dict) -> Any:
    cls = registry_map.get(provider_name)
    if cls is None:
        raise ValueError(f"Provider {provider_name!r} not registered")
    api_key = get_secret_at(vault_path, "api_key")
    # Provider classes today read from settings/env; we expose secrets
    # by setting them in os.environ as a non-destructive shim. Long-term
    # each provider should accept explicit creds in __init__.
    if api_key:
        upper = provider_name.upper().replace("-", "_") + "_API_KEY"
        os.environ.setdefault(upper, api_key)
    inst = cls()
    # Allow extra_config to override attributes (e.g. base_url, model)
    for k, v in (extra_config or {}).items():
        try:
            setattr(inst, k, v)
        except Exception:
            pass
    return inst


async def resolve_chain(category: str, registry_map: dict) -> Any | None:
    """Returns a FallbackProvider for ``category`` or ``None`` if unavailable."""
    if category in _chain_cache:
        return _chain_cache[category]

    async with _lock:
        if category in _chain_cache:
            return _chain_cache[category]
        if not await _flag_enabled():
            return None
        try:
            rows = await _load_chain(category)
        except Exception as exc:
            logger.warning("provider.chain_load_failed", category=category, error=str(exc))
            return None
        if not rows:
            return None

        members: list[Any] = []
        labels: list[str] = []
        for r in rows:
            try:
                inst = _instantiate(
                    r["provider_name"], r["vault_path"], r["extra_config"] or {}, registry_map
                )
                members.append(inst)
                labels.append(r["label"])
            except Exception as exc:
                logger.warning("provider.chain_member_failed",
                               category=category, provider=r["provider_name"],
                               error=str(exc))
        if not members:
            return None
        wrapped = FallbackProvider(category, members, labels)
        _chain_cache[category] = wrapped
        logger.info("provider.chain_resolved", category=category,
                    members=labels)
        return wrapped


def reset_chain_cache() -> None:
    _chain_cache.clear()
