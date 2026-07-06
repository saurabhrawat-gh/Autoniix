"""Permission cache for the named RBAC system (Story #218).

Role-to-permission mappings are stored in `role_permissions` and cached
in-process with a 30-second TTL.  A Redis pub/sub channel
``permissions.invalidate`` allows any service to clear the cache
immediately (e.g. after an admin edits the matrix via a future admin UI).

Failures in Redis pub/sub degrade gracefully to TTL-only refresh.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import structlog

from core.db import get_pool

logger = structlog.get_logger()

_TTL_SECONDS = 30.0
CHANNEL_NAME = "permissions.invalidate"

KNOWN_ROLES: frozenset[str] = frozenset({"owner", "member", "viewer"})

_cache: dict[str, tuple[frozenset[str], float]] = {}

_subscriber_task: asyncio.Task[Any] | None = None


class PermissionMatrixUnavailable(RuntimeError):
    """Raised when the RBAC catalog is missing, unreadable, or empty for a known role.

    Distinct from a legitimate "role exists but has zero permissions" case so
    callers (e.g. ``/auth/me``) can surface a clear 503 instead of silently
    returning an empty permissions list and breaking the dashboard nav.
    """



def _is_cached(role: str) -> tuple[frozenset[str], float] | None:
    entry = _cache.get(role)
    if entry is None:
        return None
    perms, exp = entry
    if time.monotonic() > exp:
        del _cache[role]
        return None
    return entry


async def get_permissions_for_role(role: str) -> frozenset[str]:
    """Return the full set of permission names for *role*.

    Hot-path: returns from in-process cache (O(1)) on cache hits.
    Cache miss triggers one DB SELECT and re-populates the cache.
    """
    cached = _is_cached(role)
    if cached:
        return cached[0]

    try:
        pool = await get_pool()
        rows = await pool.fetch(
            "SELECT permission FROM role_permissions WHERE role = $1", role
        )
        perms: frozenset[str] = frozenset(r["permission"] for r in rows)
    except Exception as exc:
        logger.error(
            "permissions.cache.matrix_unavailable",
            role=role,
            error=str(exc),
            hint="Run 'make migrate' to apply scripts/migrations/202605220001_named_permissions.sql",
        )
        raise PermissionMatrixUnavailable(
            f"role_permissions table unreadable for role={role!r}: {exc}"
        ) from exc

    if not perms and role in KNOWN_ROLES:
        logger.error(
            "permissions.cache.empty_for_known_role",
            role=role,
            hint="Run 'make migrate' to seed scripts/migrations/202605220001_named_permissions.sql",
        )
        raise PermissionMatrixUnavailable(
            f"role_permissions matrix has no rows for known role={role!r} — "
            "RBAC catalog appears uninitialized"
        )

    _cache[role] = (perms, time.monotonic() + _TTL_SECONDS)
    return perms


async def verify_matrix_initialized() -> None:
    """Startup probe: assert the RBAC catalog is populated for the owner role.

    Intended to be called from app startup. Logs at ERROR (not warning) and
    raises :class:`PermissionMatrixUnavailable` if the matrix is missing or
    empty so the operator gets a loud signal instead of a silently broken
    dashboard.
    """
    perms = await get_permissions_for_role("owner")
    logger.info("permissions.matrix.verified", owner_perm_count=len(perms))


def invalidate(role: str | None = None) -> None:
    """Evict one role (or all roles if *role* is None) from the local cache."""
    if role is None:
        _cache.clear()
        logger.debug("permissions.cache.cleared_all")
    else:
        _cache.pop(role, None)
        logger.debug("permissions.cache.cleared", role=role)


async def publish_invalidate(role: str | None = None) -> None:
    """Publish an invalidation event.  Best-effort; never raises."""
    try:
        from core.redis_client import get_redis
        redis = await get_redis()
        payload = json.dumps({"role": role})
        await redis.publish(CHANNEL_NAME, payload)
    except Exception as exc:
        logger.warning("permissions.invalidate.publish_failed", error=str(exc))


async def _consume(pubsub: Any) -> None:
    async for message in pubsub.listen():
        if not message or message.get("type") != "message":
            continue
        try:
            data = json.loads(message.get("data") or "{}")
        except Exception:
            data = {}
        role = data.get("role")
        try:
            invalidate(role)
            logger.info("permissions.invalidate.applied", role=role)
        except Exception as exc:
            logger.warning("permissions.invalidate.apply_failed", error=str(exc))


async def _subscriber_loop() -> None:
    from core.redis_client import get_redis
    while True:
        try:
            redis = await get_redis()
            pubsub = redis.pubsub()
            await pubsub.subscribe(CHANNEL_NAME)
            logger.info("permissions.invalidate.subscribed", channel=CHANNEL_NAME)
            await _consume(pubsub)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("permissions.invalidate.subscriber_crashed", error=str(exc))
            await asyncio.sleep(2.0)


def start_subscriber() -> asyncio.Task[Any] | None:
    """Spawn the pub/sub subscriber as a background task. Idempotent."""
    global _subscriber_task
    if _subscriber_task is not None and not _subscriber_task.done():
        return _subscriber_task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    _subscriber_task = loop.create_task(_subscriber_loop())
    return _subscriber_task


async def stop_subscriber() -> None:
    global _subscriber_task
    if _subscriber_task is None:
        return
    _subscriber_task.cancel()
    try:
        await _subscriber_task
    except (asyncio.CancelledError, Exception):
        pass
    _subscriber_task = None
