"""Workspace membership cache for immediate session revocation (Story #226).

Every authenticated request checks that the resolved user is still an active
member of the workspace encoded in their JWT.  The check is cached in-process
for ``_TTL_SECONDS`` to avoid a DB round-trip on every hot endpoint.

When a member is removed (``DELETE /workspace/members/{user_id}``), the
endpoint publishes a ``membership.revoked`` Redis pub/sub message.  All
service instances clear the relevant cache entry immediately so the removed
user's *next* request gets HTTP 403 ``workspace_access_revoked``.

Failures in Redis degrade gracefully to TTL-only refresh — the maximum
window before revocation takes effect is then ``_TTL_SECONDS``.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import structlog

from src.db import get_pool  # re-exported at module level so tests can monkeypatch

logger = structlog.get_logger()

_TTL_SECONDS = 30.0
CHANNEL_NAME = "membership.revoked"

# Cache: (user_id, workspace_id) → (is_member: bool, expires_at: float)
_cache: dict[tuple[int, int], tuple[bool, float]] = {}

_subscriber_task: asyncio.Task[Any] | None = None


def _is_cached(user_id: int, workspace_id: int) -> tuple[bool, float] | None:
    entry = _cache.get((user_id, workspace_id))
    if entry is None:
        return None
    is_member, exp = entry
    if time.monotonic() > exp:
        del _cache[(user_id, workspace_id)]
        return None
    return entry


async def check_membership(user_id: int, workspace_id: int) -> bool:
    """Return True if *user_id* is an active member of *workspace_id*.

    Hot-path: O(1) in-process cache on cache hits.
    Cache miss triggers a single DB query and re-populates the cache.
    """
    cached = _is_cached(user_id, workspace_id)
    if cached is not None:
        return cached[0]

    try:
        pool = await get_pool()
        row = await pool.fetchval(
            "SELECT 1 FROM workspace_members WHERE user_id=$1 AND workspace_id=$2",
            user_id, workspace_id,
        )
        is_member = row is not None
    except Exception as exc:
        logger.warning("membership.cache.db_error",
                       user_id=user_id, workspace_id=workspace_id, error=str(exc))
        return True  # fail-open: don't revoke on DB error

    _cache[(user_id, workspace_id)] = (is_member, time.monotonic() + _TTL_SECONDS)
    return is_member


def invalidate(user_id: int | None = None, workspace_id: int | None = None) -> None:
    """Evict matching entries from the local cache.

    If both are None, clears the entire cache.
    If only user_id is given, evicts all workspaces for that user.
    If both are given, evicts the specific (user_id, workspace_id) entry.
    """
    if user_id is None and workspace_id is None:
        _cache.clear()
        logger.debug("membership.cache.cleared_all")
        return
    to_delete = [
        k for k in _cache
        if (user_id is None or k[0] == user_id) and (workspace_id is None or k[1] == workspace_id)
    ]
    for k in to_delete:
        del _cache[k]
    if to_delete:
        logger.debug("membership.cache.cleared", keys=to_delete)


async def publish_revoked(user_id: int, workspace_id: int) -> None:
    """Broadcast a membership-revoked event.  Best-effort; never raises."""
    try:
        from src.redis_client import get_redis
        redis = await get_redis()
        payload = json.dumps({"user_id": user_id, "workspace_id": workspace_id})
        await redis.publish(CHANNEL_NAME, payload)
        logger.info("membership.revoked.published",
                    user_id=user_id, workspace_id=workspace_id)
    except Exception as exc:
        logger.warning("membership.revoked.publish_failed", error=str(exc))


async def _consume(pubsub: Any) -> None:
    async for message in pubsub.listen():
        if not message or message.get("type") != "message":
            continue
        try:
            data = json.loads(message.get("data") or "{}")
        except Exception:
            data = {}
        uid = data.get("user_id")
        wid = data.get("workspace_id")
        try:
            invalidate(
                user_id=int(uid) if uid is not None else None,
                workspace_id=int(wid) if wid is not None else None,
            )
            logger.info("membership.revoked.applied", user_id=uid, workspace_id=wid)
        except Exception as exc:
            logger.warning("membership.revoked.apply_failed", error=str(exc))


async def _subscriber_loop() -> None:
    from src.redis_client import get_redis
    while True:
        try:
            redis = await get_redis()
            pubsub = redis.pubsub()
            await pubsub.subscribe(CHANNEL_NAME)
            logger.info("membership.revoked.subscribed", channel=CHANNEL_NAME)
            await _consume(pubsub)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("membership.revoked.subscriber_crashed", error=str(exc))
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
