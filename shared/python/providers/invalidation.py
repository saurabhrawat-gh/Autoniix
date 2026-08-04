"""Cross-process cache invalidation for provider chains.

The BFF mutates `provider_credentials` / `provider_chains_v2` in
response to dashboard actions (add credential, reorder chain, set
default fallback, etc). Every other service in the fleet caches
resolved chains for ``_TTL_SECONDS`` (see :mod:`providers.chain`),
so without an out-of-band signal a key change wouldn't be picked up
until the TTL expires.

This module wires a tiny pub/sub on top of the existing Redis client:

    * BFF calls :func:`publish_invalidate(category, channel_id, content_mode)`
      after each mutating endpoint.
    * Every service (FastAPI ``main.py`` and Temporal workers) calls
      :func:`start_subscriber()` at boot. The subscriber listens to
      ``providers.invalidate`` and forwards events to
      :func:`providers.chain.invalidate` and
      :func:`providers.registry.ProviderRegistry.reset`.

Failures are intentionally swallowed: if Redis is unreachable the
runtime degrades to TTL-only refresh, which is exactly the behaviour
prior to this module being introduced.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

logger = structlog.get_logger()

CHANNEL_NAME = "providers.invalidate"

_subscriber_task: asyncio.Task[Any] | None = None


async def publish_invalidate(
    category: str | None = None,
    channel_id: str | None = None,
    content_mode: str | None = None,
) -> None:
    """Broadcast a cache-invalidation event.

    A ``None`` argument means "wildcard" — subscribers will drop every
    cache entry that matches the non-``None`` axes. Always best-effort.
    """
    try:
        from core.redis_client import get_redis
        redis = await get_redis()
        payload = json.dumps({
            "category": category,
            "channel_id": channel_id,
            "content_mode": content_mode,
        })
        await redis.publish(CHANNEL_NAME, payload)
        logger.debug("providers.invalidate.published",
                     category=category, channel_id=channel_id,
                     content_mode=content_mode)
    except Exception as exc:  # noqa: BLE001
        logger.warning("providers.invalidate.publish_failed", error=str(exc))


async def _consume(pubsub: Any) -> None:
    """Forward each Redis message to the local cache invalidator."""
    from providers import chain as chain_mod
    from providers.registry import ProviderRegistry

    async for message in pubsub.listen():
        if not message or message.get("type") != "message":
            continue
        try:
            data = json.loads(message.get("data") or "{}")
        except Exception:
            data = {}
        category = data.get("category")
        channel_id = data.get("channel_id")
        content_mode = data.get("content_mode")
        try:
            chain_mod.invalidate(
                category=category, channel_id=channel_id, content_mode=content_mode,
            )
            ProviderRegistry.reset()
            logger.info("providers.invalidate.applied",
                        category=category, channel_id=channel_id,
                        content_mode=content_mode)
        except Exception as exc:  # noqa: BLE001
            logger.warning("providers.invalidate.apply_failed", error=str(exc))


async def _subscriber_loop() -> None:
    """Reconnect-loop wrapper around :func:`_consume`."""
    from core.redis_client import get_redis

    while True:
        try:
            redis = await get_redis()
            pubsub = redis.pubsub()
            await pubsub.subscribe(CHANNEL_NAME)
            logger.info("providers.invalidate.subscribed", channel=CHANNEL_NAME)
            await _consume(pubsub)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("providers.invalidate.subscriber_crashed", error=str(exc))
            await asyncio.sleep(2.0)


def start_subscriber() -> asyncio.Task[Any] | None:
    """Spawn the subscriber as a background task. Idempotent.

    Returns the task (or None if the loop isn't running yet — callers in
    sync contexts should schedule it from inside their startup hook).
    """
    global _subscriber_task
    if _subscriber_task is not None and not _subscriber_task.done():
        return _subscriber_task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("providers.invalidate.no_loop")
        return None
    _subscriber_task = loop.create_task(_subscriber_loop())
    return _subscriber_task


async def stop_subscriber() -> None:
    """Cancel the subscriber task (best-effort)."""
    global _subscriber_task
    if _subscriber_task is None:
        return
    _subscriber_task.cancel()
    try:
        await _subscriber_task
    except (asyncio.CancelledError, Exception):  # noqa: BLE001
        pass
    _subscriber_task = None
