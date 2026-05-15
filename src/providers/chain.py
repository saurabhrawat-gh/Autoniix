"""Priority-chain provider resolution (scope + content-mode aware).

Resolves a category to an ordered list of provider instances by walking
six layers in `provider_chains_v2`, most-specific first, and always
appending the per-category ``is_default_fallback`` credential at the
tail so the pipeline never hard-fails:

    1. (scope='channel',    scope_id=channel_id, content_mode=<mode>)
    2. (scope='channel',    scope_id=channel_id, content_mode=NULL)
    3. (scope='workspace',  scope_id=NULL,       content_mode=<mode>)
    4. (scope='workspace',  scope_id=NULL,       content_mode=NULL)
    5. (scope='system',     scope_id=NULL,       content_mode=NULL)
    6. provider_credentials WHERE is_default_fallback = TRUE

Each layer appends-with-dedup, so a partial channel override (e.g. one
extra primary credential) still inherits the workspace tail.

Falls back to env-based registry if:
  - the ``providers.db_chain.enabled`` feature flag is off,
  - or all six layers resolve to nothing,
  - or any DB call fails.

Resolved chains are cached in-process for ``_TTL_SECONDS`` so the
runtime doesn't hit Postgres on every call. The cache is invalidated
either by TTL expiry or by an explicit :func:`invalidate` call (which
``providers.invalidation.start_subscriber`` triggers in response to
Redis pub/sub events from the BFF).
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Iterable

import structlog

from src.providers.secrets import get_secret_at

logger = structlog.get_logger()

_TTL_SECONDS = 30.0

# Sentinel returned by resolve_chain when the DB chain query succeeded
# but yielded zero usable rows (no credentials configured / all disabled).
# Distinct from ``None`` which means "DB unavailable, fall back to env".
EMPTY_CHAIN: Any = object()


class NoProviderConfigured(RuntimeError):
    """Raised by callers when resolve_chain returns EMPTY_CHAIN and no
    env-var fallback is available. Surfaced to the UI/job runner so the
    user gets a clear "configure a provider in the dashboard" message
    instead of a silent ghost provider.
    """

    def __init__(self, category: str, *, channel_id: str | None = None,
                 content_mode: str | None = None):
        self.category = category
        self.channel_id = channel_id
        self.content_mode = content_mode
        hint = f" channel={channel_id}" if channel_id else ""
        hint += f" mode={content_mode}" if content_mode else ""
        super().__init__(
            f"No provider configured for category '{category}'{hint}. "
            f"Add a credential and chain entry in /dashboard/providers."
        )

# key -> (instance, expires_monotonic)
_chain_cache: dict[tuple[str, str, str], tuple[Any, float]] = {}
_lock = asyncio.Lock()


def _cache_key(category: str, channel_id: str | None, content_mode: str | None) -> tuple[str, str, str]:
    return (channel_id or "", content_mode or "", category)


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


async def _load_layer(
    conn: Any,
    *,
    category: str,
    scope: str,
    scope_id: str | None,
    content_mode: str | None,
) -> list[dict]:
    """Return chain rows for one (scope, scope_id, content_mode) layer."""
    rows = await conn.fetch(
        """
        SELECT pc.id, pc.provider_name, pc.vault_path, pc.extra_config,
               pc.model, pc.enabled, pc.last_health_ok, pc.label,
               c.position, c.fallback_strategy
          FROM provider_chains_v2 c
          JOIN provider_credentials pc ON pc.id = c.credential_id
         WHERE c.scope    = $1
           AND c.category = $2
           AND pc.enabled = TRUE
           AND COALESCE(c.is_enabled, TRUE) = TRUE
           AND ($3::text IS NULL AND c.scope_id IS NULL OR c.scope_id = $3)
           AND ($4::text IS NULL AND c.content_mode IS NULL OR c.content_mode = $4)
         ORDER BY c.position
        """,
        scope, category, scope_id, content_mode,
    )
    return [dict(r) for r in rows]


async def _load_default_fallback(conn: Any, category: str) -> dict | None:
    row = await conn.fetchrow(
        """
        SELECT id, provider_name, vault_path, extra_config, model,
               enabled, last_health_ok, label
          FROM provider_credentials
         WHERE category = $1 AND is_default_fallback = TRUE AND enabled = TRUE
         LIMIT 1
        """,
        category,
    )
    return dict(row) if row else None


async def _load_chain(
    category: str,
    *,
    channel_id: str | None,
    content_mode: str | None,
) -> list[dict]:
    """Load the merged 6-layer chain for ``category``.

    Returns a deduped list (in order) of credential rows, each with at
    least: ``id, provider_name, vault_path, extra_config, model, label``.
    """
    from src.db import get_pool
    pool = await get_pool()

    layers: list[tuple[str, str | None, str | None]] = []
    if channel_id:
        if content_mode:
            layers.append(("channel", channel_id, content_mode))
        layers.append(("channel", channel_id, None))
    if content_mode:
        layers.append(("workspace", None, content_mode))
    layers.append(("workspace", None, None))
    layers.append(("system", None, None))

    merged: list[dict] = []
    seen: set[int] = set()
    async with pool.acquire() as conn:
        for scope, sid, mode in layers:
            try:
                rows = await _load_layer(
                    conn, category=category, scope=scope, scope_id=sid, content_mode=mode,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("provider.chain_layer_failed",
                               category=category, scope=scope,
                               scope_id=sid, mode=mode, error=str(exc))
                continue
            for r in rows:
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                r["__origin__"] = (
                    f"{scope}+mode" if mode else scope
                )
                merged.append(r)

        # Always append the per-category default fallback credential.
        try:
            fb = await _load_default_fallback(conn, category)
        except Exception as exc:  # noqa: BLE001
            logger.warning("provider.chain_default_fallback_failed",
                           category=category, error=str(exc))
            fb = None
        if fb and fb["id"] not in seen:
            fb["__origin__"] = "default"
            merged.append(fb)
            seen.add(fb["id"])

    return merged


class FallbackProvider:
    """Wraps an ordered list of providers; delegates calls and advances on error."""

    def __init__(self, category: str, members: list[Any], labels: list[str]):
        self._category = category
        self._members = members
        self._labels = labels

    @property
    def members(self) -> list[Any]:
        """Public accessor for the in-order provider instances."""
        return list(self._members)

    @property
    def labels(self) -> list[str]:
        return list(self._labels)

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


def _instantiate(
    provider_name: str,
    vault_path: str,
    extra_config: dict,
    model: str | None,
    registry_map: dict,
) -> Any:
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
    # Allow extra_config to override attributes (e.g. base_url, voice_id).
    for k, v in (extra_config or {}).items():
        try:
            setattr(inst, k, v)
        except Exception:
            pass
    # Per-credential model pin (column on provider_credentials). If the
    # provider class supports a `model` attribute we set it; the LLM
    # router additionally fills `LLMRequest.model` from `_pinned_model`.
    if model:
        try:
            setattr(inst, "model", model)
        except Exception:
            pass
        try:
            setattr(inst, "_pinned_model", model)
        except Exception:
            pass
    return inst


async def resolve_chain(
    category: str,
    registry_map: dict,
    *,
    channel_id: str | None = None,
    content_mode: str | None = None,
) -> Any | None:
    """Return a :class:`FallbackProvider` for the (category, channel, mode) tuple.

    Returns ``None`` when the feature flag is off, the merged chain is
    empty, or every member fails to instantiate. Callers fall through to
    env-driven resolution in that case.
    """
    # First-call side effect: ensure the cross-service invalidation
    # subscriber is running. Idempotent + best-effort; if Redis is
    # unreachable the runtime degrades to TTL-only refresh.
    try:
        from src.providers.invalidation import start_subscriber
        start_subscriber()
    except Exception:  # noqa: BLE001
        pass

    key = _cache_key(category, channel_id, content_mode)
    cached = _chain_cache.get(key)
    now = time.monotonic()
    if cached and cached[1] > now:
        return cached[0]

    async with _lock:
        cached = _chain_cache.get(key)
        if cached and cached[1] > now:
            return cached[0]
        if not await _flag_enabled():
            return None
        try:
            rows = await _load_chain(
                category, channel_id=channel_id, content_mode=content_mode,
            )
        except Exception as exc:
            logger.warning("provider.chain_load_failed",
                           category=category, channel_id=channel_id,
                           content_mode=content_mode, error=str(exc))
            return None
        if not rows:
            # Explicit empty result: DB reachable, no enabled credentials.
            # Cache it so we don't hammer the DB, and return the sentinel
            # so callers can distinguish from "DB down".
            _chain_cache[key] = (EMPTY_CHAIN, now + _TTL_SECONDS)
            return EMPTY_CHAIN

        members: list[Any] = []
        labels: list[str] = []
        models: list[str | None] = []
        origins: list[str] = []
        for r in rows:
            try:
                inst = _instantiate(
                    r["provider_name"],
                    r["vault_path"],
                    r["extra_config"] or {},
                    r.get("model"),
                    registry_map,
                )
                members.append(inst)
                labels.append(r["label"])
                models.append(r.get("model"))
                origins.append(r.get("__origin__", ""))
            except Exception as exc:
                logger.warning("provider.chain_member_failed",
                               category=category, provider=r["provider_name"],
                               error=str(exc))
        if not members:
            return None
        wrapped = FallbackProvider(category, members, labels)
        # Surface metadata for the LLM router / UI debug endpoints.
        wrapped.models = models  # type: ignore[attr-defined]
        wrapped.origins = origins  # type: ignore[attr-defined]
        wrapped.provider_names = [r["provider_name"] for r in rows]  # type: ignore[attr-defined]
        wrapped.credential_ids = [r["id"] for r in rows]  # type: ignore[attr-defined]
        _chain_cache[key] = (wrapped, now + _TTL_SECONDS)
        logger.info("provider.chain_resolved",
                    category=category, channel_id=channel_id,
                    content_mode=content_mode, members=labels,
                    origins=origins)
        return wrapped


def invalidate(
    category: str | None = None,
    channel_id: str | None = None,
    content_mode: str | None = None,
) -> None:
    """Drop matching entries from the in-process chain cache.

    A ``None`` argument acts as a wildcard. Called both directly (after
    a local mutation in the BFF) and via the Redis pub/sub subscriber in
    every other service.
    """
    if category is None and channel_id is None and content_mode is None:
        _chain_cache.clear()
        return
    targets = [
        k for k in _chain_cache.keys()
        if (category is None or k[2] == category)
        and (channel_id is None or k[0] == (channel_id or ""))
        and (content_mode is None or k[1] == (content_mode or ""))
    ]
    for k in targets:
        _chain_cache.pop(k, None)


def reset_chain_cache() -> None:
    """Back-compat alias for :func:`invalidate` (clears everything)."""
    _chain_cache.clear()
