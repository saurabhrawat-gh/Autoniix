from __future__ import annotations

import redis.asyncio as aioredis
import structlog

from src.config import settings

logger = structlog.get_logger()

_redis: aioredis.Redis | None = None
_redis_pubsub: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        logger.info("redis.connecting", url=settings.redis_url)
        _redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_keepalive=True,
        )
        await _redis.ping()
        logger.info("redis.connected")
    return _redis


async def get_pubsub_redis() -> aioredis.Redis:
    """Return a Redis client configured for pub/sub (socket_timeout=None).

    Regular clients in redis-py 8 default to socket_timeout=5s, which kills
    idle pubsub connections every 5 seconds.  Pub/sub subscribers must block
    indefinitely waiting for the next message, so they need no socket timeout.
    """
    global _redis_pubsub
    if _redis_pubsub is None:
        _redis_pubsub = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_keepalive=True,
            socket_timeout=None,
        )
    return _redis_pubsub


async def close_redis() -> None:
    global _redis, _redis_pubsub
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        logger.info("redis.closed")
    if _redis_pubsub is not None:
        await _redis_pubsub.aclose()
        _redis_pubsub = None
