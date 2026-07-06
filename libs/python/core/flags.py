"""Runtime feature-flag reader with in-process TTL cache.

The ``feature_flags`` table is the single source of truth for runtime toggles
that operators can flip without redeploying. Direct DB reads on every check
would multiply Postgres traffic across every service + every Temporal
activity, so this helper caches each key for ``_TTL_SECONDS`` seconds.

The cache is per-process and is intentionally simple — no invalidation
mechanism. When an operator toggles a flag via the dashboard, the change
becomes effective within ``_TTL_SECONDS``.

Boolean flags return ``feature_flags.enabled``. Non-boolean flags read
``feature_flags.payload['value']`` (the ``feature_flags`` schema is
boolean-first; non-boolean values live in the JSONB payload).

Public API
----------
* :func:`get_flag(key, default)` — async, returns the value or ``default``.
* :func:`get_flag_sync(key, default)` — sync convenience for non-async
  call-sites that already have a running event loop available.
* :func:`invalidate_cache(key)` — drop a single entry (e.g. immediately after
  the dashboard PUTs a new value).
* :func:`clear_cache()` — drop all entries (tests).

This module is part of AE-510 / P0 — Agentic Foundation.
"""
from __future__ import annotations

import asyncio
import json as _json
import time
from typing import Any

import structlog

from core.db import get_pool

logger = structlog.get_logger()

_TTL_SECONDS = 30.0

_cache: dict[str, tuple[Any, float]] = {}
_cache_lock = asyncio.Lock()


def _now() -> float:
    return time.monotonic()


def _is_fresh(expires_at: float) -> bool:
    return _now() < expires_at


def _extract_value(row: dict | None) -> Any | None:
    """Translate a ``feature_flags`` row to the public value shape.

    * If ``payload`` carries a ``value`` key, that wins (covers non-boolean
      flags such as integer intervals).
    * Otherwise return ``enabled`` (the boolean case).
    * For a missing row, the caller's ``default`` is used (handled upstream).

    Note: asyncpg returns JSONB columns as Python strings, not dicts. This
    function handles both representations so callers don't need to care.
    """
    if row is None:
        return None
    payload = row.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = _json.loads(payload) or {}
        except (ValueError, TypeError):
            payload = {}
    if isinstance(payload, dict) and "value" in payload:
        return payload["value"]
    return bool(row.get("enabled", False))


async def get_flag(key: str, default: Any = None) -> Any:
    """Read a feature flag with a 30s in-process cache.

    Returns ``default`` if the key does not exist in ``feature_flags`` OR if
    the DB read fails. Failures are logged at WARN — flag reads must never
    raise into business code (a single hiccup must not stop the pipeline).
    """
    cached = _cache.get(key)
    if cached is not None and _is_fresh(cached[1]):
        return cached[0]

    async with _cache_lock:
        cached = _cache.get(key)
        if cached is not None and _is_fresh(cached[1]):
            return cached[0]

        try:
            pool = await get_pool()
            row = await pool.fetchrow(
                "SELECT enabled, payload FROM feature_flags WHERE key = $1",
                key,
            )
        except Exception as exc:
            logger.warning("flags.read_failed", key=key, error=str(exc))
            return default

        value = _extract_value(dict(row) if row else None)
        if value is None:
            value = default
        _cache[key] = (value, _now() + _TTL_SECONDS)
        return value


def invalidate_cache(key: str) -> None:
    """Drop a single cache entry (e.g. after a dashboard PUT)."""
    _cache.pop(key, None)


def clear_cache() -> None:
    """Drop the entire cache. Intended for tests."""
    _cache.clear()
